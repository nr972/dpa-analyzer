"""CRUD operations for requirements matrices."""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dpa_app.models.analysis import RequirementsMatrix
from dpa_app.schemas.matrix import MatrixCreate, MatrixUpdate


def create_matrix(db: Session, data: MatrixCreate) -> RequirementsMatrix:
    """Create a new requirements matrix."""
    matrix = RequirementsMatrix(
        name=data.name,
        description=data.description,
        framework=data.framework,
        version=data.version,
        content=data.content.model_dump(),
    )
    db.add(matrix)
    db.commit()
    db.refresh(matrix)
    return matrix


def get_matrix(db: Session, matrix_id: int) -> RequirementsMatrix:
    """Get a single matrix by ID. Raises 404 if not found."""
    matrix = db.get(RequirementsMatrix, matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail="Requirements matrix not found")
    return matrix


def list_matrices(
    db: Session,
    framework: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[RequirementsMatrix], int]:
    """List matrices with optional framework filter. Returns (items, total)."""
    query = select(RequirementsMatrix)
    count_query = select(func.count()).select_from(RequirementsMatrix)

    if framework:
        query = query.where(RequirementsMatrix.framework == framework)
        count_query = count_query.where(RequirementsMatrix.framework == framework)

    total = db.scalar(count_query) or 0
    items = list(db.scalars(query.offset(skip).limit(limit).order_by(RequirementsMatrix.id)).all())
    return items, total


def update_matrix(db: Session, matrix_id: int, data: MatrixUpdate) -> RequirementsMatrix:
    """Update a matrix. Raises 404 if not found, 403 if preset."""
    matrix = get_matrix(db, matrix_id)

    if matrix.is_preset:
        raise HTTPException(
            status_code=403,
            detail="Cannot modify a preset requirements matrix. Create a copy instead.",
        )

    update_data = data.model_dump(exclude_unset=True)
    if "content" in update_data and update_data["content"] is not None:
        update_data["content"] = data.content.model_dump()  # type: ignore[union-attr]

    for field, value in update_data.items():
        setattr(matrix, field, value)

    db.commit()
    db.refresh(matrix)
    return matrix


def delete_matrix(db: Session, matrix_id: int) -> None:
    """Delete a matrix. Raises 404 if not found, 403 if preset."""
    matrix = get_matrix(db, matrix_id)

    if matrix.is_preset:
        raise HTTPException(
            status_code=403, detail="Cannot delete a preset requirements matrix."
        )

    db.delete(matrix)
    db.commit()
