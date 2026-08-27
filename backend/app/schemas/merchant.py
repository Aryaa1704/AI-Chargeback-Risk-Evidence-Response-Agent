"""Merchant Pydantic schemas."""

from app.schemas.common import TimestampedSchema


class MerchantRead(TimestampedSchema):
    """Read schema for merchants."""

    name: str
    category: str
    country: str | None = None
