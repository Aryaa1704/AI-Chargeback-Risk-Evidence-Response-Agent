"""Transaction domain model."""

from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import IdTimestampMixin


class Transaction(IdTimestampMixin, Base):
    """Synthetic payment transaction record."""

    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_transaction_id", "transaction_id"),
        Index("ix_transactions_customer_id", "customer_id"),
        Index("ix_transactions_merchant_id", "merchant_id"),
    )

    transaction_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)

    customer = relationship("Customer", back_populates="transactions")
    merchant = relationship("Merchant", back_populates="transactions")
    device = relationship("Device", back_populates="transactions")
    disputes = relationship("Dispute", back_populates="transaction")
    risk_predictions = relationship("RiskPrediction", back_populates="transaction")
    risk_cases = relationship("RiskCase", back_populates="transaction")
