"""Risk prediction domain model."""

from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import IdTimestampMixin


class RiskPrediction(IdTimestampMixin, Base):
    """Stored quantitative risk prediction produced by a later ML pipeline."""

    __tablename__ = "risk_predictions"
    __table_args__ = (
        Index("ix_risk_predictions_transaction_id", "transaction_id"),
        Index("ix_risk_predictions_model_version", "model_version"),
    )

    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    risk_band: Mapped[str] = mapped_column(String(20), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    transaction = relationship("Transaction", back_populates="risk_predictions")
