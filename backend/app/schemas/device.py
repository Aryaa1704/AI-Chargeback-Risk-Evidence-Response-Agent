"""Device Pydantic schemas."""

from app.schemas.common import TimestampedSchema


class DeviceRead(TimestampedSchema):
    """Read schema for devices."""

    customer_id: str
    fingerprint: str
    ip_address: str | None = None
    user_agent: str | None = None
