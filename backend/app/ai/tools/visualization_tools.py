import json
import re
from typing import Any

from app.ai.tools.dataset_tools import DatasetToolBase, DatasetToolExecutionError
from app.ai.tools.registry import ToolContext, ToolResult
from app.db.models.data_source_model import DataSource
from app.schemas.data_source_schema import DataSourceType
from app.schemas.visualization_schema import VisualizationBundle
from app.services.visualization_service import VisualizationRequest, VisualizationService


class VisualizationDashboardTool(DatasetToolBase):
    name = "visualization_dashboard"
    description = "Builds KPI cards, tables, and charts for an analytics dashboard."
    intents = ("visualize_dashboard",)
    keywords = (
        "dashboard",
        "visualize",
        "chart",
        "plot",
        "graph",
        "histogram",
        "scatter",
        "line chart",
        "bar chart",
        "pie chart",
        "box plot",
        "heatmap",
        "kpi",
        "kpis",
        "kpi card",
        "kpi cards",
        "card",
        "cards",
        "table",
    )

    def __init__(
        self,
        data_source_repository,
        dataset_operations_service,
        visualization_service: VisualizationService,
    ) -> None:
        super().__init__(data_source_repository, dataset_operations_service)
        self._visualization_service = visualization_service

    def execute(self, context: ToolContext) -> ToolResult:
        try:
            data_source = self._require_data_source(context)
            table_name = self._resolve_table_name(context, data_source)
            visualization_bundle = self._visualization_service.build_visualization_bundle(
                data_source,
                VisualizationRequest(
                    user_request=context.user_request,
                    table_name=table_name,
                    version_id=context.selected_version_id,
                ),
            )
            if data_source.source_type == DataSourceType.SQL_SERVER.value and table_name:
                context.session_context["active_table"] = table_name
            summary = self._visualization_service.build_summary(visualization_bundle)
            return ToolResult(
                tool_name=self.name,
                content=json.dumps(summary, indent=2, sort_keys=True),
                metadata={
                    "status": "ok",
                    "visualizations": visualization_bundle.model_dump(mode="json"),
                    "result": summary,
                    "session_context_updates": (
                        {"active_table": table_name} if table_name else {}
                    ),
                },
            )
        except Exception as error:  # noqa: BLE001
            payload = {"error": str(error)}
            return ToolResult(
                tool_name=self.name,
                content=json.dumps(payload, indent=2, sort_keys=True),
                metadata={"status": "error", "result": payload},
            )


def build_visualization_tools(
    data_source_repository,
    dataset_operations_service,
    visualization_service: VisualizationService,
) -> list[VisualizationDashboardTool]:
    return [
        VisualizationDashboardTool(
            data_source_repository,
            dataset_operations_service,
            visualization_service,
        )
    ]
