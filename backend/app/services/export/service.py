"""Top-level export orchestration.

Builds the shared :class:`ExportBundle` once (report + dataframe + aggregation
tables) and dispatches it to the requested exporter. Everything is derived from
existing profiling / analysis / visualization results — no data is recomputed
beyond lightweight summarization for the workbook.
"""

from __future__ import annotations

import re

import pandas as pd

from app.db.models.data_source_model import DataSource
from app.schemas.export_schema import ExportFormatDescriptor
from app.services.dataset_operations_service import DatasetOperationsService
from app.services.export.base import (
    AggregationTable,
    ExportArtifact,
    ExportBundle,
    ExporterRegistry,
)
from app.services.export.excel_exporter import ExcelExporter
from app.services.export.pdf_exporter import PdfExporter
from app.services.export.powerbi_exporter import PowerBiExporter
from app.services.export.report_builder import ExportReportBuilder
from app.services.json_safe import to_json_safe

_MAX_VALUE_COUNT_COLUMNS = 5
_MAX_VALUE_COUNT_ROWS = 15
_MAX_GROUP_ROWS = 20
_MAX_CATEGORY_CARDINALITY = 50


def build_default_exporter_registry() -> ExporterRegistry:
    registry = ExporterRegistry()
    registry.register(PdfExporter())
    registry.register(ExcelExporter())
    registry.register(PowerBiExporter())
    return registry


class ExportService:
    def __init__(
        self,
        report_builder: ExportReportBuilder,
        dataset_operations_service: DatasetOperationsService,
        registry: ExporterRegistry | None = None,
    ) -> None:
        self._report_builder = report_builder
        self._dataset_operations_service = dataset_operations_service
        self._registry = registry or build_default_exporter_registry()

    def list_formats(self) -> list[ExportFormatDescriptor]:
        return self._registry.list_descriptors()

    def build_report(
        self,
        data_source: DataSource,
        table_name: str | None = None,
        version_id: str | None = None,
    ):
        return self._report_builder.build(data_source, table_name, version_id)

    def build_bundle(
        self,
        data_source: DataSource,
        table_name: str | None = None,
        version_id: str | None = None,
    ) -> ExportBundle:
        report = self._report_builder.build(data_source, table_name, version_id)
        dataframe = self._dataset_operations_service.load_dataframe(
            data_source, table_name, version_id
        )
        aggregations = _build_aggregations(dataframe, report)
        return ExportBundle(report=report, dataframe=dataframe, aggregations=aggregations)

    def export(
        self,
        data_source: DataSource,
        format_key: str,
        table_name: str | None = None,
        version_id: str | None = None,
    ) -> ExportArtifact:
        exporter = self._registry.get(format_key)  # raises UnknownExportFormatError
        bundle = self.build_bundle(data_source, table_name, version_id)
        base_name = _safe_base_name(bundle.report.dataset_summary.dataset_name)
        return exporter.build_artifact(bundle, base_name)


def _build_aggregations(dataframe: pd.DataFrame, report) -> list[AggregationTable]:
    profile = report.profiling
    tables: list[AggregationTable] = []

    numeric_columns = [stat.column_name for stat in profile.numeric_statistics]
    if numeric_columns:
        rows = []
        for column in numeric_columns:
            series = pd.to_numeric(dataframe[column], errors="coerce")
            rows.append(
                {
                    "Column": column,
                    "Sum": to_json_safe(series.sum()),
                    "Mean": _round(series.mean()),
                    "Min": to_json_safe(series.min()),
                    "Max": to_json_safe(series.max()),
                    "Median": _round(series.median()),
                }
            )
        tables.append(
            AggregationTable(
                title="Numeric column aggregates",
                columns=["Column", "Sum", "Mean", "Min", "Max", "Median"],
                rows=rows,
            )
        )

    for stat in profile.categorical_statistics[:_MAX_VALUE_COUNT_COLUMNS]:
        if stat.unique_count > _MAX_CATEGORY_CARDINALITY:
            continue
        counts = dataframe[stat.column_name].value_counts().head(_MAX_VALUE_COUNT_ROWS)
        rows = [{"Value": to_json_safe(value), "Count": int(count)} for value, count in counts.items()]
        tables.append(
            AggregationTable(
                title=f"Value counts — {stat.column_name}",
                columns=["Value", "Count"],
                rows=rows,
            )
        )

    if profile.categorical_statistics and numeric_columns:
        category = profile.categorical_statistics[0].column_name
        measure = numeric_columns[0]
        grouped = (
            pd.to_numeric(dataframe[measure], errors="coerce")
            .groupby(dataframe[category], dropna=False)
            .sum()
            .sort_values(ascending=False)
            .head(_MAX_GROUP_ROWS)
        )
        rows = [
            {category: to_json_safe(value), f"Sum of {measure}": _round(total)}
            for value, total in grouped.items()
        ]
        tables.append(
            AggregationTable(
                title=f"{measure} by {category}",
                columns=[category, f"Sum of {measure}"],
                rows=rows,
            )
        )

    return tables


def _round(value) -> float | None:
    safe = to_json_safe(value)
    if isinstance(safe, (int, float)):
        return round(float(safe), 4)
    return safe


def _safe_base_name(dataset_name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", dataset_name.strip()).strip("-").lower()
    return slug or "analysis-report"
