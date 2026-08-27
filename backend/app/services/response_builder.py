"""Build versioned, non-executing response artifacts from database facts only."""

import json
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.dispute import Dispute
from app.models.risk_case import CaseRecommendation, EvidencePackage, RiskCase
from app.models.transaction import Transaction
from app.schemas.api import EvidencePackageResponse, RecommendationCategory, RecommendationResponse
from app.services.evidence_builder import EVIDENCE_UNAVAILABLE


def _claim(content: str, source: str, source_id: str) -> dict[str, str]:
    return {"content": content, "source": source, "source_id": source_id}


def _unavailable(source: str) -> dict[str, str]:
    return _claim(EVIDENCE_UNAVAILABLE, source, f"unavailable:{source}")


def _category(risk_level: str) -> RecommendationCategory:
    return {
        "HIGH": "PRIORITIZE_CHARGEBACK_RESPONSE",
        "MEDIUM": "MANUAL_REVIEW",
        "LOW": "LOW_PRIORITY_REVIEW",
    }.get(risk_level, "MANUAL_REVIEW")


def _next_version(rows: Sequence[EvidencePackage] | Sequence[CaseRecommendation]) -> int:
    return max((row.version for row in rows), default=0) + 1


def build_evidence_package(case: RiskCase, db: Session) -> EvidencePackage:
    """Persist a fresh evidence snapshot, with every claim carrying its DB source."""
    transaction = db.scalar(
        select(Transaction)
        .options(joinedload(Transaction.customer))
        .where(Transaction.id == case.transaction_id)
    )
    if transaction is None:
        raise ValueError("The case transaction is no longer available")

    transaction_evidence = [
        _claim(
            f"Transaction {transaction.transaction_id}: amount={transaction.amount} {transaction.currency}; status={transaction.status}.",
            "transactions",
            transaction.id,
        )
    ]
    customer_rows = db.scalars(
        select(Transaction).where(Transaction.customer_id == transaction.customer_id).order_by(Transaction.created_at.desc())
    ).all()
    total = sum((row.amount for row in customer_rows), Decimal("0"))
    customer_history = [
        _claim(
            f"Customer has {len(customer_rows)} recorded synthetic transactions totaling {total} {transaction.currency}.",
            "transactions",
            ",".join(row.id for row in customer_rows) or f"unavailable:customer:{transaction.customer_id}",
        )
    ] if customer_rows else [_unavailable("transactions")]
    disputes = db.scalars(
        select(Dispute).where(Dispute.customer_id == transaction.customer_id).order_by(Dispute.created_at.desc())
    ).all()
    previous_disputes = [
        _claim(
            f"Dispute {row.id}: reason_code={row.reason_code}; status={row.status}; evidence_summary={row.evidence_summary or EVIDENCE_UNAVAILABLE}.",
            "disputes",
            row.id,
        )
        for row in disputes
    ] or [_unavailable("disputes")]

    risk_analysis = [
        _claim(
            f"ML prediction: risk_score={case.risk_score}; risk_level={case.risk_level}; prediction={case.prediction}.",
            "risk_predictions",
            case.prediction_id,
        )
    ]
    try:
        factors = json.loads(case.prediction_record.explanation or "[]")
    except json.JSONDecodeError:
        factors = []
    if isinstance(factors, list) and factors:
        for factor in factors:
            if isinstance(factor, dict):
                risk_analysis.append(_claim(
                    f"ML factor {factor.get('source_feature', EVIDENCE_UNAVAILABLE)}: transformed_feature={factor.get('transformed_feature', EVIDENCE_UNAVAILABLE)}; feature_value={factor.get('feature_value', EVIDENCE_UNAVAILABLE)}; contribution={factor.get('contribution', EVIDENCE_UNAVAILABLE)}; attribution_method={factor.get('attribution_method', EVIDENCE_UNAVAILABLE)}.",
                    "risk_predictions",
                    case.prediction_id,
                ))
    else:
        risk_analysis.append(_unavailable("risk_prediction_factors"))

    content = {
        "transaction_evidence": transaction_evidence,
        "customer_history": customer_history,
        "previous_disputes": previous_disputes,
        "risk_analysis": risk_analysis,
        "recommended_response": _category(case.risk_level),
    }
    existing = db.scalars(select(EvidencePackage).where(EvidencePackage.risk_case_id == case.id)).all()
    package = EvidencePackage(
        risk_case_id=case.id,
        version=_next_version(existing),
        content_json=json.dumps(content),
        source_references_json=json.dumps([claim["source_id"] for group in content.values() if isinstance(group, list) for claim in group]),
    )
    db.add(package)
    return package


def evidence_package_response(case: RiskCase, package: EvidencePackage) -> EvidencePackageResponse:
    content = json.loads(package.content_json)
    return EvidencePackageResponse(case_id=case.case_id, package_id=package.id, version=package.version, generated_at=package.created_at, **content)


def build_recommendation(case: RiskCase, package: EvidencePackage, db: Session) -> CaseRecommendation:
    """Persist only a bounded, human-approved recommendation; never execute it."""
    category = _category(case.risk_level)
    rationale = f"The independently computed ML risk level is {case.risk_level}; this recommendation is based on evidence package version {package.version} and requires human approval."
    existing = db.scalars(select(CaseRecommendation).where(CaseRecommendation.risk_case_id == case.id)).all()
    recommendation = CaseRecommendation(
        risk_case_id=case.id,
        evidence_package_id=package.id,
        version=_next_version(existing),
        category=category,
        rationale=rationale,
        requires_human_approval=True,
    )
    db.add(recommendation)
    return recommendation


def recommendation_response(case: RiskCase, recommendation: CaseRecommendation) -> RecommendationResponse:
    return RecommendationResponse(
        case_id=case.case_id,
        recommendation_id=recommendation.id,
        evidence_package_id=recommendation.evidence_package_id,
        version=recommendation.version,
        generated_at=recommendation.created_at,
        category=recommendation.category,
        rationale=recommendation.rationale,
        human_approval_required=True,
        financial_action_executed=False,
    )
