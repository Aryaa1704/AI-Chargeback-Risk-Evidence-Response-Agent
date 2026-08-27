"""Tests for deterministic synthetic data seeding."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.db.init_db import init_db
from app.db.session import get_db
from app.main import app
from app.models.customer import Customer
from app.models.device import Device
from app.models.dispute import Dispute
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.seed import generate_synthetic
from app.seed.scaffold import seed_synthetic_demo_data


def make_client(tmp_path: Path, env: str = "development") -> tuple[TestClient, any]:
    db_path = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(db_path, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    init_db(engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(app_env=env, database_url=db_path)
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_seed_endpoint_200_in_development(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/api/v1/seed")
    assert response.status_code == 200
    assert response.json()["status"] == "seeded"


def test_seed_endpoint_403_in_production(tmp_path: Path) -> None:
    client = make_client(tmp_path, env="production")
    response = client.post("/api/v1/seed")
    assert response.status_code == 403


def test_database_has_expected_counts_after_seed(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/api/v1/seed")
    assert response.status_code == 200
    counts = response.json()["counts"]
    assert counts["customers"] >= 10
    assert counts["transactions"] >= 100
    assert counts["disputes"] >= 10
    assert counts["devices"] >= 10


def test_seed_risk_patterns_include_disputed_transactions(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/api/v1/seed")
    assert response.status_code == 200
    counts = response.json()["counts"]
    assert counts["disputes"] >= 10


def test_seed_includes_curated_phase13_demo_transactions(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/api/v1/seed")
    assert response.status_code == 200

    for transaction_id in [
        "TX-DEMO-LOW-001",
        "TX-DEMO-MED-001",
        "TX-DEMO-HIGH-001",
        "TX-DEMO-REPEAT-001",
        "TX-DEMO-001",
    ]:
        detail = client.get(f"/api/v1/transactions/{transaction_id}")
        assert detail.status_code == 200
        assert detail.json()["transaction_id"] == transaction_id


def test_hero_demo_transaction_has_repeat_dispute_context(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/api/v1/seed")
    assert response.status_code == 200

    hero = client.get("/api/v1/transactions/TX-DEMO-001")
    assert hero.status_code == 200
    body = hero.json()
    assert body["amount"] == "1240.00"
    assert body["status"] == "failed"
    assert body["disputes_count"] == 1


def test_seed_is_idempotent_and_preserves_unrelated_records(tmp_path: Path) -> None:
    """The development endpoint can safely refresh only its controlled dataset."""
    db_path = f"sqlite:///{tmp_path}/idempotent.db"
    engine = create_engine(db_path, connect_args={"check_same_thread": False})
    init_db(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as db:
        unrelated = Customer(email="unrelated@example.test", full_name="Unrelated Customer", country="US")
        db.add(unrelated)
        db.commit()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="development", database_url=db_path)
    with TestClient(app) as client:
        responses = [client.post("/api/v1/seed") for _ in range(3)]
        hero = client.get("/api/v1/transactions/TX-DEMO-001")

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert [response.json()["counts"] for response in responses] == [responses[0].json()["counts"]] * 3
    assert hero.status_code == 200
    assert hero.json()["transaction_id"] == "TX-DEMO-001"

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Customer).where(Customer.email == "unrelated@example.test")) == 1
        assert db.scalar(select(func.count()).select_from(Customer)) == 105
        assert db.scalar(select(func.count()).select_from(Merchant)) == 22
        assert db.scalar(select(func.count()).select_from(Device)) == 46
        assert db.scalar(select(func.count()).select_from(Transaction)) == 267
        assert db.scalar(select(func.count()).select_from(Dispute)) == 39
        assert db.scalar(select(func.count()).select_from(Customer).where(Customer.email.like("synthetic_phase2.%"))) == 100
        assert db.scalar(select(func.count()).select_from(Merchant).where(Merchant.name.like("synthetic_phase2_%"))) == 18
        assert db.scalar(select(func.count()).select_from(Device).where(Device.fingerprint.like("synthetic_phase2_fp_%"))) == 42
        assert db.scalar(select(func.count()).select_from(Transaction).where(Transaction.transaction_id.like("synthetic_phase2_txn_%"))) == 260
        assert db.scalar(select(func.count()).select_from(Dispute).where(Dispute.reason_code.like("synthetic_phase2_%"))) == 35
        assert db.scalar(select(func.count()).select_from(Transaction).where(Transaction.transaction_id == "TX-DEMO-001")) == 1


def test_failed_seed_rolls_back_all_pending_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failure during a refresh leaves no partially committed dataset behind."""
    engine = create_engine(f"sqlite:///{tmp_path}/rollback.db", connect_args={"check_same_thread": False})
    init_db(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    original_upsert_all = generate_synthetic._upsert_all
    calls = 0

    def fail_after_customers(db, records):
        nonlocal calls
        calls += 1
        original_upsert_all(db, records)
        if calls == 1:
            raise RuntimeError("simulated seed failure")

    monkeypatch.setattr(generate_synthetic, "_upsert_all", fail_after_customers)
    with SessionLocal() as db:
        with pytest.raises(RuntimeError, match="simulated seed failure"):
            seed_synthetic_demo_data(db)
        assert db.scalar(select(func.count()).select_from(Customer)) == 0
