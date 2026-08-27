"""Dispute domain model."""

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import IdTimestampMixin


class Dispute(IdTimestampMixin, Base):
    """Synthetic chargeback/dispute record for a transaction."""

    __tablename__ = "disputes"
    __table_args__ = (Index("ix_disputes_transaction_id", "transaction_id"), Index("ix_disputes_customer_id", "customer_id"))

    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    transaction = relationship("Transaction", back_populates="disputes")
