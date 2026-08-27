"""Risk prediction Pydantic schemas."""

from decimal import Decimal

from app.schemas.common import TimestampedSchema


class RiskPredictionRead(TimestampedSchema):
    """Read schema for quantitative ML risk predictions."""

    transaction_id: str
    model_version: str
    risk_score: Decimal
    risk_band: str
    explanation: str | None = None
