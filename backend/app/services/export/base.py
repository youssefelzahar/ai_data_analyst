"""Extensible exporter contract and registry.

Every output format implements :class:`Exporter`. Adding a new format (e.g.
JSON, PowerPoint) is a matter of writing one subclass and registering it — no
other part of the export pipeline changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd

from app.schemas.export_schema import ExportFormatDescriptor, ExportReport


@dataclass(frozen=True)
class AggregationTable:
    """A named tabular analysis result destined for the Excel workbook."""

    title: str
    columns: list[str]
    rows: list[dict]


@dataclass(frozen=True)
class ExportBundle:
    """Everything an exporter may need, computed exactly once.

    ``report`` is the JSON-serializable analysis snapshot; ``dataframe`` is the
    current (optionally versioned) dataset; ``aggregations`` and ``predictions``
    are optional analysis tables. Exporters read only what they need.
    """

    report: ExportReport
    dataframe: pd.DataFrame
    aggregations: list[AggregationTable] = field(default_factory=list)
    predictions: pd.DataFrame | None = None


@dataclass(frozen=True)
class ExportArtifact:
    filename: str
    media_type: str
    content: bytes


class Exporter(ABC):
    """Base class for a single export format."""

    format_key: str
    label: str
    file_extension: str
    media_type: str
    description: str = ""

    @abstractmethod
    def export(self, bundle: ExportBundle) -> bytes:
        """Render the bundle into the format's binary payload."""

    def build_artifact(self, bundle: ExportBundle, base_name: str) -> ExportArtifact:
        return ExportArtifact(
            filename=f"{base_name}.{self.file_extension}",
            media_type=self.media_type,
            content=self.export(bundle),
        )

    def descriptor(self) -> ExportFormatDescriptor:
        return ExportFormatDescriptor(
            key=self.format_key,
            label=self.label,
            file_extension=self.file_extension,
            media_type=self.media_type,
            description=self.description,
        )


class UnknownExportFormatError(Exception):
    """Raised when an export format key is not registered."""


class ExporterRegistry:
    def __init__(self) -> None:
        self._exporters: dict[str, Exporter] = {}

    def register(self, exporter: Exporter) -> None:
        self._exporters[exporter.format_key] = exporter

    def get(self, format_key: str) -> Exporter:
        exporter = self._exporters.get(format_key)
        if exporter is None:
            raise UnknownExportFormatError(
                f"Unknown export format '{format_key}'. "
                f"Available: {', '.join(sorted(self._exporters)) or 'none'}."
            )
        return exporter

    def list_descriptors(self) -> list[ExportFormatDescriptor]:
        return [exporter.descriptor() for exporter in self._exporters.values()]
