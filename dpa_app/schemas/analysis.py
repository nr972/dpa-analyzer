"""Pydantic schemas for DPA analyses and findings."""

from datetime import datetime

from pydantic import BaseModel

from dpa_app.models.analysis import AnalysisStatus, FindingSeverity, FindingType
from dpa_app.schemas.matrix import MatrixSummaryResponse


class FindingResponse(BaseModel):
    """Schema for a single analysis finding."""

    id: int
    framework: str
    requirement_id: str
    requirement_name: str
    finding_type: FindingType
    severity: FindingSeverity
    matched_clause_text: str | None
    explanation: str
    remediation: str | None
    confidence: float | None

    model_config = {"from_attributes": True}


class FindingsSummary(BaseModel):
    """Aggregated summary of findings."""

    total_findings: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
    by_framework: dict[str, int]


class FindingsListResponse(BaseModel):
    """Paginated list of findings with summary."""

    items: list[FindingResponse]
    total: int
    summary: FindingsSummary


class AnalysisResponse(BaseModel):
    """Schema for analysis list items."""

    id: int
    file_id: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    status: AnalysisStatus
    error_message: str | None
    overall_score: float | None
    framework_scores: dict | None
    model_used: str | None
    total_tokens_used: int | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class AnalysisDetailResponse(AnalysisResponse):
    """Full analysis detail including findings and matrices used."""

    findings: list[FindingResponse]
    matrices_used: list[MatrixSummaryResponse]


class AnalysisListResponse(BaseModel):
    """Paginated list of analyses."""

    items: list[AnalysisResponse]
    total: int
