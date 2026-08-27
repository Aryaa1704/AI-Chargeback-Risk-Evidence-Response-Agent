"""Pydantic contracts for the documented Phase 5 REST API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SafeId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]
CountryCode = Annotated[str, StringConstraints(to_upper=True, min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")]


class RiskPredictRequest(BaseModel):
    """Model-ready transaction features, supplied with an existing transaction ID for audit."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"transaction_id": "synthetic_phase2_txn_0000", "amount": 450.0, "amount_deviation": 2.1, "transaction_velocity_24h": 3, "transaction_velocity_7d": 12, "customer_account_age_days": 180, "customer_dispute_count": 1, "customer_refund_count": 0, "customer_failed_tx_count": 1, "device_age_days": 21, "dispute_ratio": 0.08, "refund_ratio": 0.0, "has_device": 1, "is_new_device": 0, "currency": "INR", "status": "captured", "payment_method": "card", "merchant_category": "electronics", "customer_country": "IN", "merchant_country": "IN", "transaction_hour_bucket": "afternoon", "transaction_day_of_week": "Friday", "location_match": "match"}]})
    transaction_id: SafeId
    amount: float = Field(ge=0, le=10_000_000)
    amount_deviation: float = Field(ge=0, le=1_000_000)
    transaction_velocity_24h: int = Field(ge=0, le=100_000)
    transaction_velocity_7d: int = Field(ge=0, le=1_000_000)
    customer_account_age_days: int = Field(ge=0, le=100_000)
    customer_dispute_count: int = Field(ge=0, le=100_000)
    customer_refund_count: int = Field(ge=0, le=100_000)
    customer_failed_tx_count: int = Field(ge=0, le=100_000)
    device_age_days: int = Field(ge=0, le=100_000)
    dispute_ratio: float = Field(ge=0, le=1)
    refund_ratio: float = Field(ge=0, le=1)
    has_device: Literal[0, 1]
    is_new_device: Literal[0, 1]
    currency: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=3, to_upper=True)]
    status: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    payment_method: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    merchant_category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    customer_country: CountryCode
    merchant_country: CountryCode
    transaction_hour_bucket: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    transaction_day_of_week: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    location_match: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class RiskFactorResponse(BaseModel):
    transformed_feature: str
    source_feature: str
    feature_value: float
    contribution: float
    attribution_method: str


class RiskPredictResponse(BaseModel):
    prediction_id: str
    transaction_id: str
    probability: float
    risk_score: int
    risk_level: str
    model_version: str
    model_derived_risk_factors: list[RiskFactorResponse]


class TransactionListItem(BaseModel):
    transaction_id: str
    customer_id: str
    merchant_id: str
    amount: Decimal
    currency: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PageResponse(BaseModel):
    items: list[TransactionListItem]
    page: int
    page_size: int
    total: int


TransactionSortField = Literal["created_at", "amount", "status", "currency"]
SortDirection = Literal["asc", "desc"]


class TransactionDetailResponse(TransactionListItem):
    id: str
    device_id: str | None
    updated_at: datetime
    customer_email: str
    customer_name: str
    merchant_name: str
    merchant_category: str
    disputes_count: int


class CustomerHistoryResponse(BaseModel):
    customer_id: str
    transaction_count: int
    total_amount: Decimal
    average_amount: Decimal
    disputed_transaction_count: int
    transactions: list[TransactionListItem]


class DisputeResponse(BaseModel):
    id: str
    transaction_id: str
    reason_code: str
    status: str
    evidence_summary: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskSummaryResponse(BaseModel):
    total_transactions: int
    total_predictions: int
    risk_level_counts: dict[str, int]
    average_risk_score: float | None


class ModelMetricsResponse(BaseModel):
    model_version: str
    model_type: str
    dataset_version: str
    evaluated_at: datetime
    metrics: dict[str, object]


class DashboardKpisResponse(BaseModel):
    total_transactions: int
    high_risk: int
    medium_risk: int
    predicted_chargebacks: int
    average_risk_score: float | None


class RiskDistributionPointResponse(BaseModel):
    risk_level: str
    count: int


class RiskScoreBucketResponse(BaseModel):
    bucket_start: int
    bucket_end: int
    count: int


class TransactionVolumePointResponse(BaseModel):
    date: str
    count: int


class RecentHighRiskCaseResponse(BaseModel):
    transaction_id: str
    risk_score: float
    risk_level: str
    model_version: str
    predicted_at: datetime
    amount: Decimal
    currency: str
    status: str


class DashboardAnalyticsResponse(BaseModel):
    generated_at: datetime
    synthetic_data: Literal[True]
    kpis: DashboardKpisResponse
    risk_distribution: list[RiskDistributionPointResponse]
    risk_score_histogram: list[RiskScoreBucketResponse]
    transaction_volume_trend: list[TransactionVolumePointResponse]
    model_metrics: ModelMetricsResponse
    recent_high_risk_cases: list[RecentHighRiskCaseResponse]


class ModelInfoResponse(BaseModel):
    model_version: str
    model_type: str
    dataset_version: str
    feature_count: int
    selection_criterion: str
    held_out_test_policy: str


CaseStatus = Literal["NEW", "INVESTIGATING", "READY_FOR_REVIEW", "APPROVED", "REJECTED", "CLOSED"]


class RiskCaseCreateRequest(BaseModel):
    """Create a human-review case from a transaction's latest audited ML prediction."""

    transaction_id: SafeId
    assigned_reviewer: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] = None


class RiskCaseUpdateRequest(BaseModel):
    """Update assignment and/or advance a case through its permitted workflow."""

    status: CaseStatus | None = None
    assigned_reviewer: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] = None


class EvidenceItemResponse(BaseModel):
    id: str
    evidence_type: str
    source: str
    source_id: str
    factual_content: str
    retrieved_at: datetime
    verification_status: str

    model_config = ConfigDict(from_attributes=True)


class RiskCaseHistoryResponse(BaseModel):
    id: str
    event_type: str
    from_status: str | None
    to_status: str | None
    assigned_reviewer: str | None
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentToolCallResponse(BaseModel):
    tool_name: str
    arguments: dict[str, object]
    evidence_references: list[str]


class PersistedInvestigationResponse(BaseModel):
    model_name: str
    tool_calls: list[AgentToolCallResponse]
    evidence_references: list[str]
    result: InvestigationResponse
    created_at: datetime


class RiskCaseResponse(BaseModel):
    case_id: str
    transaction_id: str
    prediction_id: str
    risk_score: Decimal
    risk_level: str
    prediction: str
    status: CaseStatus
    assigned_reviewer: str | None
    created_at: datetime
    updated_at: datetime
    history: list[RiskCaseHistoryResponse]
    latest_investigation: PersistedInvestigationResponse | None = None
    latest_evidence_package: EvidencePackageResponse | None = None
    latest_recommendation: RecommendationResponse | None = None


class InvestigationResponse(BaseModel):
    """Validated, human-review-only investigation output."""

    risk_summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000)]
    evidence_references: list[SafeId] = Field(min_length=1, max_length=100)
    risk_factors: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000)]] = Field(min_length=1, max_length=30)
    recommendation: Literal["MANUAL_REVIEW", "GATHER_MORE_EVIDENCE", "CONTEST_DISPUTE"]
    confidence: float = Field(ge=0, le=1)
    requires_human_review: Literal[True]


RecommendationCategory = Literal[
    "MANUAL_REVIEW",
    "MONITOR",
    "REQUEST_ADDITIONAL_VERIFICATION",
    "PRIORITIZE_CHARGEBACK_RESPONSE",
    "PREPARE_EVIDENCE_PACKAGE",
    "LOW_PRIORITY_REVIEW",
]


class EvidenceClaimResponse(BaseModel):
    content: str
    source: str
    source_id: str


class EvidencePackageResponse(BaseModel):
    case_id: str
    package_id: str
    version: int
    generated_at: datetime
    transaction_evidence: list[EvidenceClaimResponse]
    customer_history: list[EvidenceClaimResponse]
    previous_disputes: list[EvidenceClaimResponse]
    risk_analysis: list[EvidenceClaimResponse]
    recommended_response: RecommendationCategory


class RecommendationResponse(BaseModel):
    case_id: str
    recommendation_id: str
    evidence_package_id: str
    version: int
    generated_at: datetime
    category: RecommendationCategory
    rationale: str
    human_approval_required: Literal[True]
    financial_action_executed: Literal[False]
