from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class KpiCardArtifact(BaseModel):
    id: str
    artifact_type: Literal["kpi_card"] = "kpi_card"
    title: str
    value: str
    subtitle: str | None = None


class DataTableArtifact(BaseModel):
    id: str
    artifact_type: Literal["data_table"] = "data_table"
    title: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int


class ChartArtifact(BaseModel):
    id: str
    artifact_type: Literal["chart"] = "chart"
    title: str
    chart_type: Literal[
        "histogram",
        "scatter",
        "line",
        "bar",
        "pie",
        "box",
        "heatmap",
    ]
    figure: dict[str, Any]
    description: str | None = None


class VisualizationBundle(BaseModel):
    kpi_cards: list[KpiCardArtifact] = Field(default_factory=list)
    tables: list[DataTableArtifact] = Field(default_factory=list)
    charts: list[ChartArtifact] = Field(default_factory=list)


class ConversationMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    visualizations: VisualizationBundle = Field(default_factory=VisualizationBundle)


class ConversationResponse(BaseModel):
    session_id: str
    title: str | None = None
    selected_data_source_id: str | None = None
    selected_version_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationMessageResponse] = Field(default_factory=list)


class ConversationSummaryResponse(BaseModel):
    session_id: str
    title: str | None = None
    selected_data_source_id: str | None = None
    selected_version_id: str | None = None
    updated_at: datetime
    message_count: int
    last_message_preview: str | None = None
