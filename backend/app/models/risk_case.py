"""Risk investigation case, evidence, and audit-history ORM models."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import IdTimestampMixin, new_uuid


class RiskCase(IdTimestampMixin, Base):
    """A human-reviewed investigation created from an audited ML prediction."""

    __tablename__ = "risk_cases"
    __table_args__ = (
        Index("ix_risk_cases_case_id", "case_id"),
        Index("ix_risk_cases_transaction_id", "transaction_id"),
        Index("ix_risk_cases_status", "status"),
    )

    case_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, default=lambda: f"case_{new_uuid()}")
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    prediction_id: Mapped[str] = mapped_column(ForeignKey("risk_predictions.id"), nullable=False)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    prediction: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="NEW")
    assigned_reviewer: Mapped[str | None] = mapped_column(String(200), nullable=True)

    transaction = relationship("Transaction", back_populates="risk_cases")
    prediction_record = relationship("RiskPrediction")
    evidence_items = relationship("EvidenceItem", back_populates="risk_case", cascade="all, delete-orphan")
    history_entries = relationship("RiskCaseHistory", back_populates="risk_case", cascade="all, delete-orphan")
    investigations = relationship("AgentInvestigation", back_populates="risk_case", cascade="all, delete-orphan")
    evidence_packages = relationship("EvidencePackage", back_populates="risk_case", cascade="all, delete-orphan")
    recommendations = relationship("CaseRecommendation", back_populates="risk_case", cascade="all, delete-orphan")


class EvidenceItem(IdTimestampMixin, Base):
    """A database-grounded fact or explicitly unavailable evidence category."""

    __tablename__ = "evidence_items"
    __table_args__ = (Index("ix_evidence_items_risk_case_id", "risk_case_id"),)

    risk_case_id: Mapped[str] = mapped_column(ForeignKey("risk_cases.id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False)
    factual_content: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False)

    risk_case = relationship("RiskCase", back_populates="evidence_items")


class RiskCaseHistory(IdTimestampMixin, Base):
    """Append-only audit history for case status and reviewer assignments."""

    __tablename__ = "risk_case_history"
    __table_args__ = (Index("ix_risk_case_history_risk_case_id", "risk_case_id"),)

    risk_case_id: Mapped[str] = mapped_column(ForeignKey("risk_cases.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    assigned_reviewer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    risk_case = relationship("RiskCase", back_populates="history_entries")


class AgentInvestigation(IdTimestampMixin, Base):
    """Auditable Gemini investigation output and controlled tool-call trace."""

    __tablename__ = "agent_investigations"
    __table_args__ = (Index("ix_agent_investigations_risk_case_id", "risk_case_id"),)

    risk_case_id: Mapped[str] = mapped_column(ForeignKey("risk_cases.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    tool_calls_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_references_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)

    risk_case = relationship("RiskCase", back_populates="investigations")


class EvidencePackage(IdTimestampMixin, Base):
    """An immutable, versioned reviewer package assembled from verified facts."""

    __tablename__ = "evidence_packages"
    __table_args__ = (Index("ix_evidence_packages_risk_case_id", "risk_case_id"),)

    risk_case_id: Mapped[str] = mapped_column(ForeignKey("risk_cases.id"), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_references_json: Mapped[str] = mapped_column(Text, nullable=False)

    risk_case = relationship("RiskCase", back_populates="evidence_packages")


class CaseRecommendation(IdTimestampMixin, Base):
    """A non-executing, versioned recommendation for explicit human approval."""

    __tablename__ = "case_recommendations"
    __table_args__ = (Index("ix_case_recommendations_risk_case_id", "risk_case_id"),)

    risk_case_id: Mapped[str] = mapped_column(ForeignKey("risk_cases.id"), nullable=False)
    evidence_package_id: Mapped[str] = mapped_column(ForeignKey("evidence_packages.id"), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    requires_human_approval: Mapped[bool] = mapped_column(nullable=False, default=True)

    risk_case = relationship("RiskCase", back_populates="recommendations")
    evidence_package = relationship("EvidencePackage")
