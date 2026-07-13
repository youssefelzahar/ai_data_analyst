from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.data_profile_schema import DatasetOverview
from app.services.cleaning.strategy import OperationSpec

__all__ = ["OperationSpec"]


class RecommendationItem(BaseModel):
    category: str
    column_name: str | None
    recommended_operation_key: str
    recommended_label: str
    reason: str
    alternative_operation_keys: list[str] = []


class CleaningRecommendationsResponse(BaseModel):
    missing_values: list[RecommendationItem]
    duplicates: list[RecommendationItem]
    type_conversion: list[RecommendationItem]
    outliers: list[RecommendationItem]
    encoding: list[RecommendationItem]
    scaling: list[RecommendationItem]
    skew: list[RecommendationItem]
    text: list[RecommendationItem]


class CleaningMethodDescriptor(BaseModel):
    key: str
    label: str
    category: str


class CleaningMethodsCatalog(BaseModel):
    methods: list[CleaningMethodDescriptor]


class CleaningPipelineRequest(BaseModel):
    table_name: str | None = None
    operations: list[OperationSpec]


class PipelineStepResult(BaseModel):
    operation_key: str
    column_name: str | None
    affected_row_count: int
    affected_column_count: int
    message: str


class PipelinePreviewResponse(BaseModel):
    steps: list[PipelineStepResult]
    before_overview: DatasetOverview
    after_overview: DatasetOverview
    sample_before_rows: list[dict[str, Any]]
    sample_after_rows: list[dict[str, Any]]


class DatasetVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    data_source_id: str
    version_number: int
    row_count: int
    column_count: int
    file_size_bytes: int
    operations_summary: list[dict[str, Any]]
    label: str | None
    created_at: datetime
