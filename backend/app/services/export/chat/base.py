"""Contracts for conversation exports.

``ChatExportBundle`` is the single input every chat exporter receives, built once
from a :class:`ConversationResponse` by :func:`build_chat_bundle`. It aggregates
every visual artifact the conversation produced, in message order. The
:class:`ChatExporter` / :class:`ChatExporterRegistry` pair mirrors the dataset
export contract so a new chat format is one subclass plus one registration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from app.schemas.export_schema import ExportFormatDescriptor
from app.schemas.visualization_schema import (
    ChartArtifact,
    ConversationResponse,
    DataTableArtifact,
    KpiCardArtifact,
)
from app.services.export.base import ExportArtifact


@dataclass(frozen=True)
class ChatExportBundle:
    """Every artifact a chat exporter may need, aggregated once, in order."""

    title: str
    session_id: str
    generated_at: datetime
    message_count: int
    kpi_cards: list[KpiCardArtifact] = field(default_factory=list)
    charts: list[ChartArtifact] = field(default_factory=list)
    tables: list[DataTableArtifact] = field(default_factory=list)
    sql_snippets: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.kpi_cards or self.charts or self.tables or self.sql_snippets)


class ChatExporter(ABC):
    """Base class for a single conversation export format."""

    format_key: str
    label: str
    file_extension: str
    media_type: str
    description: str = ""

    @abstractmethod
    def export(self, bundle: ChatExportBundle) -> bytes:
        """Render the conversation artifacts into the format's binary payload."""

    def build_artifact(self, bundle: ChatExportBundle, base_name: str) -> ExportArtifact:
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


class ChatExporterRegistry:
    def __init__(self) -> None:
        self._exporters: dict[str, ChatExporter] = {}

    def register(self, exporter: ChatExporter) -> None:
        self._exporters[exporter.format_key] = exporter

    def get(self, format_key: str) -> ChatExporter:
        from app.services.export.base import UnknownExportFormatError

        exporter = self._exporters.get(format_key)
        if exporter is None:
            raise UnknownExportFormatError(
                f"Unknown export format '{format_key}'. "
                f"Available: {', '.join(sorted(self._exporters)) or 'none'}."
            )
        return exporter

    def list_descriptors(self) -> list[ExportFormatDescriptor]:
        return [exporter.descriptor() for exporter in self._exporters.values()]


def build_chat_bundle(conversation: ConversationResponse) -> ChatExportBundle:
    """Flatten a conversation's per-message artifacts into one export bundle."""
    kpi_cards: list[KpiCardArtifact] = []
    charts: list[ChartArtifact] = []
    tables: list[DataTableArtifact] = []
    sql_snippets: list[str] = []

    for message in conversation.messages:
        visualizations = message.visualizations
        kpi_cards.extend(visualizations.kpi_cards)
        charts.extend(visualizations.charts)
        tables.extend(visualizations.tables)
        generated_sql = (visualizations.generated_sql or "").strip()
        if generated_sql and generated_sql not in sql_snippets:
            sql_snippets.append(generated_sql)

    return ChatExportBundle(
        title=conversation.title or "Conversation",
        session_id=conversation.session_id,
        generated_at=conversation.updated_at,
        message_count=len(conversation.messages),
        kpi_cards=kpi_cards,
        charts=charts,
        tables=tables,
        sql_snippets=sql_snippets,
    )
