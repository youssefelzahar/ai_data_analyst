import json
import re
from collections.abc import Sequence
from typing import Any

import pandas as pd

from app.ai.tools.registry import ToolContext, ToolResult
from app.db.models.data_source_model import DataSource
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.data_source_schema import DataSourceType
from app.services.dataset_frame_service import (
    MissingTableNameError,
    UnknownDatasetVersionError,
    UnknownTableError,
)
from app.services.dataset_operations_service import (
    AggregationSpec,
    DatasetOperationError,
    DatasetOperationsService,
    FilterCondition,
)
from app.services.json_safe import to_json_safe
from app.services.profiling.loaders import DatasetLoadError, UnsupportedDataSourceError
from app.services.profiling.service import NonNumericColumnError, UnknownColumnError

_MAX_TOOL_ROWS = 50
_MAX_VALUE_COUNTS = 25


class DatasetToolExecutionError(Exception):
    """Raised when a dataset tool cannot fulfill a user request."""


class DatasetToolBase:
    name = ""
    description = ""
    intents: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    def __init__(
        self,
        data_source_repository: DataSourceRepository,
        dataset_operations_service: DatasetOperationsService,
    ) -> None:
        self._data_source_repository = data_source_repository
        self._dataset_operations_service = dataset_operations_service

    def execute(self, context: ToolContext) -> ToolResult:
        try:
            data_source = self._require_data_source(context)
            table_name = self._resolve_table_name(context, data_source)
            payload = self._run(context, data_source, table_name)
            return ToolResult(
                tool_name=self.name,
                content=_serialize_tool_payload(payload),
                metadata={"status": "ok", "result": payload},
            )
        except (
            DatasetToolExecutionError,
            DatasetOperationError,
            DatasetLoadError,
            UnsupportedDataSourceError,
            MissingTableNameError,
            UnknownTableError,
            UnknownDatasetVersionError,
            UnknownColumnError,
            NonNumericColumnError,
        ) as error:
            payload = {"error": str(error)}
            return ToolResult(
                tool_name=self.name,
                content=_serialize_tool_payload(payload),
                metadata={"status": "error", "result": payload},
            )

    def _run(
        self,
        context: ToolContext,
        data_source: DataSource,
        table_name: str | None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def _require_data_source(self, context: ToolContext) -> DataSource:
        if not context.selected_data_source_id:
            raise DatasetToolExecutionError(
                "Select a data source before running data-analysis tools."
            )
        data_source = self._data_source_repository.get_data_source_by_id(
            context.selected_data_source_id
        )
        if data_source is None:
            raise DatasetToolExecutionError(
                f"Data source '{context.selected_data_source_id}' was not found."
            )
        return data_source

    @staticmethod
    def _resolve_table_name(
        context: ToolContext,
        data_source: DataSource,
    ) -> str | None:
        if data_source.source_type != DataSourceType.SQL_SERVER.value:
            return None
        active_table = context.session_context.get("active_table")
        if isinstance(active_table, str) and active_table.strip():
            return active_table.strip()
        table_match = re.search(r"\btable\s+([A-Za-z_][\w$#@-]*)", context.user_request, re.I)
        if table_match:
            return table_match.group(1)
        return None


class DatasetPreviewTool(DatasetToolBase):
    name = "dataset_preview"
    description = "Returns a sample of dataset rows and basic shape information."
    intents = ("preview_dataset",)
    keywords = (
        # General preview
        "preview",
        "sample",
        "show data",
        "show dataset",
        "show table",
        "display data",
        "display dataset",
        "view data",
        "view dataset",

        # First rows
        "head",
        "show head",
        "first rows",
        "first row",
        "top rows",
        "top row",
        "show first",
        "show first rows",
        "show first 5 rows",
        "show first 10 rows",
        "show top",
        "show top rows",
        "show top 5 rows",
        "show top 10 rows",

        # Records
        "sample rows",
        "sample data",
        "sample records",
        "show sample",
        "show sample data",
        "show sample rows",

        # Display commands
        "display rows",
        "display records",
        "display first rows",
        "list rows",
        "list records",

        # Inspection
        "peek",
        "peek data",
        "peek dataset",
        "inspect data",
        "inspect dataset",

        # Pandas terminology
        "head()",
        "df.head",
    )
    def _run(
        self,
        context: ToolContext,
        data_source: DataSource,
        table_name: str | None,
    ) -> dict[str, Any]:
        row_count = _extract_limit(context.user_request, default=5, maximum=_MAX_TOOL_ROWS)
        return self._dataset_operations_service.preview(
            data_source, table_name, row_count, context.selected_version_id
        )


class DatasetSummaryTool(DatasetToolBase):
    name = "dataset_summary"
    description = "Returns dataset-level summary statistics and quality information."
    intents = ("summarize_dataset",)
    keywords = (
        "summarize",
        "summary",
        "describe",
        "overview",
        "profile",
        "dataset summary",
        "analyze",
        "analyse",
        "analysis",
        "insights",
        "explore",
        "tell me about",
        "what can you tell me",
        "understand the data",
    )

    def _run(
        self,
        context: ToolContext,
        data_source: DataSource,
        table_name: str | None,
    ) -> dict[str, Any]:
        return self._dataset_operations_service.summary(
            data_source, table_name, context.selected_version_id
        )


class ColumnInformationTool(DatasetToolBase):
    name = "column_information"
    description = "Returns schema and profiling details for one or more columns."
    intents = ("column_information",)
    keywords = ("column", "columns", "schema", "datatype", "data type", "field")

    def _run(
        self,
        context: ToolContext,
        data_source: DataSource,
        table_name: str | None,
    ) -> dict[str, Any]:
        profile = self._dataset_operations_service.summary(
            data_source, table_name, context.selected_version_id
        )
        available_columns = _extract_columns_from_summary(profile)
        matched_columns = _match_columns(context.user_request, available_columns)
        return self._dataset_operations_service.column_information(
            data_source,
            table_name,
            matched_columns or None,
            context.selected_version_id,
        )


class ValueCountsTool(DatasetToolBase):
    name = "value_counts"
    description = "Counts occurrences of distinct values in one column."
    intents = ("value_counts",)
    keywords = (
        "value counts",
        "frequency",
        "frequencies",
        "most common",
        "distinct values",
        "how many of each",
        "distribution of",
        "count by value",
        "unique values",
    )

    def _run(
        self,
        context: ToolContext,
        data_source: DataSource,
        table_name: str | None,
    ) -> dict[str, Any]:
        dataframe = self._load_dataframe(data_source, table_name, context.selected_version_id)
        column_name = _require_single_column(context.user_request, dataframe.columns)
        limit = _extract_limit(
            context.user_request,
            default=10,
            maximum=_MAX_VALUE_COUNTS,
        )
        include_nulls = "include null" in context.user_request.lower()
        return self._dataset_operations_service.value_counts(
            data_source,
            column_name,
            table_name,
            limit,
            include_nulls,
            context.selected_version_id,
        )

    def _load_dataframe(
        self, data_source: DataSource, table_name: str | None, version_id: str | None = None
    ) -> pd.DataFrame:
        return self._dataset_operations_service.load_dataframe(data_source, table_name, version_id)


class GroupByTool(DatasetToolBase):
    name = "group_by"
    description = "Groups rows and computes grouped aggregations."
    intents = ("group_by",)
    keywords = ("group by", "grouped by", "breakdown by", "by category")

    def _run(
        self,
        context: ToolContext,
        data_source: DataSource,
        table_name: str | None,
    ) -> dict[str, Any]:
        dataframe = self._load_dataframe(data_source, table_name, context.selected_version_id)
        group_columns = _extract_group_columns(context.user_request, dataframe.columns)
        if not group_columns:
            raise DatasetToolExecutionError(
                "Specify at least one group-by column."
            )
        aggregations = _extract_aggregations(context.user_request, dataframe.columns)
        limit = _extract_limit(context.user_request, default=20, maximum=_MAX_TOOL_ROWS)
        ascending = _is_ascending_request(context.user_request)
        return self._dataset_operations_service.group_by(
            data_source,
            group_columns,
            aggregations,
            table_name,
            limit,
            ascending,
            context.selected_version_id,
        )

    def _load_dataframe(
        self, data_source: DataSource, table_name: str | None, version_id: str | None = None
    ) -> pd.DataFrame:
        return self._dataset_operations_service.load_dataframe(data_source, table_name, version_id)


class CorrelationTool(DatasetToolBase):
    name = "correlation"
    description = "Computes correlations between numeric columns."
    intents = ("correlation",)
    keywords = (
        "correlation",
        "correlate",
        "relationship",
        "correlation matrix",
        "related",
        "correlated",
        "connection between",
        "affect",
        "impact",
    )

    def _run(
        self,
        context: ToolContext,
        data_source: DataSource,
        table_name: str | None,
    ) -> dict[str, Any]:
        dataframe = self._load_dataframe(data_source, table_name, context.selected_version_id)
        matched_columns = _match_columns(context.user_request, dataframe.columns)
        return self._dataset_operations_service.correlation(
            data_source,
            matched_columns or None,
            table_name,
            version_id=context.selected_version_id,
        )

    def _load_dataframe(
        self, data_source: DataSource, table_name: str | None, version_id: str | None = None
    ) -> pd.DataFrame:
        return self._dataset_operations_service.load_dataframe(data_source, table_name, version_id)


class FilteringTool(DatasetToolBase):
    name = "filtering"
    description = "Filters dataset rows using explicit conditions."
    intents = ("filter_dataset",)
    keywords = ("filter", "where", "rows with", "only rows", "contains")

    def _run(
        self,
        context: ToolContext,
        data_source: DataSource,
        table_name: str | None,
    ) -> dict[str, Any]:
        dataframe = self._load_dataframe(data_source, table_name, context.selected_version_id)
        filters = _extract_filters(context.user_request, dataframe.columns)
        if not filters:
            raise DatasetToolExecutionError(
                "Specify filter conditions like 'revenue > 100' or 'region = north'."
            )
        limit = _extract_limit(context.user_request, default=20, maximum=_MAX_TOOL_ROWS)
        return self._dataset_operations_service.filter_rows(
            data_source,
            filters,
            table_name,
            limit,
            context.selected_version_id,
        )

    def _load_dataframe(
        self, data_source: DataSource, table_name: str | None, version_id: str | None = None
    ) -> pd.DataFrame:
        return self._dataset_operations_service.load_dataframe(data_source, table_name, version_id)


class SortingTool(DatasetToolBase):
    name = "sorting"
    description = "Sorts dataset rows by one column."
    intents = ("sort_dataset",)
    keywords = ("sort", "order by", "ascending", "descending", "highest", "lowest")

    def _run(
        self,
        context: ToolContext,
        data_source: DataSource,
        table_name: str | None,
    ) -> dict[str, Any]:
        dataframe = self._load_dataframe(data_source, table_name, context.selected_version_id)
        column_name = _require_single_column(context.user_request, dataframe.columns)
        limit = _extract_limit(context.user_request, default=20, maximum=_MAX_TOOL_ROWS)
        ascending = _is_ascending_request(context.user_request)
        return self._dataset_operations_service.sort_rows(
            data_source,
            column_name,
            table_name,
            ascending,
            limit,
            context.selected_version_id,
        )

    def _load_dataframe(
        self, data_source: DataSource, table_name: str | None, version_id: str | None = None
    ) -> pd.DataFrame:
        return self._dataset_operations_service.load_dataframe(data_source, table_name, version_id)


class AggregationTool(DatasetToolBase):
    name = "aggregations"
    description = "Computes scalar aggregations like sum, avg, min, max, count, and median."
    intents = ("aggregate_dataset",)
    keywords = (
        "sum",
        "avg",
        "average",
        "mean",
        "min",
        "max",
        "count",
        "median",
        "total",
        "how much",
        "how many",
        "grand total",
        "overall",
    )

    def _run(
        self,
        context: ToolContext,
        data_source: DataSource,
        table_name: str | None,
    ) -> dict[str, Any]:
        dataframe = self._load_dataframe(data_source, table_name, context.selected_version_id)
        aggregations = _extract_aggregations(context.user_request, dataframe.columns)
        if not aggregations:
            raise DatasetToolExecutionError(
                "Specify an aggregation like 'sum of revenue' or 'count rows'."
            )
        return self._dataset_operations_service.aggregate(
            data_source,
            aggregations,
            table_name,
            context.selected_version_id,
        )

    def _load_dataframe(
        self, data_source: DataSource, table_name: str | None, version_id: str | None = None
    ) -> pd.DataFrame:
        return self._dataset_operations_service.load_dataframe(data_source, table_name, version_id)


def build_dataset_tools(
    data_source_repository: DataSourceRepository,
    dataset_operations_service: DatasetOperationsService,
) -> list[DatasetToolBase]:
    return [
        DatasetPreviewTool(data_source_repository, dataset_operations_service),
        DatasetSummaryTool(data_source_repository, dataset_operations_service),
        ColumnInformationTool(data_source_repository, dataset_operations_service),
        ValueCountsTool(data_source_repository, dataset_operations_service),
        GroupByTool(data_source_repository, dataset_operations_service),
        CorrelationTool(data_source_repository, dataset_operations_service),
        FilteringTool(data_source_repository, dataset_operations_service),
        SortingTool(data_source_repository, dataset_operations_service),
        AggregationTool(data_source_repository, dataset_operations_service),
    ]


def _extract_limit(user_request: str, default: int, maximum: int) -> int:
    match = re.search(r"\b(?:top|first|last|limit)\s+(\d+)\b", user_request, re.I)
    if match is None:
        return default
    return max(1, min(int(match.group(1)), maximum))


def _extract_columns_from_summary(summary: dict[str, Any]) -> list[str]:
    numeric_columns = [
        statistics["column_name"]
        for statistics in summary.get("numeric_statistics", [])
    ]
    categorical_columns = [
        statistics["column_name"]
        for statistics in summary.get("categorical_statistics", [])
    ]
    return list(dict.fromkeys(numeric_columns + categorical_columns))


def _match_columns(user_request: str, columns: Sequence[str]) -> list[str]:
    normalized_request = user_request.lower()
    matched_columns: list[tuple[int, str]] = []
    for column in sorted(columns, key=len, reverse=True):
        pattern = r"(?<!\w)" + re.escape(column.lower()).replace(r"\ ", r"\s+") + r"(?!\w)"
        match = re.search(pattern, normalized_request)
        if match is not None:
            matched_columns.append((match.start(), str(column)))
    matched_columns.sort(key=lambda item: item[0])
    return [column for _, column in matched_columns]


def _require_single_column(user_request: str, columns: Sequence[str]) -> str:
    matched_columns = _match_columns(user_request, columns)
    if not matched_columns:
        raise DatasetToolExecutionError("Specify which column to use.")
    return matched_columns[0]


def _extract_group_columns(user_request: str, columns: Sequence[str]) -> list[str]:
    match = re.search(
        r"\bgroup(?:ed)?\s+by\s+(.+?)(?:\b(?:with|using|show|where|having|for)\b|$)",
        user_request,
        re.I,
    )
    if match is None:
        return []
    clause = match.group(1)
    group_columns = _match_columns(clause, columns)
    if group_columns:
        return group_columns
    normalized_clause = clause.strip().strip(",.")
    for column in columns:
        if column.lower() == normalized_clause.lower():
            return [str(column)]
    return []


def _extract_aggregations(
    user_request: str,
    columns: Sequence[str],
) -> list[AggregationSpec]:
    normalized_request = user_request.lower()
    aggregation_keywords = {
        "sum": ("sum", "total"),
        "avg": ("avg", "average", "mean"),
        "min": ("min", "minimum", "lowest"),
        "max": ("max", "maximum", "highest"),
        "count": ("count",),
        "median": ("median",),
    }
    matched_columns = _match_columns(user_request, columns)
    aggregations: list[AggregationSpec] = []

    for operation, keywords in aggregation_keywords.items():
        if not any(re.search(rf"\b{re.escape(keyword)}\b", normalized_request) for keyword in keywords):
            continue

        column_name = None
        for keyword in keywords:
            keyword_match = re.search(
                rf"\b{re.escape(keyword)}\b(?:\s+of)?\s+([A-Za-z_][\w\s$#@-]*)",
                user_request,
                re.I,
            )
            if keyword_match is None:
                continue
            candidate_columns = _match_columns(keyword_match.group(1), columns)
            if candidate_columns:
                column_name = candidate_columns[0]
                break

        if column_name is None and matched_columns:
            column_name = matched_columns[0]
            if operation == "count" and "row" in normalized_request:
                column_name = None

        if operation == "count" and "row" in normalized_request:
            aggregations.append(AggregationSpec(operation="count"))
            continue

        if column_name is None and operation != "count":
            continue

        aggregations.append(AggregationSpec(operation=operation, column_name=column_name))

    return _deduplicate_aggregations(aggregations)


def _deduplicate_aggregations(
    aggregations: Sequence[AggregationSpec],
) -> list[AggregationSpec]:
    seen: set[tuple[str, str | None]] = set()
    result: list[AggregationSpec] = []
    for aggregation in aggregations:
        key = (aggregation.operation, aggregation.column_name)
        if key in seen:
            continue
        seen.add(key)
        result.append(aggregation)
    return result


def _extract_filters(
    user_request: str,
    columns: Sequence[str],
) -> list[FilterCondition]:
    filters: list[tuple[int, FilterCondition]] = []
    for column in sorted(columns, key=len, reverse=True):
        pattern = re.escape(str(column)).replace(r"\ ", r"\s+")
        for operator in (">=", "<=", "!=", "==", "=", ">", "<"):
            regex = re.compile(
                rf"(?P<column>{pattern})\s*{re.escape(operator)}\s*(?P<value>'[^']*'|\"[^\"]*\"|[^\s,]+)",
                re.I,
            )
            for match in regex.finditer(user_request):
                filters.append(
                    (
                        match.start(),
                        FilterCondition(
                            column_name=str(column),
                            operator=operator,
                            value=_strip_quotes(match.group("value")),
                        ),
                    )
                )

        word_operators = {
            "contains": "contains",
            "starts with": "starts_with",
            "ends with": "ends_with",
            "is": "is",
        }
        for phrase, operator in word_operators.items():
            regex = re.compile(
                rf"(?P<column>{pattern})\s+{re.escape(phrase)}\s+(?P<value>'[^']*'|\"[^\"]*\"|[^\s,]+)",
                re.I,
            )
            for match in regex.finditer(user_request):
                filters.append(
                    (
                        match.start(),
                        FilterCondition(
                            column_name=str(column),
                            operator=operator,
                            value=_strip_quotes(match.group("value")),
                        ),
                    )
                )

    filters.sort(key=lambda item: item[0])
    return [filter_condition for _, filter_condition in filters]


def _is_ascending_request(user_request: str) -> bool:
    normalized_request = user_request.lower()
    descending_markers = ("desc", "descending", "highest", "largest")
    if any(marker in normalized_request for marker in descending_markers):
        return False
    ascending_markers = ("asc", "ascending", "lowest", "smallest")
    if any(marker in normalized_request for marker in ascending_markers):
        return True
    return True


def _strip_quotes(value: str) -> str:
    return value.strip().strip("'").strip('"')


def _serialize_tool_payload(payload: dict[str, Any]) -> str:
    return json.dumps(_to_serializable(payload), indent=2, sort_keys=True)


def _to_serializable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_serializable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_serializable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_serializable(item) for item in value]
    return to_json_safe(value)
