from typing import Any

from pydantic import BaseModel, Field

from app.schemas.data_profile_schema import DataProfileResponse
from app.schemas.data_source_schema import DatasetPreviewResponse


class SqlQueryRequest(BaseModel):
    sql: str = Field(min_length=1)


class QueryResultResponse(BaseModel):
    """Raw result grid for an executed query (row-capped for display)."""

    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool


class QueryAnalysisResponse(BaseModel):
    """The pd.read_sql result turned into the standard preview + profile."""

    preview: DatasetPreviewResponse
    profile: DataProfileResponse
