"""SQLAlchemy models for DPA analysis."""

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dpa_app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    SCORING = "scoring"
    COMPLETED = "completed"
    FAILED = "failed"


class FindingSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingType(str, enum.Enum):
    MISSING_PROVISION = "missing_provision"
    DEVIATION = "deviation"
    SUBPROCESSOR_ISSUE = "subprocessor_issue"
    TRANSFER_MECHANISM_ISSUE = "transfer_mechanism_issue"
    PARTIAL_COMPLIANCE = "partial_compliance"
    COMPLIANT = "compliant"


# ---------------------------------------------------------------------------
# Association table
# ---------------------------------------------------------------------------


class AnalysisMatrix(Base):
    """Association table: which matrices were used for a given analysis."""

    __tablename__ = "analysis_matrices"

    analysis_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dpa_analyses.id", ondelete="CASCADE"), primary_key=True
    )
    matrix_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("requirements_matrices.id"), primary_key=True
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RequirementsMatrix(Base):
    """A regulatory requirements matrix used to evaluate DPAs."""

    __tablename__ = "requirements_matrices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    framework: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(50), default="1.0")
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False)
    content: Mapped[dict] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    analyses: Mapped[list["DPAAnalysis"]] = relationship(
        back_populates="matrices",
        secondary="analysis_matrices",
    )


class DPAAnalysis(Base):
    """A single DPA analysis run."""

    __tablename__ = "dpa_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # File metadata
    file_id: Mapped[str] = mapped_column(String(36))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    file_size_bytes: Mapped[int] = mapped_column(Integer)

    # Status tracking
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus), default=AnalysisStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extracted content
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    clause_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Scores
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    framework_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # LLM metadata
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    findings: Mapped[list["AnalysisFinding"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    matrices: Mapped[list["RequirementsMatrix"]] = relationship(
        back_populates="analyses",
        secondary="analysis_matrices",
    )


class AnalysisFinding(Base):
    """A single finding from a DPA analysis."""

    __tablename__ = "analysis_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dpa_analyses.id", ondelete="CASCADE")
    )

    # Requirement reference
    framework: Mapped[str] = mapped_column(String(100))
    requirement_id: Mapped[str] = mapped_column(String(100))
    requirement_name: Mapped[str] = mapped_column(String(255))

    # Finding details
    finding_type: Mapped[FindingType] = mapped_column(Enum(FindingType))
    severity: Mapped[FindingSeverity] = mapped_column(Enum(FindingSeverity))
    matched_clause_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str] = mapped_column(Text)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    analysis: Mapped["DPAAnalysis"] = relationship(back_populates="findings")
