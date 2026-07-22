"""Orchestrates conversation exports.

The single place to register a new chat format is
:func:`build_default_chat_exporter_registry`.
"""

from __future__ import annotations

from app.schemas.export_schema import ExportFormatDescriptor
from app.schemas.visualization_schema import ConversationResponse
from app.services.export.base import ExportArtifact
from app.services.export.chat.base import (
    ChatExporterRegistry,
    build_chat_bundle,
)
from app.services.export.chat.excel_exporter import ChatExcelExporter
from app.services.export.chat.pdf_exporter import ChatPdfExporter
from app.services.export.chat.powerbi_exporter import ChatPowerBiExporter
from app.services.export.service import _safe_base_name


def build_default_chat_exporter_registry() -> ChatExporterRegistry:
    registry = ChatExporterRegistry()
    registry.register(ChatPdfExporter())
    registry.register(ChatExcelExporter())
    registry.register(ChatPowerBiExporter())
    return registry


class ChatExportService:
    """Turns a conversation into a downloadable artifact in a chosen format."""

    def __init__(self, registry: ChatExporterRegistry | None = None) -> None:
        self._registry = registry or build_default_chat_exporter_registry()

    def list_formats(self) -> list[ExportFormatDescriptor]:
        return self._registry.list_descriptors()

    def export(
        self, conversation: ConversationResponse, format_key: str
    ) -> ExportArtifact:
        exporter = self._registry.get(format_key)
        bundle = build_chat_bundle(conversation)
        base_name = _safe_base_name(bundle.title)
        return exporter.build_artifact(bundle, base_name)
