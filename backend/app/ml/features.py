"""Feature extraction for synthetic chargeback-risk model training.

The ORM schema intentionally stays small in early phases, so this module derives
several operational risk features from available relationships and uses stable
hash-based synthetic values only when the source field does not exist yet. No
randomness, Gemini calls, external APIs, or fabricated labels are used.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session, joinedload

from app.models.dispute import Dispute
from app.models.transaction import Transaction

NUMERIC_FEATURE_COLUMNS = [
    "amount",
    "amount_deviation",
    "transaction_velocity_24h",
    "transaction_velocity_7d",
    "customer_account_age_days",
    "customer_dispute_count",
    "customer_refund_count",
    "customer_failed_tx_count",
    "device_age_days",
    "dispute_ratio",
    "refund_ratio",
    "has_device",
    "is_new_device",
]
CATEGORICAL_FEATURE_COLUMNS = [
    "currency",
    "status",
    "payment_method",
    "merchant_category",
    "customer_country",
    "merchant_country",
    "transaction_hour_bucket",
    "transaction_day_of_week",
    "location_match",
]
FEATURE_COLUMNS = [*NUMERIC_FEATURE_COLUMNS, *CATEGORICAL_FEATURE_COLUMNS]
TARGET_COLUMN = "has_chargeback"
DATASET_VERSION = "synthetic_phase2_v2_22_features"

_PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]
_BASE_EVENT_TIME = datetime(2026, 8, 22, 12, 0, 0)


@dataclass(frozen=True)
class CustomerHistory:
    """Precomputed deterministic customer aggregates for risk features."""

    average_amount: float
    total_transactions: int
    dispute_count: int
    refund_count: int
    failed_transaction_count: int
    transaction_times: tuple[datetime, ...]


def _stable_int(value: str, modulo: int) -> int:
    """Return a deterministic integer bucket for synthetic fallback features."""
    digest = hashlib.sha256(value.encode()).hexdigest()
    return int(digest[:12], 16) % modulo


def _amount(transaction: Transaction) -> float:
    return float(transaction.amount or Decimal("0"))


def _event_time(transaction: Transaction) -> datetime:
    """Return deterministic transaction event time.

    The current Transaction model has audit `created_at` but no payment-event
    timestamp. To avoid identical server-default timestamps dominating velocity
    and time-bucket features, derive a stable synthetic event offset from the
    transaction id until a real transaction timestamp is introduced.
    """
    minutes_back = _stable_int(transaction.id, 60 * 24 * 30)
    return _BASE_EVENT_TIME - timedelta(minutes=minutes_back)


def _account_created_at(transaction: Transaction) -> datetime:
    """Return customer creation time, using a deterministic fallback age.

    Existing customers have audit `created_at`, but seeded rows are inserted in a
    tight batch. A stable fallback based on customer id gives meaningful account
    age without adding fake source fields to the ORM.
    """
    if transaction.customer and transaction.customer.created_at:
        age_days = 30 + _stable_int(transaction.customer.id, 365)
        return _event_time(transaction) - timedelta(days=age_days)
    return _event_time(transaction)


def _device_first_seen(transaction: Transaction) -> datetime | None:
    """Return device first-seen time or deterministic fallback when unavailable.

    Device currently exposes audit `created_at` but no explicit `first_seen`.
    The stable fallback preserves deterministic device age/new-device features.
    """
    if not transaction.device_id:
        return None
    age_days = _stable_int(transaction.device_id, 120)
    return _event_time(transaction) - timedelta(days=age_days)


def _payment_method(transaction: Transaction) -> str:
    """Derive deterministic payment method until Transaction gains the field."""
    return _PAYMENT_METHODS[_stable_int(transaction.id, len(_PAYMENT_METHODS))]


def _hour_bucket(event_time: datetime) -> str:
    hour = event_time.hour
    if hour <= 6:
        return "night"
    if hour <= 11:
        return "morning"
    if hour <= 17:
        return "afternoon"
    return "evening"


def _build_customer_history(
    transactions: list[Transaction], disputes: list[Dispute]
) -> dict[str, CustomerHistory]:
    dispute_count_by_customer: dict[str, int] = defaultdict(int)
    refund_count_by_customer: dict[str, int] = defaultdict(int)
    for dispute in disputes:
        dispute_count_by_customer[dispute.customer_id] += 1
        # There is no Refund model yet. Treat the synthetic dispute reason
        # `credit_not_processed` as the deterministic refund-like signal.
        if "credit_not_processed" in dispute.reason_code:
            refund_count_by_customer[dispute.customer_id] += 1

    transactions_by_customer: dict[str, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        transactions_by_customer[transaction.customer_id].append(transaction)

    history: dict[str, CustomerHistory] = {}
    for customer_id, customer_transactions in transactions_by_customer.items():
        amounts = [_amount(transaction) for transaction in customer_transactions]
        failed_count = sum(
            1 for transaction in customer_transactions if transaction.status in {"failed", "declined"}
        )
        history[customer_id] = CustomerHistory(
            average_amount=sum(amounts) / max(len(amounts), 1),
            total_transactions=len(customer_transactions),
            dispute_count=dispute_count_by_customer[customer_id],
            refund_count=refund_count_by_customer[customer_id],
            failed_transaction_count=failed_count,
            transaction_times=tuple(_event_time(transaction) for transaction in customer_transactions),
        )
    return history


def transaction_to_feature_row(
    transaction: Transaction,
    customer_history: dict[str, CustomerHistory] | None = None,
) -> dict[str, Any]:
    """Convert a transaction ORM object into the 22 model-ready feature values."""
    amount = _amount(transaction)
    event_time = _event_time(transaction)
    history = customer_history.get(transaction.customer_id) if customer_history else None
    customer_tx_count = history.total_transactions if history else 1
    customer_dispute_count = history.dispute_count if history else 0
    customer_refund_count = history.refund_count if history else 0
    device_first_seen = _device_first_seen(transaction)
    customer_country = transaction.customer.country if transaction.customer else "unknown"
    merchant_country = transaction.merchant.country if transaction.merchant else "unknown"

    return {
        "amount": amount,
        "amount_deviation": abs(amount - history.average_amount) if history else 0.0,
        "transaction_velocity_24h": sum(
            1
            for transaction_time in (history.transaction_times if history else ())
            if timedelta() <= event_time - transaction_time <= timedelta(days=1)
        ),
        "transaction_velocity_7d": sum(
            1
            for transaction_time in (history.transaction_times if history else ())
            if timedelta() <= event_time - transaction_time <= timedelta(days=7)
        ),
        "customer_account_age_days": max((_event_time(transaction) - _account_created_at(transaction)).days, 0),
        "customer_dispute_count": customer_dispute_count,
        "customer_refund_count": customer_refund_count,
        "customer_failed_tx_count": history.failed_transaction_count if history else 0,
        "device_age_days": max((event_time - device_first_seen).days, 0) if device_first_seen else 0,
        "dispute_ratio": customer_dispute_count / max(customer_tx_count, 1),
        "refund_ratio": customer_refund_count / max(customer_tx_count, 1),
        "has_device": int(transaction.device_id is not None),
        "is_new_device": int(device_first_seen is not None and event_time - device_first_seen <= timedelta(days=7)),
        "currency": transaction.currency,
        "status": transaction.status,
        "payment_method": _payment_method(transaction),
        "merchant_category": transaction.merchant.category if transaction.merchant else "unknown",
        "customer_country": customer_country,
        "merchant_country": merchant_country,
        "transaction_hour_bucket": _hour_bucket(event_time),
        "transaction_day_of_week": "weekend" if event_time.weekday() >= 5 else "weekday",
        "location_match": "match" if customer_country == merchant_country else "mismatch",
    }


def build_training_frame(db: Session) -> pd.DataFrame:
    """Build a synthetic training frame from database rows and real dispute labels."""
    disputes = db.query(Dispute).all()
    disputed_transaction_ids = {dispute.transaction_id for dispute in disputes}
    transactions = (
        db.query(Transaction)
        .options(joinedload(Transaction.customer), joinedload(Transaction.merchant))
        .order_by(Transaction.transaction_id)
        .all()
    )
    customer_history = _build_customer_history(transactions, disputes)
    rows = []
    for transaction in transactions:
        row = transaction_to_feature_row(transaction, customer_history)
        row[TARGET_COLUMN] = int(transaction.id in disputed_transaction_ids)
        rows.append(row)
    if not rows:
        raise ValueError("No transactions available for ML training")
    return pd.DataFrame(rows, columns=[*FEATURE_COLUMNS, TARGET_COLUMN])
