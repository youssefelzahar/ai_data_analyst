"""Assemble a complete :class:`ExportReport` by reusing existing results.

The builder never runs its own profiling / cleaning / charting logic. It calls
the same services the rest of the app uses (profiling, dataset operations,
visualization) so the report reflects exactly what the user already sees, then
layers deterministic insights on top.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.models.data_source_model import DataSource
from app.repositories.dataset_version_repository import DatasetVersionRepository
from app.schemas.export_schema import (
    CleaningOperationSummary,
    CleaningSummarySection,
    CleaningVersionSummary,
    DatasetSummarySection,
    ExportReport,
    VisualizationSection,
)
from app.services.export.insights import build_insights, build_recommendations
from app.services.profiling.service import DataProfileService
from app.services.visualization_service import VisualizationRequest, VisualizationService

# A request that exercises every chart type the visualization service supports,
# plus KPI cards and a data table, so the report bundle is a full dashboard.
_DASHBOARD_REQUEST = (
    "dashboard with kpi cards, bar chart, line chart, pie chart, scatter plot, "
    "histogram, box plot, correlation heatmap and a data table"
)


class ExportReportBuilder:
    def __init__(
        self,
        data_profile_service: DataProfileService,
        visualization_service: VisualizationService,
        dataset_version_repository: DatasetVersionRepository,
    ) -> None:
        self._data_profile_service = data_profile_service
        self._visualization_service = visualization_service
        self._dataset_version_repository = dataset_version_repository

    def build(
        self,
        data_source: DataSource,
        table_name: str | None = None,
        version_id: str | None = None,
    ) -> ExportReport:
        profile = self._data_profile_service.get_profile(data_source, table_name, version_id)

        bundle = self._visualization_service.build_visualization_bundle(
            data_source,
            VisualizationRequest(
                user_request=_DASHBOARD_REQUEST,
                table_name=table_name,
                version_id=version_id,
            ),
        )

        cleaning_summary = self._build_cleaning_summary(data_source, version_id)
        dataset_summary = self._build_dataset_summary(profile, cleaning_summary, version_id)

        return ExportReport(
            generated_at=datetime.now(timezone.utc),
            dataset_summary=dataset_summary,
            profiling=profile,
            cleaning_summary=cleaning_summary,
            visualizations=VisualizationSection(
                kpi_cards=bundle.kpi_cards,
                charts=bundle.charts,
                tables=bundle.tables,
            ),
            kpi_summary=bundle.kpi_cards,
            insights=build_insights(profile, cleaning_summary),
            recommendations=build_recommendations(profile, cleaning_summary),
            model_performance=None,
        )

    def _build_dataset_summary(
        self,
        profile,
        cleaning_summary: CleaningSummarySection | None,
        version_id: str | None,
    ) -> DatasetSummarySection:
        overview = profile.overview
        total_cells = max(overview.row_count * overview.column_count, 1)
        version_label = None
        if cleaning_summary and cleaning_summary.versions:
            target_number = cleaning_summary.selected_version_number
            match = next(
                (
                    version
                    for version in cleaning_summary.versions
                    if version.version_number == target_number
                ),
                None,
            )
            if match is not None:
                version_label = match.label or f"Version {match.version_number}"
        return DatasetSummarySection(
            dataset_name=overview.dataset_name,
            source_type=str(overview.source_type.value)
            if hasattr(overview.source_type, "value")
            else str(overview.source_type),
            version_id=version_id,
            version_label=version_label,
            row_count=overview.row_count,
            column_count=overview.column_count,
            numeric_column_count=overview.numeric_column_count,
            categorical_column_count=overview.categorical_column_count,
            total_missing_values=overview.total_missing_values,
            missing_percentage=round(overview.total_missing_values / total_cells * 100, 2),
            total_duplicate_rows=overview.total_duplicate_rows,
            memory_usage_bytes=overview.memory_usage_bytes,
            dataset_size_bytes=overview.dataset_size_bytes,
        )

    def _build_cleaning_summary(
        self,
        data_source: DataSource,
        version_id: str | None,
    ) -> CleaningSummarySection | None:
        versions = self._dataset_version_repository.list_for_data_source(data_source.id)
        if not versions:
            return None

        version_summaries = [
            CleaningVersionSummary(
                version_id=version.id,
                version_number=version.version_number,
                label=version.label,
                row_count=version.row_count,
                column_count=version.column_count,
                created_at=version.created_at,
                operations=[
                    CleaningOperationSummary(
                        operation_key=str(operation.get("operation_key", "")),
                        column_name=operation.get("column_name"),
                        message=operation.get("message"),
                        params=operation.get("params") or {},
                    )
                    for operation in (version.operations_summary or [])
                ],
            )
            for version in versions
        ]

        if version_id is not None:
            selected = next(
                (version for version in versions if version.id == version_id), None
            )
            selected_number = selected.version_number if selected else None
        else:
            selected_number = versions[-1].version_number

        return CleaningSummarySection(
            applied=True,
            total_versions=len(versions),
            selected_version_number=selected_number,
            versions=version_summaries,
        )
