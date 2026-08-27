"""Groq-powered investigation agent."""
import json, logging, time, os, re
from typing import Any
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.config import Settings
from app.models.dispute import Dispute
from app.models.risk_case import EvidenceItem, RiskCase
from app.models.transaction import Transaction
from app.schemas.api import InvestigationResponse

logger = logging.getLogger("app.gemini")

class GeminiAgentError(Exception): pass
class GeminiAgentUnavailable(GeminiAgentError): pass
class GeminiAgentResponseInvalid(GeminiAgentError): pass

class GeminiInvestigationAgent:
    def __init__(self, settings: Settings, client: Any | None = None, types_module: Any | None = None) -> None:
        self.settings = settings
        from dotenv import load_dotenv
        load_dotenv()
        self.groq_key = os.getenv("GROQ_API_KEY", "")
        if not self.groq_key:
            raise GeminiAgentUnavailable("GROQ_API_KEY not configured")
        from groq import Groq
        self.client = Groq(api_key=self.groq_key)

    def investigate(self, case: RiskCase, db: Session) -> tuple[InvestigationResponse, list[dict[str, Any]]]:
        transaction = db.scalar(select(Transaction).options(
            joinedload(Transaction.customer), joinedload(Transaction.merchant)
        ).where(Transaction.id == case.transaction_id))
        if not transaction:
            raise GeminiAgentResponseInvalid("Transaction not found")
        evidence_rows = db.scalars(select(EvidenceItem).where(EvidenceItem.risk_case_id == case.id)).all()
        evidence_ids = [r.id for r in evidence_rows]
        disputes = list(db.scalars(select(Dispute).where(Dispute.customer_id == transaction.customer_id)).all())
        
        prompt = f"""You are a chargeback investigation assistant. Output ONLY raw JSON. No thinking tags, no markdown, no explanation.

Transaction: {transaction.transaction_id}
Amount: {transaction.amount} {transaction.currency}
Status: {transaction.status}
Risk Score: {case.risk_score}
Risk Level: {case.risk_level}
Disputes: {len(disputes)}
Evidence IDs: {evidence_ids[:3]}

Output this exact JSON structure with real values:
{{"risk_summary": "Transaction shows medium risk due to amount and dispute history", "evidence_references": {json.dumps(evidence_ids[:3] if evidence_ids else [])}, "risk_factors": ["elevated transaction amount", "prior dispute history"], "recommendation": "MANUAL_REVIEW", "confidence": 0.75, "requires_human_review": true}}"""

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model="groq/compound-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=400
                )
                raw = response.choices[0].message.content.strip()
                # Remove think tags if present
                raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
                raw = raw.replace("```json","").replace("```","").strip()
                # Extract JSON if wrapped in text
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                if match:
                    raw = match.group()
                result = InvestigationResponse.model_validate_json(raw)
                return result, [{"tool_name": "groq_investigation", "arguments": {}, "evidence_references": evidence_ids}]
            except ValidationError as e:
                raise GeminiAgentResponseInvalid(f"Invalid response: {e}")
            except Exception as e:
                logger.warning(f"Groq attempt {attempt+1} failed: {e}")
                if attempt >= 2:
                    raise GeminiAgentUnavailable(f"Groq unavailable: {e}")
                time.sleep(1)
        raise GeminiAgentUnavailable("All attempts failed")

def serialize_investigation(result: InvestigationResponse, tool_trace: list[dict[str, Any]]) -> tuple[str, str, str]:
    return json.dumps(tool_trace), json.dumps(result.evidence_references), result.model_dump_json()
