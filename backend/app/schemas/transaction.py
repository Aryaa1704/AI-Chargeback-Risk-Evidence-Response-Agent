"""Transaction Pydantic schemas."""

from decimal import Decimal

from app.schemas.common import TimestampedSchema


class TransactionRead(TimestampedSchema):
    """Read schema for transactions."""

    transaction_id: str
    customer_id: str
    merchant_id: str
    device_id: str | None = None
    amount: Decimal
    currency: str
    status: str
