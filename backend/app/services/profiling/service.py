import pandas as pd

from app.db.models.data_source_model import DataSource
from app.schemas.data_profile_schema import (
    DataProfileResponse,
    DatasetOverview,
    OutlierRowsResponse,
)
from app.services.dataset_frame_service import DatasetFrameService
from app.services.json_safe import to_json_safe
from app.services.profiling.column_analysis import (
    build_categorical_statistics,
    build_column_profile,
    build_numeric_statistics,
    is_numeric_column,
)
from app.services.profiling.outliers import build_outlier_report, get_outlier_row_indices
from app.services.profiling.quality_checks import build_data_quality_report

_MAX_RETURNED_OUTLIER_ROWS = 500

class UnknownColumnError(Exception):
    """Raised when the requested column doesn't exist in the dataset."""


class NonNumericColumnError(Exception):
    """Raised when outlier detection is requested for a non-numeric column."""


class DataProfileService:
    """Builds a full statistical profile for any supported data source."""

    def __init__(self, dataset_frame_service: DatasetFrameService) -> None:
        self._dataset_frame_service = dataset_frame_service

    def get_profile(self, data_source: DataSource, table_name: str | None = None) -> DataProfileResponse:
        dataframe = self._load_dataframe(data_source, table_name)
        return self._build_profile(
            dataframe,
            dataset_name=data_source.name,
            source_type=data_source.source_type,
            dataset_size_bytes=data_source.file_size_bytes,
        )

    def build_profile_from_dataframe(
        self,
        dataframe: pd.DataFrame,
        dataset_name: str,
        source_type: str,
    ) -> DataProfileResponse:
        """Profile an arbitrary in-memory DataFrame (e.g. an ad-hoc query result)."""
        return self._build_profile(
            dataframe,
            dataset_name=dataset_name,
            source_type=source_type,
            dataset_size_bytes=None,
        )

    def get_outlier_rows(
        self,
        data_source: DataSource,
        column_name: str,
        table_name: str | None = None,
        method: str = "iqr",
    ) -> OutlierRowsResponse:
        dataframe = self._load_dataframe(data_source, table_name)
        if column_name not in dataframe.columns:
            raise UnknownColumnError(f"Column '{column_name}' was not found in this dataset.")

        series = dataframe[column_name]
        if not is_numeric_column(series):
            raise NonNumericColumnError(f"Column '{column_name}' is not numeric.")

        row_indices = get_outlier_row_indices(series, method)
        outlier_rows_dataframe = dataframe.iloc[row_indices[:_MAX_RETURNED_OUTLIER_ROWS]]
        rows = [
            {column: to_json_safe(value) for column, value in row.items()}
            for row in outlier_rows_dataframe.to_dict(orient="records")
        ]

        return OutlierRowsResponse(
            column_name=column_name,
            detection_method=method,
            row_count=len(row_indices),
            rows=rows,
        )

    def _load_dataframe(self, data_source: DataSource, table_name: str | None) -> pd.DataFrame:
        return self._dataset_frame_service.load_dataframe(data_source, table_name)

    def _build_profile(
        self,
        dataframe: pd.DataFrame,
        dataset_name: str,
        source_type: str,
        dataset_size_bytes: int | None,
    ) -> DataProfileResponse:
        row_count, column_count = dataframe.shape

        columns = [build_column_profile(dataframe[name], name) for name in dataframe.columns]
        numeric_statistics = [
            statistics
            for name in dataframe.columns
            if (statistics := build_numeric_statistics(dataframe[name], name)) is not None
        ]
        categorical_statistics = [
            statistics
            for name in dataframe.columns
            if (statistics := build_categorical_statistics(dataframe[name], name)) is not None
        ]
        data_quality = build_data_quality_report(dataframe)
        outliers = [
            build_outlier_report(dataframe[statistics.column_name], statistics.column_name)
            for statistics in numeric_statistics
        ]

        overview = DatasetOverview(
            dataset_name=dataset_name,
            source_type=source_type,
            row_count=row_count,
            column_count=column_count,
            shape=(row_count, column_count),
            memory_usage_bytes=int(dataframe.memory_usage(deep=True).sum()),
            dataset_size_bytes=dataset_size_bytes,
            total_missing_values=int(dataframe.isna().sum().sum()),
            total_duplicate_rows=int(dataframe.duplicated().sum()),
            numeric_column_count=len(numeric_statistics),
            categorical_column_count=len(categorical_statistics),
        )

        return DataProfileResponse(
            overview=overview,
            columns=columns,
            numeric_statistics=numeric_statistics,
            categorical_statistics=categorical_statistics,
            data_quality=data_quality,
            outliers=outliers,
        )
