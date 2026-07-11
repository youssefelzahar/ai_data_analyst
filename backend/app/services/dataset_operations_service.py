from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.db.models.data_source_model import DataSource
from app.schemas.data_profile_schema import DataProfileResponse
from app.services.dataset_preview_service import build_preview_response
from app.services.dataset_frame_service import DatasetFrameService
from app.services.json_safe import to_json_safe
from app.services.profiling.column_analysis import is_numeric_column
from app.services.profiling.service import DataProfileService


class DatasetOperationError(Exception):
    """Raised when a dataset operation cannot be completed."""


class UnknownDatasetColumnError(DatasetOperationError):
    """Raised when an operation references a missing dataset column."""


class UnsupportedAggregationError(DatasetOperationError):
    """Raised when an unsupported aggregation is requested."""


class InvalidDatasetFilterError(DatasetOperationError):
    """Raised when a filter condition is malformed or unsupported."""


@dataclass(frozen=True)
class FilterCondition:
    column_name: str
    operator: str
    value: Any


@dataclass(frozen=True)
class AggregationSpec:
    operation: str
    column_name: str | None = None
    alias: str | None = None


class DatasetOperationsService:
    """Reusable dataset operations that work through the shared data-source abstraction."""

    _PANDAS_AGGREGATIONS = {
        "sum": "sum",
        "avg": "mean",
        "min": "min",
        "max": "max",
        "count": "count",
        "median": "median",
    }

    def __init__(
        self,
        dataset_frame_service: DatasetFrameService,
        data_profile_service: DataProfileService,
    ) -> None:
        self._dataset_frame_service = dataset_frame_service
        self._data_profile_service = data_profile_service

    def load_dataframe(
        self,
        data_source: DataSource,
        table_name: str | None = None,
    ) -> pd.DataFrame:
        return self._dataset_frame_service.load_dataframe(data_source, table_name)

    def preview(
        self,
        data_source: DataSource,
        table_name: str | None = None,
        row_count: int = 10,
    ) -> dict[str, Any]:
        dataframe = self.load_dataframe(data_source, table_name)
        preview = build_preview_response(dataframe, row_count)
        return preview.model_dump(mode="json")

    def summary(
        self,
        data_source: DataSource,
        table_name: str | None = None,
    ) -> dict[str, Any]:
        profile = self._data_profile_service.get_profile(data_source, table_name)
        return {
            "overview": profile.overview.model_dump(mode="json"),
            "numeric_statistics": [
                statistics.model_dump(mode="json")
                for statistics in profile.numeric_statistics
            ],
            "categorical_statistics": [
                statistics.model_dump(mode="json")
                for statistics in profile.categorical_statistics
            ],
            "data_quality": profile.data_quality.model_dump(mode="json"),
        }

    def column_information(
        self,
        data_source: DataSource,
        table_name: str | None = None,
        column_names: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        profile = self._data_profile_service.get_profile(data_source, table_name)
        requested_columns = set(column_names or [column.column_name for column in profile.columns])
        available_columns = {column.column_name for column in profile.columns}
        missing_columns = sorted(requested_columns - available_columns)
        if missing_columns:
            raise UnknownDatasetColumnError(
                f"Unknown column(s): {', '.join(missing_columns)}."
            )

        numeric_by_column = {
            statistics.column_name: statistics.model_dump(mode="json")
            for statistics in profile.numeric_statistics
        }
        categorical_by_column = {
            statistics.column_name: statistics.model_dump(mode="json")
            for statistics in profile.categorical_statistics
        }

        selected_columns = []
        for column in profile.columns:
            if column.column_name not in requested_columns:
                continue
            selected_columns.append(
                {
                    "profile": column.model_dump(mode="json"),
                    "numeric_statistics": numeric_by_column.get(column.column_name),
                    "categorical_statistics": categorical_by_column.get(column.column_name),
                }
            )

        return {"columns": selected_columns}

    def value_counts(
        self,
        data_source: DataSource,
        column_name: str,
        table_name: str | None = None,
        limit: int = 10,
        include_nulls: bool = False,
    ) -> dict[str, Any]:
        dataframe = self.load_dataframe(data_source, table_name)
        self._require_columns(dataframe, [column_name])

        series = dataframe[column_name]
        counts = series.value_counts(dropna=not include_nulls).head(limit)
        rows = [
            {"value": to_json_safe(index), "count": int(count)}
            for index, count in counts.items()
        ]
        return {
            "column_name": column_name,
            "unique_value_count": int(series.nunique(dropna=not include_nulls)),
            "value_counts": rows,
        }

    def group_by(
        self,
        data_source: DataSource,
        group_columns: Sequence[str],
        aggregations: Sequence[AggregationSpec],
        table_name: str | None = None,
        limit: int = 50,
        ascending: bool = False,
    ) -> dict[str, Any]:
        dataframe = self.load_dataframe(data_source, table_name)
        self._require_columns(dataframe, group_columns)

        grouped = dataframe.groupby(list(group_columns), dropna=False)
        result = pd.DataFrame(index=grouped.size().index)

        requested_aggregations = list(aggregations) or [AggregationSpec("count")]
        for index, aggregation in enumerate(requested_aggregations):
            alias = aggregation.alias or self._build_aggregation_alias(aggregation, index)
            if aggregation.operation == "count" and aggregation.column_name is None:
                result[alias] = grouped.size()
                continue

            if aggregation.column_name is None:
                raise UnsupportedAggregationError(
                    f"Aggregation '{aggregation.operation}' requires a column name."
                )

            self._require_columns(dataframe, [aggregation.column_name])
            pandas_operation = self._PANDAS_AGGREGATIONS.get(aggregation.operation)
            if pandas_operation is None:
                raise UnsupportedAggregationError(
                    f"Unsupported aggregation '{aggregation.operation}'."
                )
            result[alias] = grouped[aggregation.column_name].agg(pandas_operation)

        result = result.reset_index()
        value_columns = [column for column in result.columns if column not in group_columns]
        if value_columns:
            result = result.sort_values(
                by=value_columns[0],
                ascending=ascending,
                na_position="last",
            )

        return {
            "group_columns": list(group_columns),
            "aggregations": [aggregation.__dict__ for aggregation in requested_aggregations],
            "row_count": int(len(result)),
            "rows": self._records_to_json_safe(result.head(limit)),
        }

    def correlation(
        self,
        data_source: DataSource,
        column_names: Sequence[str] | None = None,
        table_name: str | None = None,
        method: str = "pearson",
    ) -> dict[str, Any]:
        dataframe = self.load_dataframe(data_source, table_name)
        requested_columns = list(column_names or [])
        if requested_columns:
            self._require_columns(dataframe, requested_columns)
            numeric_dataframe = dataframe[requested_columns]
        else:
            numeric_dataframe = dataframe.select_dtypes(include=["number"]).copy()

        numeric_columns = [
            column for column in numeric_dataframe.columns if is_numeric_column(numeric_dataframe[column])
        ]
        if len(numeric_columns) < 2:
            raise DatasetOperationError(
                "Correlation requires at least two numeric columns."
            )

        correlation_matrix = numeric_dataframe[numeric_columns].corr(method=method)
        matrix = {
            row_name: {
                column_name: to_json_safe(value)
                for column_name, value in row.items()
            }
            for row_name, row in correlation_matrix.to_dict(orient="index").items()
        }
        return {
            "method": method,
            "columns": numeric_columns,
            "correlation_matrix": matrix,
        }

    def filter_rows(
        self,
        data_source: DataSource,
        filters: Sequence[FilterCondition],
        table_name: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        dataframe = self.load_dataframe(data_source, table_name)
        filtered_dataframe = dataframe.copy()

        for filter_condition in filters:
            self._require_columns(filtered_dataframe, [filter_condition.column_name])
            filtered_dataframe = filtered_dataframe[
                self._build_filter_mask(filtered_dataframe, filter_condition)
            ]

        return {
            "applied_filters": [filter_condition.__dict__ for filter_condition in filters],
            "row_count": int(len(filtered_dataframe)),
            "rows": self._records_to_json_safe(filtered_dataframe.head(limit)),
        }

    def sort_rows(
        self,
        data_source: DataSource,
        column_name: str,
        table_name: str | None = None,
        ascending: bool = True,
        limit: int = 50,
    ) -> dict[str, Any]:
        dataframe = self.load_dataframe(data_source, table_name)
        self._require_columns(dataframe, [column_name])
        sorted_dataframe = dataframe.sort_values(
            by=column_name,
            ascending=ascending,
            na_position="last",
        )
        return {
            "column_name": column_name,
            "direction": "asc" if ascending else "desc",
            "row_count": int(len(sorted_dataframe)),
            "rows": self._records_to_json_safe(sorted_dataframe.head(limit)),
        }

    def aggregate(
        self,
        data_source: DataSource,
        aggregations: Sequence[AggregationSpec],
        table_name: str | None = None,
    ) -> dict[str, Any]:
        dataframe = self.load_dataframe(data_source, table_name)
        requested_aggregations = list(aggregations)
        if not requested_aggregations:
            raise UnsupportedAggregationError("At least one aggregation is required.")

        result: dict[str, Any] = {}
        for index, aggregation in enumerate(requested_aggregations):
            alias = aggregation.alias or self._build_aggregation_alias(aggregation, index)
            result[alias] = self._compute_aggregation(dataframe, aggregation)

        return {"aggregations": [aggregation.__dict__ for aggregation in requested_aggregations], "results": result}

    def _compute_aggregation(
        self,
        dataframe: pd.DataFrame,
        aggregation: AggregationSpec,
    ) -> Any:
        if aggregation.operation == "count" and aggregation.column_name is None:
            return int(len(dataframe))

        if aggregation.column_name is None:
            raise UnsupportedAggregationError(
                f"Aggregation '{aggregation.operation}' requires a column name."
            )

        self._require_columns(dataframe, [aggregation.column_name])
        series = dataframe[aggregation.column_name]
        pandas_operation = self._PANDAS_AGGREGATIONS.get(aggregation.operation)
        if pandas_operation is None:
            raise UnsupportedAggregationError(
                f"Unsupported aggregation '{aggregation.operation}'."
            )

        if aggregation.operation != "count" and not is_numeric_column(series):
            raise UnsupportedAggregationError(
                f"Aggregation '{aggregation.operation}' requires a numeric column."
            )

        value = getattr(series, pandas_operation)()
        return to_json_safe(value)

    def _build_filter_mask(
        self,
        dataframe: pd.DataFrame,
        filter_condition: FilterCondition,
    ) -> pd.Series:
        series = dataframe[filter_condition.column_name]
        value = self._coerce_value(series, filter_condition.value)
        operator = filter_condition.operator

        if operator in {"=", "==", "is"}:
            return series == value
        if operator == "!=":
            return series != value
        if operator == ">":
            return series > value
        if operator == ">=":
            return series >= value
        if operator == "<":
            return series < value
        if operator == "<=":
            return series <= value
        if operator == "contains":
            return series.astype("string").str.contains(str(value), case=False, na=False)
        if operator == "starts_with":
            return series.astype("string").str.startswith(str(value), na=False)
        if operator == "ends_with":
            return series.astype("string").str.endswith(str(value), na=False)

        raise InvalidDatasetFilterError(f"Unsupported filter operator '{operator}'.")

    @staticmethod
    def _coerce_value(series: pd.Series, value: Any) -> Any:
        if value is None:
            return None
        if pd.api.types.is_bool_dtype(series):
            normalized_value = str(value).strip().lower()
            if normalized_value in {"true", "1", "yes"}:
                return True
            if normalized_value in {"false", "0", "no"}:
                return False
        if is_numeric_column(series):
            numeric_value = pd.to_numeric([value], errors="raise")[0]
            return to_json_safe(numeric_value)
        if pd.api.types.is_datetime64_any_dtype(series):
            return pd.to_datetime(value)
        return str(value)

    @staticmethod
    def _build_aggregation_alias(aggregation: AggregationSpec, index: int) -> str:
        if aggregation.column_name:
            return f"{aggregation.operation}_{aggregation.column_name}"
        return aggregation.alias or f"{aggregation.operation}_{index + 1}"

    @staticmethod
    def _require_columns(dataframe: pd.DataFrame, column_names: Sequence[str]) -> None:
        available_columns = set(dataframe.columns)
        missing_columns = sorted(set(column_names) - available_columns)
        if missing_columns:
            raise UnknownDatasetColumnError(
                f"Unknown column(s): {', '.join(missing_columns)}."
            )

    @staticmethod
    def _records_to_json_safe(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        return [
            {column: to_json_safe(value) for column, value in row.items()}
            for row in dataframe.to_dict(orient="records")
        ]
