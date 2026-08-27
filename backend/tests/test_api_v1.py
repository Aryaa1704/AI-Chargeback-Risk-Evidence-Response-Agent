"""Integration tests for the Phase 5 versioned risk and investigation API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.db.init_db import init_db
from app.db.session import get_db
from app.main import app
from app.ml.evaluation import evaluate_held_out_model
from app.ml.features import FEATURE_COLUMNS, build_training_frame
from app.ml.training import train_and_persist
from app.seed.generate_synthetic import seed_synthetic


@pytest.fixture()
def api_client(tmp_path: Path) -> TestClient:
    engine = create_engine(f"sqlite:///{tmp_path}/api.db", connect_args={"check_same_thread": False})
    init_db(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as db:
        seed_synthetic(db)
        frame = build_training_frame(db)
    training = train_and_persist(frame, tmp_path / "models")
    evaluate_held_out_model(frame, training.artifact_path, training.metadata_path)

    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: Settings(database_url=f"sqlite:///{tmp_path}/api.db", ml_model_artifact_path=str(training.artifact_path))
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _prediction_payload() -> dict[str, object]:
    return {"transaction_id": "synthetic_phase2_txn_0000", "amount": 450.0, "amount_deviation": 2.1, "transaction_velocity_24h": 3, "transaction_velocity_7d": 12, "customer_account_age_days": 180, "customer_dispute_count": 1, "customer_refund_count": 0, "customer_failed_tx_count": 1, "device_age_days": 21, "dispute_ratio": 0.08, "refund_ratio": 0.0, "has_device": 1, "is_new_device": 0, "currency": "INR", "status": "captured", "payment_method": "card", "merchant_category": "electronics", "customer_country": "IN", "merchant_country": "IN", "transaction_hour_bucket": "afternoon", "transaction_day_of_week": "Friday", "location_match": "match"}


def test_risk_prediction_is_model_backed_and_audited(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/risk/predict", json=_prediction_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["transaction_id"] == "synthetic_phase2_txn_0000"
    assert 0 <= body["risk_score"] <= 100
    assert body["model_derived_risk_factors"]
    summary = api_client.get("/api/v1/risk/summary").json()
    assert summary["total_predictions"] == 1
    dashboard = api_client.get("/api/v1/risk/dashboard")
    assert dashboard.status_code == 200
    dashboard_body = dashboard.json()
    assert dashboard_body["synthetic_data"] is True
    assert dashboard_body["kpis"]["total_transactions"] == summary["total_transactions"]
    assert dashboard_body["kpis"]["predicted_chargebacks"] == summary["total_predictions"]
    assert sum(point["count"] for point in dashboard_body["risk_score_histogram"]) == summary["total_predictions"]


def test_data_routes_metrics_metadata_validation_and_openapi(api_client: TestClient) -> None:
    transactions = api_client.get("/api/v1/transactions?page=1&page_size=2")
    assert transactions.status_code == 200 and transactions.json()["total"] == 267
    first = transactions.json()["items"][0]
    detail = api_client.get(f"/api/v1/transactions/{first['transaction_id']}")
    assert detail.status_code == 200 and detail.json()["customer_email"].endswith("synthetic.example.test")
    customer_id = first["customer_id"]
    assert api_client.get(f"/api/v1/customers/{customer_id}/history").status_code == 200
    assert api_client.get(f"/api/v1/customers/{customer_id}/disputes").status_code == 200
    metrics = api_client.get("/api/v1/model/metrics")
    assert metrics.status_code == 200 and "confusion_matrix" in metrics.json()["metrics"]
    dashboard_metrics = api_client.get("/api/v1/risk/dashboard").json()["model_metrics"]
    assert dashboard_metrics["metrics"] == metrics.json()["metrics"]
    assert api_client.get("/api/v1/model/info").json()["feature_count"] == len(FEATURE_COLUMNS)
    invalid = api_client.post("/api/v1/risk/predict", json={"transaction_id": "bad id", "amount": -1})
    assert invalid.status_code == 422 and invalid.json()["code"] == "validation_error"
    paths = api_client.get("/openapi.json").json()["paths"]
    assert {"/api/v1/risk/predict", "/api/v1/transactions", "/api/v1/model/metrics"} <= set(paths)


def test_transactions_support_search_status_and_sort(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/transactions", params={"search": "synthetic_phase2_txn_0000", "sort_by": "amount", "sort_dir": "asc"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["transaction_id"] == "synthetic_phase2_txn_0000"

    failed = api_client.get("/api/v1/transactions", params={"status": "failed", "sort_by": "status", "sort_dir": "desc"})
    assert failed.status_code == 200
    assert all(item["status"] == "failed" for item in failed.json()["items"])
