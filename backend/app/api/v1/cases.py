"""Human-review risk investigation case endpoints; no LLM or financial actions."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.risk_case import AgentInvestigation, EvidencePackage, RiskCase, RiskCaseHistory
from app.models.risk_prediction import RiskPrediction
from app.models.transaction import Transaction
from app.schemas.api import EvidenceItemResponse, EvidencePackageResponse, InvestigationResponse, PersistedInvestigationResponse, RecommendationResponse, RiskCaseCreateRequest, RiskCaseResponse, RiskCaseUpdateRequest, SafeId
from app.services.evidence_builder import build_evidence
from app.services.gemini_agent import GeminiAgentError, GeminiInvestigationAgent, serialize_investigation
from app.services.response_builder import build_evidence_package, build_recommendation, evidence_package_response, recommendation_response
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/cases", tags=["risk cases"])

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "NEW": {"INVESTIGATING"},
    "INVESTIGATING": {"READY_FOR_REVIEW"},
    "READY_FOR_REVIEW": {"APPROVED", "REJECTED"},
    "APPROVED": {"CLOSED"},
    "REJECTED": {"CLOSED"},
    "CLOSED": set(),
}


def _case_or_404(db: Session, case_id: str) -> RiskCase:
    case = db.scalar(select(RiskCase).options(selectinload(RiskCase.history_entries), selectinload(RiskCase.investigations), selectinload(RiskCase.evidence_packages), selectinload(RiskCase.recommendations)).where(RiskCase.case_id == case_id))
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk case not found")
    return case


def _latest_investigation(case: RiskCase) -> PersistedInvestigationResponse | None:
    latest = max(case.investigations, key=lambda row: row.created_at, default=None)
    if latest is None:
        return None
    return PersistedInvestigationResponse(
        model_name=latest.model_name,
        tool_calls=json.loads(latest.tool_calls_json),
        evidence_references=json.loads(latest.evidence_references_json),
        result=InvestigationResponse.model_validate_json(latest.result_json),
        created_at=latest.created_at,
    )


def _response(case: RiskCase) -> RiskCaseResponse:
    latest_package = max(case.evidence_packages, key=lambda row: row.version, default=None)
    latest_recommendation = max(case.recommendations, key=lambda row: row.version, default=None)
    return RiskCaseResponse(
        case_id=case.case_id, transaction_id=case.transaction.transaction_id, prediction_id=case.prediction_id,
        risk_score=case.risk_score, risk_level=case.risk_level, prediction=case.prediction, status=case.status,
        assigned_reviewer=case.assigned_reviewer, created_at=case.created_at, updated_at=case.updated_at,
        history=sorted(case.history_entries, key=lambda entry: entry.created_at),
        latest_investigation=_latest_investigation(case),
        latest_evidence_package=evidence_package_response(case, latest_package) if latest_package else None,
        latest_recommendation=recommendation_response(case, latest_recommendation) if latest_recommendation else None,
    )


@router.post("", response_model=RiskCaseResponse, status_code=status.HTTP_201_CREATED, summary="Create an investigation case from an audited ML prediction")
def create_case(payload: RiskCaseCreateRequest, db: Annotated[Session, Depends(get_db)]) -> RiskCaseResponse:
    transaction = db.scalar(select(Transaction).where(Transaction.transaction_id == payload.transaction_id))
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    prediction = db.scalar(select(RiskPrediction).where(RiskPrediction.transaction_id == transaction.id).order_by(RiskPrediction.created_at.desc()))
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An audited risk prediction is required before creating a risk case")
    existing_case = db.scalar(select(RiskCase).where(RiskCase.transaction_id == transaction.id, RiskCase.prediction_id == prediction.id).order_by(RiskCase.created_at.desc()))
    if existing_case is not None:
        return _response(_case_or_404(db, existing_case.case_id))
    case = RiskCase(transaction_id=transaction.id, prediction_id=prediction.id, risk_score=prediction.risk_score, risk_level=prediction.risk_band, prediction="CHARGEBACK_RISK", assigned_reviewer=payload.assigned_reviewer)
    db.add(case)
    db.flush()
    db.add(RiskCaseHistory(risk_case_id=case.id, event_type="CASE_CREATED", to_status=case.status, assigned_reviewer=case.assigned_reviewer))
    build_evidence(case, db)
    db.commit()
    return _response(_case_or_404(db, case.case_id))


@router.get("/{case_id}", response_model=RiskCaseResponse, summary="Get a risk investigation case and audit history")
def get_case(case_id: SafeId, db: Annotated[Session, Depends(get_db)]) -> RiskCaseResponse:
    return _response(_case_or_404(db, case_id))


@router.patch("/{case_id}", response_model=RiskCaseResponse, summary="Update reviewer or make a validated case-status transition")
def update_case(case_id: SafeId, payload: RiskCaseUpdateRequest, db: Annotated[Session, Depends(get_db)]) -> RiskCaseResponse:
    case = _case_or_404(db, case_id)
    status_changed = payload.status is not None and payload.status != case.status
    reviewer_changed = "assigned_reviewer" in payload.model_fields_set and payload.assigned_reviewer != case.assigned_reviewer
    if not status_changed and not reviewer_changed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide a changed status or assigned_reviewer")
    if status_changed and payload.status not in ALLOWED_STATUS_TRANSITIONS[case.status]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Invalid case status transition: {case.status} to {payload.status}")
    previous_status = case.status
    if status_changed:
        case.status = payload.status
    if reviewer_changed:
        case.assigned_reviewer = payload.assigned_reviewer
    db.add(RiskCaseHistory(risk_case_id=case.id, event_type="STATUS_CHANGED" if status_changed else "REVIEWER_ASSIGNED", from_status=previous_status if status_changed else None, to_status=payload.status if status_changed else None, assigned_reviewer=case.assigned_reviewer))
    db.commit()
    return _response(_case_or_404(db, case.case_id))


@router.get("/{case_id}/evidence", response_model=list[EvidenceItemResponse], summary="List traceable, database-grounded evidence for a case")
def list_evidence(case_id: SafeId, db: Annotated[Session, Depends(get_db)]) -> list[EvidenceItemResponse]:
    case = _case_or_404(db, case_id)
    return [EvidenceItemResponse.model_validate(item) for item in sorted(case.evidence_items, key=lambda item: (item.retrieved_at, item.id))]


@router.post("/{case_id}/investigate", response_model=InvestigationResponse, summary="Run a controlled Gemini investigation for a risk case")
def investigate_case(
    case_id: SafeId,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InvestigationResponse:
    """Invoke Gemini only as a bounded evidence synthesizer; ML prediction remains independent."""
    case = _case_or_404(db, case_id)
    if case.status != "NEW":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Investigation can only start from NEW status")
    try:
        result, tool_trace = GeminiInvestigationAgent(settings).investigate(case, db)
    except GeminiAgentError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    tool_calls_json, evidence_references_json, result_json = serialize_investigation(result, tool_trace)
    db.add(AgentInvestigation(
        risk_case_id=case.id,
        model_name=settings.gemini_model,
        tool_calls_json=tool_calls_json,
        evidence_references_json=evidence_references_json,
        result_json=result_json,
    ))
    db.add(RiskCaseHistory(risk_case_id=case.id, event_type="GEMINI_INVESTIGATION_COMPLETED"))
    case.status = "INVESTIGATING"
    db.add(RiskCaseHistory(risk_case_id=case.id, event_type="STATUS_CHANGED", from_status="NEW", to_status="INVESTIGATING", assigned_reviewer=case.assigned_reviewer))
    db.commit()
    return result


@router.post("/{case_id}/evidence", response_model=EvidencePackageResponse, status_code=status.HTTP_201_CREATED, summary="Generate a versioned, database-traceable evidence package")
def generate_evidence_package(case_id: SafeId, db: Annotated[Session, Depends(get_db)]) -> EvidencePackageResponse:
    """Create a fresh reviewer package from DB facts; regeneration is allowed while investigating."""
    case = _case_or_404(db, case_id)
    if case.status != "INVESTIGATING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Evidence packages can only be generated while a case is INVESTIGATING")
    try:
        package = build_evidence_package(case, db)
        db.flush()
        db.add(RiskCaseHistory(risk_case_id=case.id, event_type="EVIDENCE_PACKAGE_GENERATED"))
        db.commit()
        db.refresh(package)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return evidence_package_response(case, package)


@router.post("/{case_id}/recommendation", response_model=RecommendationResponse, status_code=status.HTTP_201_CREATED, summary="Generate a bounded recommendation requiring human approval")
def generate_recommendation(case_id: SafeId, db: Annotated[Session, Depends(get_db)]) -> RecommendationResponse:
    """Persist a recommendation only; this endpoint has no payment or account action path."""
    case = _case_or_404(db, case_id)
    if case.status != "INVESTIGATING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Recommendations can only be generated while a case is INVESTIGATING")
    package = db.scalar(
        select(EvidencePackage).where(EvidencePackage.risk_case_id == case.id).order_by(EvidencePackage.version.desc())
    )
    if package is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Generate an evidence package before requesting a recommendation")
    recommendation = build_recommendation(case, package, db)
    db.flush()
    db.add(RiskCaseHistory(risk_case_id=case.id, event_type="RECOMMENDATION_GENERATED"))
    db.commit()
    db.refresh(recommendation)
    return recommendation_response(case, recommendation)
