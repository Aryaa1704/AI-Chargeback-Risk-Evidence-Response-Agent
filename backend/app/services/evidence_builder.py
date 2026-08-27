"""Deterministic evidence construction from verified database records only."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.risk_case import EvidenceItem, RiskCase
from app.models.transaction import Transaction

EVIDENCE_UNAVAILABLE = "Evidence unavailable"
VERIFIED_DATABASE_FACT = "VERIFIED_DATABASE_FACT"
EVIDENCE_UNAVAILABLE_STATUS = "EVIDENCE_UNAVAILABLE"


def _fact(evidence_type: str, source: str, source_id: str, factual_content: str) -> dict[str, str]:
    return {"evidence_type": evidence_type, "source": source, "source_id": source_id, "factual_content": factual_content, "verification_status": VERIFIED_DATABASE_FACT}


def _unavailable(evidence_type: str, source: str) -> dict[str, str]:
    return {"evidence_type": evidence_type, "source": source, "source_id": f"unavailable:{source}", "factual_content": EVIDENCE_UNAVAILABLE, "verification_status": EVIDENCE_UNAVAILABLE_STATUS}


def build_evidence(case: RiskCase, db: Session) -> list[EvidenceItem]:
    """Persist deterministic evidence derived exclusively from records linked to a case."""
    transaction = db.scalar(
        select(Transaction)
        .options(joinedload(Transaction.customer), joinedload(Transaction.merchant), joinedload(Transaction.device), joinedload(Transaction.disputes))
        .where(Transaction.id == case.transaction_id)
    )
    if transaction is None:  # Defensive guard for a database altered outside this application.
        return []

    facts: list[dict[str, str]] = [
        _fact("transaction", "transactions", transaction.id, f"Transaction {transaction.transaction_id}: amount={transaction.amount} {transaction.currency}; status={transaction.status}."),
        _fact("customer", "customers", transaction.customer.id, f"Customer {transaction.customer.id}: country={transaction.customer.country or EVIDENCE_UNAVAILABLE}."),
        _fact("merchant", "merchants", transaction.merchant.id, f"Merchant {transaction.merchant.id}: category={transaction.merchant.category}; country={transaction.merchant.country}."),
        _fact("risk_prediction", "risk_predictions", case.prediction_id, f"ML prediction {case.prediction_id}: risk_score={case.risk_score}; risk_level={case.risk_level}; prediction={case.prediction}."),
    ]
    if transaction.device is None:
        facts.append(_unavailable("device", "devices"))
    else:
        facts.append(_fact("device", "devices", transaction.device.id, f"Device {transaction.device.id}: fingerprint={transaction.device.fingerprint}; ip_address={transaction.device.ip_address or EVIDENCE_UNAVAILABLE}."))
    disputes: Iterable = transaction.disputes
    if not transaction.disputes:
        facts.append(_unavailable("dispute", "disputes"))
    else:
        for dispute in disputes:
            facts.append(_fact("dispute", "disputes", dispute.id, f"Dispute {dispute.id}: reason_code={dispute.reason_code}; status={dispute.status}; evidence_summary={dispute.evidence_summary or EVIDENCE_UNAVAILABLE}."))

    items = [EvidenceItem(risk_case_id=case.id, **fact) for fact in facts]
    db.add_all(items)
    return items
