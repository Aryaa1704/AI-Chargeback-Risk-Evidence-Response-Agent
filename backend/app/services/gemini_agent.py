"""Mock investigation agent — no external API needed."""
import json
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.config import Settings
from app.models.dispute import Dispute
from app.models.risk_case import EvidenceItem, RiskCase
from app.models.transaction import Transaction
from app.schemas.api import InvestigationResponse

class GeminiAgentError(Exception): pass
class GeminiAgentUnavailable(GeminiAgentError): pass
class GeminiAgentResponseInvalid(GeminiAgentError): pass

class GeminiInvestigationAgent:
    def __init__(self, settings: Settings, client: Any | None = None, types_module: Any | None = None) -> None:
        self.settings = settings

    def investigate(self, case: RiskCase, db: Session) -> tuple[InvestigationResponse, list[dict[str, Any]]]:
        transaction = db.scalar(select(Transaction).options(
            joinedload(Transaction.customer), joinedload(Transaction.merchant)
        ).where(Transaction.id == case.transaction_id))
        if not transaction:
            raise GeminiAgentResponseInvalid("Transaction not found")

        evidence_rows = db.scalars(select(EvidenceItem).where(EvidenceItem.risk_case_id == case.id)).all()
        evidence_ids = [r.id for r in evidence_rows]
        disputes = list(db.scalars(select(Dispute).where(Dispute.customer_id == transaction.customer_id)).all())

        risk_level = case.risk_level or "MEDIUM"
        score = case.risk_score or 50

        if risk_level == "HIGH":
            summary = f"Transaction {transaction.transaction_id} shows HIGH risk (score: {score}). Multiple risk factors detected including elevated amount, failed status, and {len(disputes)} prior dispute(s)."
            recommendation = "PRIORITIZE_CHARGEBACK_RESPONSE"
            factors = ["elevated transaction amount", "failed transaction status", "prior dispute history", "cross-border merchant"]
            confidence = 0.88
        elif risk_level == "LOW":
            summary = f"Transaction {transaction.transaction_id} shows LOW risk (score: {score}). No significant risk factors detected."
            recommendation = "LOW_PRIORITY_REVIEW"
            factors = ["normal transaction amount", "clean dispute history"]
            confidence = 0.91
        else:
            summary = f"Transaction {transaction.transaction_id} shows MEDIUM risk (score: {score}). Manual review recommended."
            recommendation = "MANUAL_REVIEW"
            factors = ["moderate transaction amount", "limited dispute history"]
            confidence = 0.75

        result = InvestigationResponse(
            risk_summary=summary,
            evidence_references=evidence_ids[:3],
            risk_factors=factors,
            recommendation=recommendation,
            confidence=confidence,
            requires_human_review=True,
        )
        tool_trace = [{"tool_name": "mock_investigation", "arguments": {}, "evidence_references": evidence_ids}]
        return result, tool_trace

def serialize_investigation(result: InvestigationResponse, tool_trace: list[dict[str, Any]]) -> tuple[str, str, str]:
    return json.dumps(tool_trace), json.dumps(result.evidence_references), result.model_dump_json()
