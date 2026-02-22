"""Pydantic schemas for requirements matrices."""

from datetime import datetime

from pydantic import BaseModel, Field


class RequirementItem(BaseModel):
    """A single requirement within a framework matrix."""

    id: str = Field(min_length=1, description="Unique requirement identifier")
    name: str = Field(min_length=1, max_length=255)
    article_reference: str = Field(min_length=1, description="Legal article reference")
    description: str = Field(min_length=1)
    expected_provisions: list[str] = Field(min_length=1)
    severity: str = Field(pattern="^(critical|high|medium|low)$")
    category: str = Field(min_length=1)


class MatrixContent(BaseModel):
    """The structured content of a requirements matrix."""

    framework_id: str = Field(min_length=1)
    framework_name: str = Field(min_length=1)
    requirements: list[RequirementItem] = Field(min_length=1)


class MatrixCreate(BaseModel):
    """Schema for creating a new requirements matrix."""

    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    framework: str = Field(min_length=1, max_length=100)
    version: str = "1.0"
    content: MatrixContent


class MatrixUpdate(BaseModel):
    """Schema for updating a requirements matrix."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    version: str | None = None
    content: MatrixContent | None = None


class MatrixResponse(BaseModel):
    """Full matrix response including content."""

    id: int
    name: str
    description: str
    framework: str
    version: str
    is_preset: bool
    content: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MatrixSummaryResponse(BaseModel):
    """Matrix summary without full content, for list views."""

    id: int
    name: str
    description: str
    framework: str
    version: str
    is_preset: bool
    requirement_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MatrixListResponse(BaseModel):
    """Paginated list of matrix summaries."""

    items: list[MatrixSummaryResponse]
    total: int
