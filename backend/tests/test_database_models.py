"""Tests for Phase 1 database model foundation."""

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.customer import Customer
from app.models.merchant import Merchant
from app.models.transaction import Transaction


def test_database_initializes_with_expected_tables_indexes_and_foreign_keys() -> None:
    """Fresh metadata creation should produce valid tables, indexes, and FKs."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
        "agent_investigations",
        "case_recommendations",
        "customers",
        "devices",
        "disputes",
        "merchants",
        "risk_predictions",
        "risk_cases",
        "risk_case_history",
        "evidence_items",
        "evidence_packages",
        "transactions",
    }

    transaction_indexes = {index["name"] for index in inspector.get_indexes("transactions")}
    assert {"ix_transactions_transaction_id", "ix_transactions_customer_id", "ix_transactions_merchant_id"}.issubset(
        transaction_indexes
    )
    assert "ix_transactions_created_at" in transaction_indexes
    assert "ix_transactions_updated_at" in transaction_indexes

    transaction_fks = {fk["referred_table"] for fk in inspector.get_foreign_keys("transactions")}
    assert {"customers", "merchants", "devices"}.issubset(transaction_fks)


def test_relationships_persist_and_load() -> None:
    """Customer, merchant, and transaction relationships should round-trip."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)

    with SessionLocal() as session:
        customer = Customer(email="synthetic@example.test", full_name="Synthetic Customer", country="IN")
        merchant = Merchant(name="Synthetic Merchant", category="digital_goods", country="IN")
        transaction = Transaction(
            transaction_id="txn_synthetic_001",
            customer=customer,
            merchant=merchant,
            amount="125.50",
            currency="INR",
            status="captured",
        )
        session.add(transaction)
        session.commit()
        session.refresh(transaction)

        assert transaction.customer.email == "synthetic@example.test"
        assert transaction.merchant.name == "Synthetic Merchant"
