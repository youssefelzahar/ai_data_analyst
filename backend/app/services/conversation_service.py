from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from app.ai.memory import ConversationMemory, ConversationMessage
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.auth_schema import CurrentUser
from app.schemas.visualization_schema import (
    ChartArtifact,
    ConversationMessageResponse,
    ConversationResponse,
    ConversationSummaryResponse,
    DataTableArtifact,
    KpiCardArtifact,
    VisualizationBundle,
)


class ConversationAccessError(Exception):
    """Raised when a caller tries to access a conversation they do not own."""


class ConversationNotFoundError(Exception):
    """Raised when a conversation does not exist."""


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
        selected_version_id: str | None = None,
        company_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        if self._conversation_memory.has_session(session_id):
            return

        conversation = self._conversation_repository.get_or_create_conversation(
            session_id,
            selected_data_source_id,
            selected_version_id,
            company_id,
            user_id,
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
            selected_version_id=conversation.selected_version_id,
        )

    def sync_selected_data_source(
        self,
        session_id: str,
        selected_data_source_id: str | None,
        selected_version_id: str | None = None,
        company_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        self._conversation_repository.update_conversation(
            session_id,
            selected_data_source_id=selected_data_source_id,
            selected_version_id=selected_version_id,
            company_id=company_id,
            user_id=user_id,
        )

    def sync_context(self, session_id: str, context: dict[str, Any]) -> None:
        self._conversation_repository.update_conversation(
            session_id,
            context_json=context,
        )

    def save_user_message(
        self,
        session_id: str,
        content: str,
        company_id: str | None = None,
        user_id: str | None = None,
    ) -> str:
        message = self._conversation_repository.add_message(
            session_id,
            role="user",
            content=content,
            company_id=company_id,
            user_id=user_id,
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

    def _can_access(self, conversation: Any, current_user: CurrentUser) -> bool:
        """Admins may access any conversation in their company; users only their own."""
        if conversation.company_id != current_user.company_id:
            return False
        if current_user.is_admin:
            return True
        return conversation.user_id == current_user.id

    def verify_chat_access(self, session_id: str | None, current_user: CurrentUser) -> None:
        """Guard the chat endpoint: reject continuing a conversation the caller
        does not own. A non-existent session is treated as a new conversation."""
        if not session_id:
            return
        conversation = self._conversation_repository.get_conversation(session_id)
        if conversation is None:
            return
        if not self._can_access(conversation, current_user):
            raise ConversationAccessError("You do not have access to this conversation")

    def list_conversations(
        self, current_user: CurrentUser
    ) -> list[ConversationSummaryResponse]:
        # Users see only their own conversations; admins see the whole company.
        conversations = self._conversation_repository.list_conversations(
            company_id=current_user.company_id,
            user_id=None if current_user.is_admin else current_user.id,
        )
        summaries: list[ConversationSummaryResponse] = []
        for conversation in conversations:
            last_message = conversation.messages[-1] if conversation.messages else None
            summaries.append(
                ConversationSummaryResponse(
                    session_id=conversation.id,
                    title=conversation.title,
                    selected_data_source_id=conversation.selected_data_source_id,
                    selected_version_id=conversation.selected_version_id,
                    updated_at=conversation.updated_at,
                    message_count=len(conversation.messages),
                    last_message_preview=(
                        last_message.content[:120] if last_message is not None else None
                    ),
                )
            )
        return summaries

    def _require_owned_conversation(self, session_id: str, current_user: CurrentUser):
        conversation = self._conversation_repository.get_conversation(session_id)
        if conversation is None:
            raise ConversationNotFoundError("Conversation not found")
        if not self._can_access(conversation, current_user):
            # Do not reveal existence of conversations outside the caller's scope.
            raise ConversationNotFoundError("Conversation not found")
        return conversation

    def rename_conversation(
        self, session_id: str, current_user: CurrentUser, title: str
    ) -> ConversationResponse:
        self._require_owned_conversation(session_id, current_user)
        self._conversation_repository.update_conversation(session_id, title=title)
        return self.get_conversation(session_id, current_user)

    def delete_conversation(self, session_id: str, current_user: CurrentUser) -> None:
        conversation = self._require_owned_conversation(session_id, current_user)
        self._conversation_memory.drop_session(session_id)
        self._conversation_repository.delete_conversation(conversation)

    def get_conversation(
        self, session_id: str, current_user: CurrentUser
    ) -> ConversationResponse | None:
        conversation = self._conversation_repository.get_conversation(session_id)
        if conversation is None:
            return None
        if not self._can_access(conversation, current_user):
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
            selected_version_id=conversation.selected_version_id,
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
        # Non-visual artifacts are stored so future Report/Export features can
        # reuse them without re-running the AI. Each is a single JSON-payload row.
        for artifact_type, value, title in (
            ("sql", visualizations.generated_sql, "Generated SQL"),
            ("dataset_reference", visualizations.dataset_reference, "Dataset Reference"),
            ("applied_filters", visualizations.applied_filters, "Applied Filters"),
            ("dashboard", visualizations.dashboard, "Dashboard Metadata"),
        ):
            if not value:
                continue
            payload = {"value": value} if not isinstance(value, dict) else value
            self._conversation_repository.add_artifact(
                session_id,
                message_id=message_id,
                artifact_type=artifact_type,
                title=title,
                payload_json=payload,
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

        def _payload_for(artifact_type: str) -> Any:
            for artifact in artifacts:
                if artifact.artifact_type == artifact_type:
                    return artifact.payload_json
            return None

        sql_payload = _payload_for("sql")
        generated_sql = sql_payload.get("value") if isinstance(sql_payload, dict) else None

        return VisualizationBundle(
            kpi_cards=kpi_cards,
            tables=tables,
            charts=charts,
            generated_sql=generated_sql,
            dataset_reference=_payload_for("dataset_reference"),
            applied_filters=_payload_for("applied_filters"),
            dashboard=_payload_for("dashboard"),
        )
