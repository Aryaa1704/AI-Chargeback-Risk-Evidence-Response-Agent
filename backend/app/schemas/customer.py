"""Customer Pydantic schemas."""

from app.schemas.common import TimestampedSchema


class CustomerRead(TimestampedSchema):
    """Read schema for customers."""

    email: str
    full_name: str
    country: str | None = None
