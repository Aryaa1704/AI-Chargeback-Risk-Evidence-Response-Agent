"""Device domain model."""

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import IdTimestampMixin


class Device(IdTimestampMixin, Base):
    """Synthetic customer device metadata used by later risk features."""

    __tablename__ = "devices"
    __table_args__ = (Index("ix_devices_customer_id", "customer_id"), Index("ix_devices_fingerprint", "fingerprint"))

    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    customer = relationship("Customer", back_populates="devices")
    transactions = relationship("Transaction", back_populates="device")
