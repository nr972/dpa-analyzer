"""Orchestration service for DPA analysis pipeline."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from dpa_app.config import settings
from dpa_app.models.analysis import (
    AnalysisFinding,
    AnalysisStatus,
    DPAAnalysis,
    FindingSeverity,
    FindingType,
    RequirementsMatrix,
)
from dpa_app.schemas.matrix import MatrixContent
from dpa_app.services.analyzer import analyze_dpa
from dpa_app.services.parser import parse_document
from dpa_app.services.scorer import calculate_scores

logger = logging.getLogger(__name__)


def resolve_api_key(header_key: str | None) -> str:
    """Resolve Anthropic API key from request header or environment."""
    key = header_key or settings.anthropic_api_key
    if not key:
        raise HTTPException(
            status_code=400,
            detail=(
                "Anthropic API key required. Set the DPA_ANTHROPIC_API_KEY "
                "environment variable or pass the X-API-Key header."
            ),
        )
    return key


def validate_upload(file: UploadFile) -> None:
    """Validate uploaded file type and size."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    # Check extension
    suffix = Path(file.filename).suffix.lower()
    if suffix not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(settings.allowed_extensions)}",
        )

    # Check content type
    allowed_content_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",  # Some clients send this for .docx
    }
    if file.content_type and file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type '{file.content_type}'.",
        )


def save_upload(file: UploadFile) -> tuple[str, Path, int]:
    """Save uploaded file with UUID filename. Returns (file_id, file_path, size)."""
    suffix = Path(file.filename or "unknown").suffix.lower()
    file_id = str(uuid.uuid4())
    safe_name = f"{file_id}{suffix}"

    # Ensure uploads dir exists and path is within it
    uploads_dir = settings.uploads_dir.resolve()
    uploads_dir.mkdir(parents=True, exist_ok=True)
    file_path = (uploads_dir / safe_name).resolve()

    if not str(file_path).startswith(str(uploads_dir)):
        raise HTTPException(status_code=400, detail="Invalid file path.")

    content = file.file.read()
    size = len(content)

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if size > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size} bytes). Max: {settings.max_file_size_mb} MB.",
        )

    with open(file_path, "wb") as f:
        f.write(content)

    return file_id, file_path, size


def run_analysis(
    db: Session,
    file: UploadFile,
    matrix_ids: list[int],
    api_key: str,
    model: str | None = None,
) -> DPAAnalysis:
    """Full analysis pipeline: validate → save → parse → analyze → score → persist."""
    model = model or settings.default_model

    # Validate
    validate_upload(file)

    # Save file
    file_id, file_path, file_size = save_upload(file)
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")

    # Create analysis record
    analysis = DPAAnalysis(
        file_id=file_id,
        original_filename=file.filename or "unknown",
        file_type=suffix,
        file_size_bytes=file_size,
        status=AnalysisStatus.PENDING,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    try:
        # Load matrices
        matrices: list[RequirementsMatrix] = []
        for mid in matrix_ids:
            matrix = db.get(RequirementsMatrix, mid)
            if not matrix:
                raise HTTPException(status_code=404, detail=f"Matrix {mid} not found.")
            matrices.append(matrix)

        analysis.matrices = matrices

        # Parse document
        analysis.status = AnalysisStatus.PARSING
        db.commit()

        parsed = parse_document(file_path)
        analysis.extracted_text = parsed.full_text
        analysis.clause_count = len(parsed.clauses)

        # Analyze against each matrix
        analysis.status = AnalysisStatus.ANALYZING
        db.commit()

        all_findings_data = []
        total_tokens = 0

        for matrix in matrices:
            matrix_content = MatrixContent(**matrix.content)
            result = analyze_dpa(
                clauses=parsed.clauses,
                full_text=parsed.full_text,
                matrix=matrix_content,
                api_key=api_key,
                model=model,
            )
            all_findings_data.extend(result.findings)
            total_tokens += result.total_tokens

        # Score
        analysis.status = AnalysisStatus.SCORING
        db.commit()

        scores = calculate_scores(all_findings_data)
        analysis.overall_score = scores.overall_score
        analysis.framework_scores = scores.framework_scores
        analysis.model_used = model
        analysis.total_tokens_used = total_tokens

        # Persist findings
        for fd in all_findings_data:
            finding = AnalysisFinding(
                analysis_id=analysis.id,
                framework=fd.framework,
                requirement_id=fd.requirement_id,
                requirement_name=fd.requirement_name,
                finding_type=FindingType(fd.finding_type),
                severity=FindingSeverity(fd.severity),
                matched_clause_text=fd.matched_clause_text,
                explanation=fd.explanation,
                remediation=fd.remediation,
                confidence=fd.confidence,
            )
            db.add(finding)

        analysis.status = AnalysisStatus.COMPLETED
        analysis.completed_at = datetime.now(UTC)
        db.commit()
        db.refresh(analysis)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Analysis failed for %s", analysis.file_id)
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = str(e)[:1000]
        db.commit()
        db.refresh(analysis)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}") from e

    return analysis
