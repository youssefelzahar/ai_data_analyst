"""Schemas describing a fully-assembled analysis report.

An `ExportReport` is a snapshot of everything the exporters need. It is built
once (by the report builder, reusing profiling / analysis / visualization
results) and then rendered into PDF, Excel, or Power BI without recomputing any
of the underlying data. Keeping it as a serializable pydantic model also lets
the API expose the same structure to the frontend for a live report preview.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.data_profile_schema import DataProfileResponse
from app.schemas.visualization_schema import (
    ChartArtifact,
    DataTableArtifact,
    KpiCardArtifact,
)


class DatasetSummarySection(BaseModel):
    dataset_name: str
    source_type: str
    version_id: str | None = None
    version_label: str | None = None
    row_count: int
    column_count: int
    numeric_column_count: int
    categorical_column_count: int
    total_missing_values: int
    missing_percentage: float
    total_duplicate_rows: int
    memory_usage_bytes: int
    dataset_size_bytes: int | None = None


class CleaningOperationSummary(BaseModel):
    operation_key: str
    column_name: str | None = None
    message: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class CleaningVersionSummary(BaseModel):
    version_id: str
    version_number: int
    label: str | None = None
    row_count: int
    column_count: int
    created_at: datetime
    operations: list[CleaningOperationSummary] = Field(default_factory=list)


class CleaningSummarySection(BaseModel):
    """Present only when at least one cleaning version has been applied."""

    applied: bool
    total_versions: int
    selected_version_number: int | None = None
    versions: list[CleaningVersionSummary] = Field(default_factory=list)


class Insight(BaseModel):
    title: str
    detail: str
    severity: Literal["info", "warning", "critical"] = "info"


class Recommendation(BaseModel):
    title: str
    detail: str
    priority: Literal["low", "medium", "high"] = "medium"


class ModelMetric(BaseModel):
    name: str
    value: str


class ModelPerformanceSection(BaseModel):
    """Present only when a model / prediction result is available."""

    model_name: str
    task_type: str
    metrics: list[ModelMetric] = Field(default_factory=list)


class VisualizationSection(BaseModel):
    kpi_cards: list[KpiCardArtifact] = Field(default_factory=list)
    charts: list[ChartArtifact] = Field(default_factory=list)
    tables: list[DataTableArtifact] = Field(default_factory=list)


class ExportReport(BaseModel):
    """The complete, pre-computed analysis report shared by every exporter."""

    generated_at: datetime
    dataset_summary: DatasetSummarySection
    profiling: DataProfileResponse
    cleaning_summary: CleaningSummarySection | None = None
    visualizations: VisualizationSection = Field(default_factory=VisualizationSection)
    kpi_summary: list[KpiCardArtifact] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    model_performance: ModelPerformanceSection | None = None


class ExportFormatDescriptor(BaseModel):
    key: str
    label: str
    file_extension: str
    media_type: str
    description: str


class ExportFormatsResponse(BaseModel):
    formats: list[ExportFormatDescriptor]
