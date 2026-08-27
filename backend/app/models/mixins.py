"""Reusable ORM column mixins."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


def new_uuid() -> str:
    """Generate a string-safe UUID primary key."""
    return str(uuid4())


class IdTimestampMixin:
    """String UUID primary key plus created/updated timestamps."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )
