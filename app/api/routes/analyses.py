"""API routes for DPA analysis."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.database import DbDep
from app.models.analysis import (
    AnalysisFinding,
    AnalysisStatus,
    DPAAnalysis,
    FindingSeverity,
    FindingType,
)
from app.schemas.analysis import (
    AnalysisDetailResponse,
    AnalysisListResponse,
    AnalysisResponse,
    FindingResponse,
    FindingsListResponse,
    FindingsSummary,
)
from app.schemas.matrix import MatrixSummaryResponse
from app.services import analysis_service
from app.services.reporter import generate_report

router = APIRouter()


@router.post("/", response_model=AnalysisResponse, status_code=201)
def create_analysis(
    file: UploadFile,
    db: DbDep,
    matrix_ids: Annotated[str, Query(description="Comma-separated matrix IDs")] = "",
    model: Annotated[str | None, Query()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> AnalysisResponse:
    """Upload a DPA document and run analysis against selected matrices."""
    api_key = analysis_service.resolve_api_key(x_api_key)

    ids = [int(x.strip()) for x in matrix_ids.split(",") if x.strip()]
    if not ids:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="At least one matrix_id is required.")

    analysis = analysis_service.run_analysis(
        db=db,
        file=file,
        matrix_ids=ids,
        api_key=api_key,
        model=model,
    )
    return AnalysisResponse.model_validate(analysis)


@router.get("/", response_model=AnalysisListResponse)
def list_analyses(
    db: DbDep,
    status: AnalysisStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> AnalysisListResponse:
    """List all DPA analyses."""
    query = select(DPAAnalysis)
    count_query = select(func.count()).select_from(DPAAnalysis)

    if status:
        query = query.where(DPAAnalysis.status == status)
        count_query = count_query.where(DPAAnalysis.status == status)

    total = db.scalar(count_query) or 0
    items = list(
        db.scalars(
            query.order_by(DPAAnalysis.created_at.desc()).offset(skip).limit(limit)
        ).all()
    )
    return AnalysisListResponse(
        items=[AnalysisResponse.model_validate(a) for a in items],
        total=total,
    )


@router.get("/{analysis_id}", response_model=AnalysisDetailResponse)
def get_analysis(analysis_id: int, db: DbDep) -> AnalysisDetailResponse:
    """Get full analysis detail including findings and matrices used."""
    analysis = db.get(DPAAnalysis, analysis_id)
    if not analysis:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Analysis not found.")

    finding_responses = [
        FindingResponse.model_validate(f) for f in analysis.findings
    ]
    matrix_summaries = []
    for m in analysis.matrices:
        req_count = len(m.content.get("requirements", [])) if m.content else 0
        matrix_summaries.append(
            MatrixSummaryResponse(
                id=m.id,
                name=m.name,
                description=m.description,
                framework=m.framework,
                version=m.version,
                is_preset=m.is_preset,
                requirement_count=req_count,
                created_at=m.created_at,
            )
        )

    return AnalysisDetailResponse(
        **AnalysisResponse.model_validate(analysis).model_dump(),
        findings=finding_responses,
        matrices_used=matrix_summaries,
    )


@router.delete("/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: int, db: DbDep) -> None:
    """Delete an analysis and its findings."""
    analysis = db.get(DPAAnalysis, analysis_id)
    if not analysis:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Analysis not found.")
    db.delete(analysis)
    db.commit()


@router.get("/{analysis_id}/findings", response_model=FindingsListResponse)
def get_findings(
    analysis_id: int,
    db: DbDep,
    framework: str | None = None,
    finding_type: FindingType | None = None,
    severity: FindingSeverity | None = None,
) -> FindingsListResponse:
    """Get findings for an analysis with optional filters."""
    analysis = db.get(DPAAnalysis, analysis_id)
    if not analysis:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Analysis not found.")

    query = select(AnalysisFinding).where(AnalysisFinding.analysis_id == analysis_id)
    if framework:
        query = query.where(AnalysisFinding.framework == framework)
    if finding_type:
        query = query.where(AnalysisFinding.finding_type == finding_type)
    if severity:
        query = query.where(AnalysisFinding.severity == severity)

    findings = list(db.scalars(query).all())

    # Build summary
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_framework: dict[str, int] = {}
    for f in findings:
        ft = f.finding_type.value if hasattr(f.finding_type, "value") else str(f.finding_type)
        by_type[ft] = by_type.get(ft, 0) + 1
        sv = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        by_severity[sv] = by_severity.get(sv, 0) + 1
        by_framework[f.framework] = by_framework.get(f.framework, 0) + 1

    return FindingsListResponse(
        items=[FindingResponse.model_validate(f) for f in findings],
        total=len(findings),
        summary=FindingsSummary(
            total_findings=len(findings),
            by_type=by_type,
            by_severity=by_severity,
            by_framework=by_framework,
        ),
    )


@router.get("/{analysis_id}/report")
def download_report(
    analysis_id: int,
    db: DbDep,
    format: Annotated[str, Query(pattern="^(json|html|docx|pdf)$")] = "json",
) -> FileResponse:
    """Download gap analysis report in specified format."""
    analysis = db.get(DPAAnalysis, analysis_id)
    if not analysis:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if analysis.status != AnalysisStatus.COMPLETED:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Analysis not yet completed.")

    findings = list(
        db.scalars(
            select(AnalysisFinding).where(AnalysisFinding.analysis_id == analysis_id)
        ).all()
    )

    report_path = generate_report(analysis, findings, list(analysis.matrices), format)

    media_types = {
        "json": "application/json",
        "html": "text/html",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }

    return FileResponse(
        path=str(report_path),
        media_type=media_types.get(format, "application/octet-stream"),
        filename=report_path.name,
    )
