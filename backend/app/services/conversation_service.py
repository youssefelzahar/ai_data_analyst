from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from app.ai.memory import ConversationMemory, ConversationMessage
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.visualization_schema import (
    ChartArtifact,
    ConversationMessageResponse,
    ConversationResponse,
    ConversationSummaryResponse,
    DataTableArtifact,
    KpiCardArtifact,
    VisualizationBundle,
)


class ConversationService:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        conversation_memory: ConversationMemory,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._conversation_memory = conversation_memory

    def hydrate_session(
        self,
        session_id: str,
        selected_data_source_id: str | None = None,
    ) -> None:
        if self._conversation_memory.has_session(session_id):
            return

        conversation = self._conversation_repository.get_or_create_conversation(
            session_id,
            selected_data_source_id,
        )
        messages = [
            ConversationMessage(
                message_id=message.id,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
                metadata=message.metadata_json or {},
            )
            for message in conversation.messages
        ]
        self._conversation_memory.load_session(
            session_id=conversation.id,
            messages=messages,
            context=conversation.context_json or {},
            selected_data_source_id=conversation.selected_data_source_id,
        )

    def sync_selected_data_source(
        self,
        session_id: str,
        selected_data_source_id: str | None,
    ) -> None:
        self._conversation_repository.update_conversation(
            session_id,
            selected_data_source_id=selected_data_source_id,
        )

    def sync_context(self, session_id: str, context: dict[str, Any]) -> None:
        self._conversation_repository.update_conversation(
            session_id,
            context_json=context,
        )

    def save_user_message(self, session_id: str, content: str) -> str:
        message = self._conversation_repository.add_message(
            session_id,
            role="user",
            content=content,
        )
        return message.id

    def save_assistant_message(
        self,
        session_id: str,
        content: str,
        metadata: dict[str, Any],
        visualizations: VisualizationBundle,
    ) -> str:
        message = self._conversation_repository.add_message(
            session_id,
            role="assistant",
            content=content,
            metadata_json=metadata,
        )
        self._persist_visualizations(session_id, message.id, visualizations)
        return message.id

    def list_conversations(self) -> list[ConversationSummaryResponse]:
        conversations = self._conversation_repository.list_conversations()
        summaries: list[ConversationSummaryResponse] = []
        for conversation in conversations:
            last_message = conversation.messages[-1] if conversation.messages else None
            summaries.append(
                ConversationSummaryResponse(
                    session_id=conversation.id,
                    title=conversation.title,
                    selected_data_source_id=conversation.selected_data_source_id,
                    updated_at=conversation.updated_at,
                    message_count=len(conversation.messages),
                    last_message_preview=(
                        last_message.content[:120] if last_message is not None else None
                    ),
                )
            )
        return summaries

    def get_conversation(self, session_id: str) -> ConversationResponse | None:
        conversation = self._conversation_repository.get_conversation(session_id)
        if conversation is None:
            return None

        artifacts_by_message_id = defaultdict(list)
        for artifact in conversation.artifacts:
            if artifact.message_id is not None:
                artifacts_by_message_id[artifact.message_id].append(artifact)

        messages = [
            ConversationMessageResponse(
                id=message.id,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
                metadata=message.metadata_json or {},
                visualizations=self._build_visualization_bundle(
                    artifacts_by_message_id.get(message.id, [])
                ),
            )
            for message in conversation.messages
        ]

        return ConversationResponse(
            session_id=conversation.id,
            title=conversation.title,
            selected_data_source_id=conversation.selected_data_source_id,
            context=conversation.context_json or {},
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=messages,
        )

    def _persist_visualizations(
        self,
        session_id: str,
        message_id: str,
        visualizations: VisualizationBundle,
    ) -> None:
        for card in visualizations.kpi_cards:
            self._conversation_repository.add_artifact(
                session_id,
                message_id=message_id,
                artifact_type=card.artifact_type,
                title=card.title,
                payload_json=card.model_dump(mode="json"),
            )
        for table in visualizations.tables:
            self._conversation_repository.add_artifact(
                session_id,
                message_id=message_id,
                artifact_type=table.artifact_type,
                title=table.title,
                payload_json=table.model_dump(mode="json"),
            )
        for chart in visualizations.charts:
            self._conversation_repository.add_artifact(
                session_id,
                message_id=message_id,
                artifact_type=chart.artifact_type,
                title=chart.title,
                payload_json=chart.model_dump(mode="json"),
            )

    @staticmethod
    def _build_visualization_bundle(artifacts: Sequence[Any]) -> VisualizationBundle:
        kpi_cards = [
            KpiCardArtifact.model_validate(artifact.payload_json)
            for artifact in artifacts
            if artifact.artifact_type == "kpi_card"
        ]
        tables = [
            DataTableArtifact.model_validate(artifact.payload_json)
            for artifact in artifacts
            if artifact.artifact_type == "data_table"
        ]
        charts = [
            ChartArtifact.model_validate(artifact.payload_json)
            for artifact in artifacts
            if artifact.artifact_type == "chart"
        ]
        return VisualizationBundle(
            kpi_cards=kpi_cards,
            tables=tables,
            charts=charts,
        )
