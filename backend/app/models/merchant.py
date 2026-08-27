"""Merchant domain model."""

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import IdTimestampMixin


class Merchant(IdTimestampMixin, Base):
    """Synthetic merchant accepting transactions."""

    __tablename__ = "merchants"
    __table_args__ = (Index("ix_merchants_name", "name"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)

    transactions = relationship("Transaction", back_populates="merchant")
