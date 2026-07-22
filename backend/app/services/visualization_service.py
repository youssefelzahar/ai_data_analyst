import uuid
from dataclasses import dataclass
import re
from typing import Any

import pandas as pd

from app.db.models.data_source_model import DataSource
from app.schemas.visualization_schema import (
    ChartArtifact,
    DataTableArtifact,
    KpiCardArtifact,
    VisualizationBundle,
)
from app.services.json_safe import to_json_safe
from app.services.dataset_operations_service import (
    AggregationSpec,
    DatasetOperationsService,
    UnsupportedAggregationError,
)
from app.services.profiling.service import DataProfileService


class VisualizationError(Exception):
    """Raised when the requested visualization cannot be created."""


@dataclass(frozen=True)
class VisualizationRequest:
    user_request: str
    table_name: str | None = None
    version_id: str | None = None


class VisualizationService:
    def __init__(
        self,
        dataset_operations_service: DatasetOperationsService,
        data_profile_service: DataProfileService,
    ) -> None:
        self._dataset_operations_service = dataset_operations_service
        self._data_profile_service = data_profile_service

    def build_visualization_bundle(
        self,
        data_source: DataSource,
        visualization_request: VisualizationRequest,
    ) -> VisualizationBundle:
        dataframe = self._dataset_operations_service.load_dataframe(
            data_source,
            visualization_request.table_name,
            visualization_request.version_id,
        )
        profile = self._data_profile_service.get_profile(
            data_source,
            visualization_request.table_name,
            visualization_request.version_id,
        )

        requested_chart_types = _detect_chart_types(visualization_request.user_request)
        if not requested_chart_types:
            requested_chart_types = _default_chart_types(dataframe, visualization_request.user_request)

        kpi_cards = self._build_default_kpis(profile)
        kpi_cards.extend(self._build_requested_kpis(data_source, dataframe, visualization_request))

        charts = [
            self._build_chart(chart_type, dataframe, visualization_request.user_request)
            for chart_type in requested_chart_types
        ]
        charts = [chart for chart in charts if chart is not None]

        tables: list[DataTableArtifact] = []
        if _should_include_table(visualization_request.user_request, charts):
            preview = self._dataset_operations_service.preview(
                data_source,
                visualization_request.table_name,
                row_count=25,
                version_id=visualization_request.version_id,
            )
            tables.append(
                DataTableArtifact(
                    id=_artifact_id(),
                    title="Data Table",
                    columns=preview["column_names"],
                    rows=preview["preview_rows"],
                    row_count=preview["row_count"],
                )
            )

        return VisualizationBundle(
            kpi_cards=kpi_cards,
            tables=tables,
            charts=charts,
        )

    def build_summary(self, bundle: VisualizationBundle) -> dict[str, Any]:
        return {
            "kpi_card_count": len(bundle.kpi_cards),
            "kpi_cards": [
                {
                    "title": card.title,
                    "value": card.value,
                    "subtitle": card.subtitle,
                }
                for card in bundle.kpi_cards
            ],
            "table_count": len(bundle.tables),
            "chart_count": len(bundle.charts),
            "charts": [_summarize_chart(chart) for chart in bundle.charts],
            "chart_types": [chart.chart_type for chart in bundle.charts],
            "titles": [* [card.title for card in bundle.kpi_cards], * [chart.title for chart in bundle.charts]],
        }

    def _build_default_kpis(self, profile) -> list[KpiCardArtifact]:
        overview = profile.overview
        return [
            self._kpi("Total Records", f"{overview.row_count:,}"),
            self._kpi("Total Columns", f"{overview.column_count:,}"),
            self._kpi("Missing Values", f"{overview.total_missing_values:,}"),
            self._kpi("Duplicate Rows", f"{overview.total_duplicate_rows:,}"),
            self._kpi("Numeric Columns", f"{overview.numeric_column_count:,}"),
            self._kpi("Categorical Columns", f"{overview.categorical_column_count:,}"),
        ]

    def _build_requested_kpis(
        self,
        data_source: DataSource,
        dataframe: pd.DataFrame,
        visualization_request: VisualizationRequest,
    ) -> list[KpiCardArtifact]:
        normalized_request = visualization_request.user_request.lower()
        numeric_columns = [
            column
            for column in dataframe.columns
            if pd.api.types.is_numeric_dtype(dataframe[column])
        ]
        requested: list[KpiCardArtifact] = []
        for operation, keywords in {
            "sum": ("sum", "total"),
            "avg": ("average", "avg", "mean"),
            "min": ("min", "minimum"),
            "max": ("max", "maximum"),
            "median": ("median",),
            "count": ("count",),
        }.items():
            if not any(keyword in normalized_request for keyword in keywords):
                continue
            if operation == "count":
                column_name = _find_matching_column(normalized_request, dataframe.columns)
                if column_name is None:
                    result = self._dataset_operations_service.aggregate(
                        data_source,
                        [AggregationSpec(operation="count")],
                        visualization_request.table_name,
                        visualization_request.version_id,
                    )
                    value = next(iter(result["results"].values()))
                    requested.append(self._kpi("Count Rows", f"{value:,}" if isinstance(value, int) else str(value)))
                    continue
            else:
                # sum/avg/min/max/median only apply to numeric columns; if the
                # request names only non-numeric columns, skip the KPI instead
                # of failing the whole dashboard.
                column_name = _find_matching_column(normalized_request, numeric_columns)
                if column_name is None:
                    continue
            kpi_card = self._safe_aggregation_kpi(
                data_source, operation, column_name, visualization_request
            )
            if kpi_card is not None:
                requested.append(kpi_card)
        return requested

    def _safe_aggregation_kpi(
        self,
        data_source: DataSource,
        operation: str,
        column_name: str,
        visualization_request: VisualizationRequest,
    ) -> KpiCardArtifact | None:
        try:
            aggregation_result = self._dataset_operations_service.aggregate(
                data_source,
                [AggregationSpec(operation=operation, column_name=column_name)],
                visualization_request.table_name,
                visualization_request.version_id,
            )
        except UnsupportedAggregationError:
            return None
        alias, value = next(iter(aggregation_result["results"].items()))
        return self._kpi(alias.replace("_", " ").title(), str(value))

    def _build_chart(
        self,
        chart_type: str,
        dataframe: pd.DataFrame,
        user_request: str,
    ) -> ChartArtifact | None:
        numeric_columns = [
            column for column in dataframe.columns if pd.api.types.is_numeric_dtype(dataframe[column])
        ]
        categorical_columns = [
            column for column in dataframe.columns if not pd.api.types.is_numeric_dtype(dataframe[column])
        ]
        matched_columns = _match_columns(user_request, dataframe.columns)

        if chart_type == "histogram":
            column = matched_columns[0] if matched_columns else (numeric_columns[0] if numeric_columns else None)
            if column is None:
                return None
            return ChartArtifact(
                id=_artifact_id(),
                title=f"Histogram of {column}",
                chart_type="histogram",
                figure={
                    "data": [{"type": "histogram", "x": _json_safe_list(dataframe[column].dropna().tolist()), "name": column}],
                    "layout": {"title": f"Histogram of {column}", "bargap": 0.05},
                },
                description=f"Distribution of {column}.",
            )

        if chart_type == "scatter":
            numeric = [column for column in matched_columns if column in numeric_columns] or numeric_columns
            if len(numeric) < 2:
                return None
            x_column, y_column = numeric[:2]
            return ChartArtifact(
                id=_artifact_id(),
                title=f"{y_column} vs {x_column}",
                chart_type="scatter",
                figure={
                    "data": [
                        {
                            "type": "scatter",
                            "mode": "markers",
                            "x": _json_safe_list(dataframe[x_column].tolist()),
                            "y": _json_safe_list(dataframe[y_column].tolist()),
                            "name": f"{y_column} vs {x_column}",
                        }
                    ],
                    "layout": {"title": f"{y_column} vs {x_column}", "xaxis": {"title": x_column}, "yaxis": {"title": y_column}},
                },
            )

        if chart_type == "line":
            x_column = matched_columns[0] if matched_columns else dataframe.columns[0]
            y_column = next((column for column in matched_columns if column in numeric_columns), None)
            if y_column is None and numeric_columns:
                y_column = numeric_columns[0]
            if y_column is None:
                return None
            return ChartArtifact(
                id=_artifact_id(),
                title=f"{y_column} over {x_column}",
                chart_type="line",
                figure={
                    "data": [{"type": "scatter", "mode": "lines+markers", "x": _json_safe_list(dataframe[x_column].tolist()), "y": _json_safe_list(dataframe[y_column].tolist()), "name": y_column}],
                    "layout": {"title": f"{y_column} over {x_column}", "xaxis": {"title": x_column}, "yaxis": {"title": y_column}},
                },
            )

        if chart_type == "bar":
            category_column = next((column for column in matched_columns if column in categorical_columns), None)
            value_column = next((column for column in matched_columns if column in numeric_columns), None)
            if category_column is None:
                category_column = categorical_columns[0] if categorical_columns else None
            if category_column is None:
                return None
            if value_column is None:
                counts = dataframe[category_column].value_counts().head(10)
                x_values = counts.index.tolist()
                y_values = counts.tolist()
                title = f"Count by {category_column}"
            else:
                grouped = (
                    dataframe.groupby(category_column, dropna=False)[value_column]
                    .sum()
                    .sort_values(ascending=False)
                    .head(10)
                )
                x_values = _json_safe_list(grouped.index.tolist())
                y_values = _json_safe_list(grouped.tolist())
                title = f"{value_column} by {category_column}"
            return ChartArtifact(
                id=_artifact_id(),
                title=title,
                chart_type="bar",
                figure={
                    "data": [{"type": "bar", "x": _json_safe_list(x_values), "y": _json_safe_list(y_values), "name": title}],
                    "layout": {"title": title, "xaxis": {"title": category_column}},
                },
            )

        if chart_type == "pie":
            category_column = next((column for column in matched_columns if column in categorical_columns), None)
            if category_column is None:
                category_column = categorical_columns[0] if categorical_columns else None
            if category_column is None:
                return None
            counts = dataframe[category_column].fillna("Missing").value_counts().head(8)
            return ChartArtifact(
                id=_artifact_id(),
                title=f"Share of {category_column}",
                chart_type="pie",
                figure={
                    "data": [{"type": "pie", "labels": _json_safe_list(counts.index.tolist()), "values": _json_safe_list(counts.tolist()), "hole": 0.35}],
                    "layout": {"title": f"Share of {category_column}"},
                },
            )

        if chart_type == "box":
            column = matched_columns[0] if matched_columns else (numeric_columns[0] if numeric_columns else None)
            if column is None:
                return None
            return ChartArtifact(
                id=_artifact_id(),
                title=f"Box Plot of {column}",
                chart_type="box",
                figure={
                    "data": [{"type": "box", "y": _json_safe_list(dataframe[column].dropna().tolist()), "name": column, "boxpoints": "outliers"}],
                    "layout": {"title": f"Box Plot of {column}"},
                },
            )

        if chart_type == "heatmap":
            correlation = dataframe.select_dtypes(include=["number"]).corr()
            if correlation.empty:
                return None
            return ChartArtifact(
                id=_artifact_id(),
                title="Correlation Heatmap",
                chart_type="heatmap",
                figure={
                    "data": [
                        {
                            "type": "heatmap",
                            "x": _json_safe_list(correlation.columns.tolist()),
                            "y": _json_safe_list(correlation.index.tolist()),
                            "z": [
                                _json_safe_list(row)
                                for row in correlation.round(4).values.tolist()
                            ],
                            "colorscale": "Blues",
                        }
                    ],
                    "layout": {"title": "Correlation Heatmap"},
                },
            )

        return None

    @staticmethod
    def _kpi(title: str, value: str, subtitle: str | None = None) -> KpiCardArtifact:
        return KpiCardArtifact(
            id=_artifact_id(),
            title=title,
            value=value,
            subtitle=subtitle,
        )


def _artifact_id() -> str:
    return str(uuid.uuid4())


def _json_safe_list(values: list[Any]) -> list[Any]:
    return [to_json_safe(value) for value in values]


def _detect_chart_types(user_request: str) -> list[str]:
    normalized_request = user_request.lower()
    chart_keywords = {
        "histogram": ("histogram",),
        "scatter": ("scatter", "scatter plot"),
        "line": ("line", "trend"),
        "bar": ("bar", "bar chart"),
        "pie": ("pie", "donut"),
        "box": ("box plot", "boxplot"),
        "heatmap": ("heatmap", "correlation"),
    }
    detected = [
        chart_type
        for chart_type, keywords in chart_keywords.items()
        if any(keyword in normalized_request for keyword in keywords)
    ]
    return list(dict.fromkeys(detected))


def _default_chart_types(dataframe: pd.DataFrame, user_request: str) -> list[str]:
    normalized_request = user_request.lower()
    if "dashboard" in normalized_request:
        chart_types = ["bar"]
        if len(dataframe.select_dtypes(include=["number"]).columns) >= 2:
            chart_types.append("heatmap")
        elif len(dataframe.select_dtypes(include=["number"]).columns) == 1:
            chart_types.append("histogram")
        return chart_types
    if any(keyword in normalized_request for keyword in ("chart", "plot", "visualize", "graph")):
        if len(dataframe.select_dtypes(include=["number"]).columns) >= 2:
            return ["scatter"]
        if len(dataframe.select_dtypes(include=["number"]).columns) == 1:
            return ["histogram"]
        return ["bar"]
    if any(keyword in normalized_request for keyword in ("kpi", "kpis", "card", "cards")):
        matched_columns = _match_columns(user_request, dataframe.columns)
        categorical_columns = [
            column for column in dataframe.columns if not pd.api.types.is_numeric_dtype(dataframe[column])
        ]
        if any(column in categorical_columns for column in matched_columns):
            return ["bar"]
    return []


def _should_include_table(user_request: str, charts: list[ChartArtifact]) -> bool:
    normalized_request = user_request.lower()
    if any(keyword in normalized_request for keyword in ("table", "rows", "data table", "show data")):
        return True
    return not charts or "dashboard" in normalized_request


def _match_columns(user_request: str, columns) -> list[str]:
    normalized_request = user_request.lower()
    matched_columns: list[str] = []
    for column in columns:
        pattern = r"(?<!\w)" + re.escape(str(column).lower()).replace(r"\ ", r"\s+") + r"(?!\w)"
        if re.search(pattern, normalized_request):
            matched_columns.append(str(column))
    return matched_columns


def _find_matching_column(user_request: str, columns) -> str | None:
    matched_columns = _match_columns(user_request, columns)
    return matched_columns[0] if matched_columns else None


def _summarize_chart(chart: ChartArtifact) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "title": chart.title,
        "chart_type": chart.chart_type,
        "description": chart.description,
    }
    series = chart.figure.get("data", [])
    if not series:
        return summary
    first_series = series[0]
    if chart.chart_type == "bar":
        x_values = first_series.get("x", [])
        y_values = first_series.get("y", [])
        summary["values"] = [
            {"label": label, "value": value}
            for label, value in zip(x_values[:10], y_values[:10])
        ]
    if chart.chart_type == "pie":
        labels = first_series.get("labels", [])
        values = first_series.get("values", [])
        summary["values"] = [
            {"label": label, "value": value}
            for label, value in zip(labels[:10], values[:10])
        ]
    return summary
