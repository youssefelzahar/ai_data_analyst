from typing import Any

from pydantic import BaseModel, Field

from app.schemas.data_profile_schema import DataProfileResponse
from app.schemas.data_source_schema import DatasetPreviewResponse


class SqlQueryRequest(BaseModel):
    sql: str = Field(min_length=1)


class QueryValidationResponse(BaseModel):
    is_valid: bool
    normalized_sql: str
    message: str


class QueryPagination(BaseModel):
    page: int
    page_size: int
    total_pages: int
    total_rows: int


class QueryResultResponse(BaseModel):
    """Raw result grid for an executed query (row-capped for display)."""

    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    pagination: QueryPagination | None = None


class SqlTableColumnMetadata(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool
    ordinal_position: int
    character_maximum_length: int | None = None
    numeric_precision: int | None = None
    numeric_scale: int | None = None


class SqlTableMetadataResponse(BaseModel):
    table_name: str
    columns: list[SqlTableColumnMetadata]


class SqlTablePreviewResponse(BaseModel):
    table_name: str
    columns: list[str]
    rows: list[dict[str, Any]]
    pagination: QueryPagination


class QueryAnalysisResponse(BaseModel):
    """The pd.read_sql result turned into the standard preview + profile."""

    preview: DatasetPreviewResponse
    profile: DataProfileResponse
