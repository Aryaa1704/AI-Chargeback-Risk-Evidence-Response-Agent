"""Shared Pydantic schema primitives."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    """Base schema configured for SQLAlchemy object serialization."""

    model_config = ConfigDict(from_attributes=True)


class TimestampedSchema(ORMBase):
    """Common identifier and timestamp fields returned by domain schemas."""

    id: str
    created_at: datetime
    updated_at: datetime
