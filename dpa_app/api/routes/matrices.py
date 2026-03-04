"""API routes for requirements matrix CRUD."""

from fastapi import APIRouter, Query

from dpa_app.database import DbDep
from dpa_app.schemas.matrix import (
    MatrixCreate,
    MatrixListResponse,
    MatrixResponse,
    MatrixSummaryResponse,
    MatrixUpdate,
)
from dpa_app.services import matrix_service

router = APIRouter()


@router.post("/", response_model=MatrixResponse, status_code=201)
def create_matrix(data: MatrixCreate, db: DbDep) -> MatrixResponse:
    """Create a new requirements matrix."""
    matrix = matrix_service.create_matrix(db, data)
    return MatrixResponse.model_validate(matrix)


@router.get("/", response_model=MatrixListResponse)
def list_matrices(
    db: DbDep,
    framework: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> MatrixListResponse:
    """List all requirements matrices."""
    items, total = matrix_service.list_matrices(db, framework, skip, limit)
    summaries = []
    for m in items:
        req_count = len(m.content.get("requirements", [])) if m.content else 0
        summaries.append(
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
    return MatrixListResponse(items=summaries, total=total)


@router.get("/{matrix_id}", response_model=MatrixResponse)
def get_matrix(matrix_id: int, db: DbDep) -> MatrixResponse:
    """Get a single requirements matrix with full content."""
    matrix = matrix_service.get_matrix(db, matrix_id)
    return MatrixResponse.model_validate(matrix)


@router.put("/{matrix_id}", response_model=MatrixResponse)
def update_matrix(
    matrix_id: int, data: MatrixUpdate, db: DbDep
) -> MatrixResponse:
    """Update a requirements matrix. Cannot modify preset matrices."""
    matrix = matrix_service.update_matrix(db, matrix_id, data)
    return MatrixResponse.model_validate(matrix)


@router.delete("/{matrix_id}", status_code=204)
def delete_matrix(matrix_id: int, db: DbDep) -> None:
    """Delete a requirements matrix. Cannot delete preset matrices."""
    matrix_service.delete_matrix(db, matrix_id)
