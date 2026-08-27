"""Customer domain model."""

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import IdTimestampMixin


class Customer(IdTimestampMixin, Base):
    """Synthetic customer involved in transactions and disputes."""

    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_email", "email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)

    transactions = relationship("Transaction", back_populates="customer")
    devices = relationship("Device", back_populates="customer")
