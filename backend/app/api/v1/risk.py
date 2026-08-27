"""Risk prediction, summary, and persisted model metadata endpoints."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.ml.features import FEATURE_COLUMNS
from app.ml.prediction import predict_risk
from app.models.risk_prediction import RiskPrediction
from app.models.transaction import Transaction
from app.schemas.api import DashboardAnalyticsResponse, DashboardKpisResponse, ModelInfoResponse, ModelMetricsResponse, RecentHighRiskCaseResponse, RiskDistributionPointResponse, RiskPredictRequest, RiskPredictResponse, RiskScoreBucketResponse, RiskSummaryResponse, TransactionVolumePointResponse

router = APIRouter(prefix="/risk", tags=["risk"])
model_router = APIRouter(prefix="/model", tags=["model"])


def _artifact_payload(settings: Settings, suffix: str) -> dict[str, Any]:
    import os
    base = Path("/workspaces/AI-Chargeback-Risk-Evidence-Response-Agent/backend/artifacts/models/chargeback-risk-v1")
    path = Path(str(base) + suffix)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model metadata artifact is invalid") from exc


@router.post("/predict", response_model=RiskPredictResponse, status_code=status.HTTP_201_CREATED, summary="Predict risk and store an audit record")
def predict(
    payload: RiskPredictRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RiskPredictResponse:
    """Run the persisted ML model only; the result is a human-review risk assessment, not a financial action."""
    transaction = db.scalar(select(Transaction).where(Transaction.transaction_id == payload.transaction_id))
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    try:
        result = predict_risk(payload.model_dump(exclude={"transaction_id"}), settings=settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Risk model artifact is unavailable; train the model first") from exc
    # Persist only model-derived factors returned by the ML pipeline so later evidence
    # packages can cite the exact factors used for this audited prediction.
    record = RiskPrediction(transaction_id=transaction.id, model_version=result.model_version, risk_score=Decimal(str(result.risk_score / 100)), risk_band=result.risk_level, explanation=json.dumps([factor.__dict__ for factor in result.model_derived_risk_factors]))
    db.add(record)
    db.commit()
    db.refresh(record)
    return RiskPredictResponse(prediction_id=record.id, transaction_id=transaction.transaction_id, probability=result.probability, risk_score=result.risk_score, risk_level=result.risk_level, model_version=result.model_version, model_derived_risk_factors=[factor.__dict__ for factor in result.model_derived_risk_factors])


def _metrics_response(settings: Settings) -> ModelMetricsResponse:
    payload = _artifact_payload(settings, ".evaluation.json")
    return ModelMetricsResponse(model_version=payload["model_version"], model_type=payload["model_type"], dataset_version=payload["dataset_version"], evaluated_at=payload["evaluated_at"], metrics=payload["metrics"])


def _score_bucket(score_percent: float) -> tuple[int, int]:
    start = min(int(score_percent // 10) * 10, 90)
    return start, start + 10


@router.get("/dashboard", response_model=DashboardAnalyticsResponse, summary="Get live risk operations dashboard analytics")
def risk_dashboard(db: Annotated[Session, Depends(get_db)], settings: Annotated[Settings, Depends(get_settings)]) -> DashboardAnalyticsResponse:
    """Return presentation dashboard data from DB aggregates and persisted held-out metrics only."""
    total_transactions = db.scalar(select(func.count()).select_from(Transaction)) or 0
    total_predictions = db.scalar(select(func.count()).select_from(RiskPrediction)) or 0
    average = db.scalar(select(func.avg(RiskPrediction.risk_score)))
    grouped = db.execute(select(RiskPrediction.risk_band, func.count()).group_by(RiskPrediction.risk_band)).all()
    risk_counts = {band: int(count) for band, count in grouped}
    histogram_counts = {(start, start + 10): 0 for start in range(0, 100, 10)}
    for (score,) in db.execute(select(RiskPrediction.risk_score)).all():
        bucket = _score_bucket(float(score) * 100)
        histogram_counts[bucket] += 1
    trend_rows = db.execute(select(func.date(Transaction.created_at), func.count()).group_by(func.date(Transaction.created_at)).order_by(func.date(Transaction.created_at))).all()
    recent_rows = db.execute(
        select(RiskPrediction, Transaction)
        .join(Transaction, RiskPrediction.transaction_id == Transaction.id)
        .where(RiskPrediction.risk_band == "HIGH")
        .order_by(RiskPrediction.created_at.desc())
        .limit(10)
    ).all()
    return DashboardAnalyticsResponse(
        generated_at=datetime.now(UTC),
        synthetic_data=True,
        kpis=DashboardKpisResponse(
            total_transactions=total_transactions,
            high_risk=risk_counts.get("HIGH", 0),
            medium_risk=risk_counts.get("MEDIUM", 0),
            predicted_chargebacks=total_predictions,
            average_risk_score=float(average * 100) if average is not None else None,
        ),
        risk_distribution=[RiskDistributionPointResponse(risk_level=band, count=count) for band, count in sorted(risk_counts.items())],
        risk_score_histogram=[RiskScoreBucketResponse(bucket_start=start, bucket_end=end, count=count) for (start, end), count in histogram_counts.items()],
        transaction_volume_trend=[TransactionVolumePointResponse(date=str(day), count=int(count)) for day, count in trend_rows],
        model_metrics=_metrics_response(settings),
        recent_high_risk_cases=[RecentHighRiskCaseResponse(transaction_id=txn.transaction_id, risk_score=float(pred.risk_score) * 100, risk_level=pred.risk_band, model_version=pred.model_version, predicted_at=pred.created_at, amount=txn.amount, currency=txn.currency, status=txn.status) for pred, txn in recent_rows],
    )


@router.get("/summary", response_model=RiskSummaryResponse, summary="Get database-derived risk summary")
def risk_summary(db: Annotated[Session, Depends(get_db)]) -> RiskSummaryResponse:
    """Return aggregate counts calculated from stored transactions and prediction audit records."""
    total_transactions = db.scalar(select(func.count()).select_from(Transaction)) or 0
    total_predictions = db.scalar(select(func.count()).select_from(RiskPrediction)) or 0
    average = db.scalar(select(func.avg(RiskPrediction.risk_score)))
    grouped = db.execute(select(RiskPrediction.risk_band, func.count()).group_by(RiskPrediction.risk_band)).all()
    return RiskSummaryResponse(total_transactions=total_transactions, total_predictions=total_predictions, risk_level_counts={band: count for band, count in grouped}, average_risk_score=float(average * 100) if average is not None else None)


@model_router.get("/metrics", response_model=ModelMetricsResponse, summary="Get actual held-out evaluation metrics")
def model_metrics(settings: Annotated[Settings, Depends(get_settings)]) -> ModelMetricsResponse:
    """Expose the persisted Phase 4 evaluation JSON, never hard-coded performance values."""
    return _metrics_response(settings)


@model_router.get("/info", response_model=ModelInfoResponse, summary="Get persisted model metadata")
def model_info(settings: Annotated[Settings, Depends(get_settings)]) -> ModelInfoResponse:
    """Expose safe model registry metadata without returning model internals or artifact contents."""
    payload = _artifact_payload(settings, ".metadata.json")
    return ModelInfoResponse(model_version=payload["model_version"], model_type=payload["model_type"], dataset_version=payload["dataset_version"], feature_count=len(payload.get("feature_list", FEATURE_COLUMNS)), selection_criterion=payload["selection_criterion"], held_out_test_policy=payload["held_out_test_policy"])
