from app.db.models.data_source_model import DataSource
from app.schemas.data_source_schema import DatasetPreviewResponse
from app.services.json_safe import to_json_safe
from app.services.profiling.loaders import DatasetLoader, DatasetLoadError, UnsupportedDataSourceError

__all__ = ["DatasetPreviewService", "UnsupportedDataSourceError", "DatasetLoadError"]


class DatasetPreviewService:
    """Reads an uploaded dataset file and summarizes its shape and contents."""

    def __init__(self, dataset_loader: DatasetLoader) -> None:
        self._dataset_loader = dataset_loader

    def get_preview(self, data_source: DataSource, preview_row_count: int) -> DatasetPreviewResponse:
        dataframe = self._dataset_loader.load_file(data_source)

        row_count, column_count = dataframe.shape
        preview_rows = [
            {column: to_json_safe(value) for column, value in row.items()}
            for row in dataframe.head(preview_row_count).to_dict(orient="records")
        ]

        return DatasetPreviewResponse(
            row_count=row_count,
            column_count=column_count,
            column_names=list(dataframe.columns),
            dtypes={column: str(dtype) for column, dtype in dataframe.dtypes.items()},
            missing_value_counts={
                column: int(count) for column, count in dataframe.isna().sum().items()
            },
            preview_rows=preview_rows,
        )
