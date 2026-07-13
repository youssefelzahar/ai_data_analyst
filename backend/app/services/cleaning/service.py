from io import BytesIO

import pandas as pd

from app.db.models.data_source_model import DataSource
from app.db.models.dataset_version_model import DatasetVersion
from app.repositories.dataset_version_repository import DatasetVersionRepository
from app.schemas.data_cleaning_schema import (
    CleaningMethodDescriptor,
    CleaningMethodsCatalog,
    CleaningRecommendationsResponse,
    DatasetVersionResponse,
    OperationSpec,
    PipelinePreviewResponse,
    PipelineStepResult,
)
from app.services.cleaning.pipeline import CleaningPipelineExecutor
from app.services.cleaning.recommendations import CleaningRecommendationService
from app.services.cleaning.strategy import CleaningStrategyRegistry
from app.services.dataset_frame_service import DatasetFrameService
from app.services.dataset_preview_service import build_preview_response
from app.services.profiling.service import DataProfileService
from app.storage.base import FileStorage

_PREVIEW_SAMPLE_ROW_COUNT = 10


class NoVersionToUndoError(Exception):
    """Raised when undo is requested but no derived version exists yet."""


class DataCleaningService:
    """Recommend -> preview -> apply cleaning pipelines for any DataSource.

    The original DataSource file is never modified: `apply_pipeline` always
    writes a brand-new file and records it as the next `DatasetVersion`.
    """

    def __init__(
        self,
        dataset_frame_service: DatasetFrameService,
        data_profile_service: DataProfileService,
        recommendation_service: CleaningRecommendationService,
        strategy_registry: CleaningStrategyRegistry,
        dataset_version_repository: DatasetVersionRepository,
        file_storage: FileStorage,
    ) -> None:
        self._dataset_frame_service = dataset_frame_service
        self._data_profile_service = data_profile_service
        self._recommendation_service = recommendation_service
        self._strategy_registry = strategy_registry
        self._dataset_version_repository = dataset_version_repository
        self._file_storage = file_storage
        self._pipeline_executor = CleaningPipelineExecutor(strategy_registry)

    def get_recommendations(
        self, data_source: DataSource, table_name: str | None = None
    ) -> CleaningRecommendationsResponse:
        return self._recommendation_service.recommend(data_source, table_name)

    def list_available_methods(self) -> CleaningMethodsCatalog:
        return CleaningMethodsCatalog(
            methods=[
                CleaningMethodDescriptor(key=strategy.key, label=strategy.label, category=strategy.category)
                for strategy in self._strategy_registry.list_all()
            ]
        )

    def preview_pipeline(
        self,
        data_source: DataSource,
        table_name: str | None,
        operations: list[OperationSpec],
    ) -> PipelinePreviewResponse:
        before_dataframe = self._load_current_dataframe(data_source, table_name)
        after_dataframe, outcomes = self._pipeline_executor.run(before_dataframe, operations)

        before_profile = self._data_profile_service.build_profile_from_dataframe(
            before_dataframe, dataset_name=data_source.name, source_type=data_source.source_type
        )
        after_profile = self._data_profile_service.build_profile_from_dataframe(
            after_dataframe, dataset_name=data_source.name, source_type=data_source.source_type
        )

        return PipelinePreviewResponse(
            steps=[
                PipelineStepResult(
                    operation_key=operation_spec.operation_key,
                    column_name=operation_spec.column_name,
                    affected_row_count=outcome.affected_row_count,
                    affected_column_count=outcome.affected_column_count,
                    message=outcome.message,
                )
                for operation_spec, outcome in zip(operations, outcomes)
            ],
            before_overview=before_profile.overview,
            after_overview=after_profile.overview,
            sample_before_rows=self._sample_rows(before_dataframe),
            sample_after_rows=self._sample_rows(after_dataframe),
        )

    def apply_pipeline(
        self,
        data_source: DataSource,
        table_name: str | None,
        operations: list[OperationSpec],
    ) -> DatasetVersionResponse:
        before_dataframe = self._load_current_dataframe(data_source, table_name)
        after_dataframe, outcomes = self._pipeline_executor.run(before_dataframe, operations)

        next_version_number = _next_version_number(self._dataset_version_repository, data_source.id)
        csv_payload = after_dataframe.to_csv(index=False).encode("utf-8")
        stored_filename = f"{data_source.id}-cleaned-{next_version_number}.csv"
        file_size_bytes = self._file_storage.save_file(
            file_stream=BytesIO(csv_payload),
            stored_filename=stored_filename,
            max_size_bytes=len(csv_payload) + 1,
        )

        row_count, column_count = after_dataframe.shape
        version = DatasetVersion(
            data_source_id=data_source.id,
            version_number=next_version_number,
            stored_filename=stored_filename,
            file_format="csv",
            file_size_bytes=file_size_bytes,
            row_count=row_count,
            column_count=column_count,
            operations_summary=[
                {
                    "operation_key": operation_spec.operation_key,
                    "column_name": operation_spec.column_name,
                    "params": operation_spec.params,
                    "message": outcome.message,
                }
                for operation_spec, outcome in zip(operations, outcomes)
            ],
        )
        saved_version = self._dataset_version_repository.add_version(version)
        return DatasetVersionResponse.model_validate(saved_version)

    def list_versions(self, data_source: DataSource) -> list[DatasetVersionResponse]:
        versions = self._dataset_version_repository.list_for_data_source(data_source.id)
        return [DatasetVersionResponse.model_validate(version) for version in versions]

    def undo_last_version(self, data_source: DataSource) -> None:
        latest_version = self._dataset_version_repository.get_latest(data_source.id)
        if latest_version is None:
            raise NoVersionToUndoError("There is no applied cleaning version to undo.")
        self._file_storage.delete_file(latest_version.stored_filename)
        self._dataset_version_repository.delete(latest_version)

    def _load_current_dataframe(self, data_source: DataSource, table_name: str | None) -> pd.DataFrame:
        latest_version = self._dataset_version_repository.get_latest(data_source.id)
        if latest_version is None:
            return self._dataset_frame_service.load_dataframe(data_source, table_name)
        file_path = self._file_storage.get_file_path(latest_version.stored_filename)
        return pd.read_csv(file_path)

    def _sample_rows(self, dataframe: pd.DataFrame) -> list[dict]:
        preview = build_preview_response(dataframe, _PREVIEW_SAMPLE_ROW_COUNT)
        return preview.preview_rows


def _next_version_number(repository: DatasetVersionRepository, data_source_id: str) -> int:
    latest_version = repository.get_latest(data_source_id)
    return (latest_version.version_number if latest_version else 0) + 1
