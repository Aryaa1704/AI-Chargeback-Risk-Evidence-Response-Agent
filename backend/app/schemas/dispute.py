"""Dispute Pydantic schemas."""

from app.schemas.common import TimestampedSchema


class DisputeRead(TimestampedSchema):
    """Read schema for disputes."""

    transaction_id: str
    customer_id: str
    reason_code: str
    status: str
    evidence_summary: str | None = None
