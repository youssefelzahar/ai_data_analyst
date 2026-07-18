from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.conversation_model import (
    Conversation,
    ConversationArtifactModel,
    ConversationMessageModel,
)


def _current_utc_time() -> datetime:
    return datetime.now(timezone.utc)


class ConversationRepository:
    def __init__(self, database_session: Session) -> None:
        self._database_session = database_session

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        query = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(
                selectinload(Conversation.messages).selectinload(ConversationMessageModel.artifacts),
                selectinload(Conversation.artifacts),
            )
        )
        return self._database_session.scalar(query)

    def list_conversations(self) -> list[Conversation]:
        query = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .order_by(Conversation.updated_at.desc())
        )
        return list(self._database_session.scalars(query).all())

    def get_or_create_conversation(
        self,
        conversation_id: str,
        selected_data_source_id: str | None = None,
        selected_version_id: str | None = None,
    ) -> Conversation:
        conversation = self.get_conversation(conversation_id)
        if conversation is not None:
            return conversation

        conversation = Conversation(
            id=conversation_id,
            selected_data_source_id=selected_data_source_id,
            selected_version_id=selected_version_id,
            context_json={},
        )
        self._database_session.add(conversation)
        self._database_session.commit()
        self._database_session.refresh(conversation)
        return self.get_conversation(conversation_id) or conversation

    def update_conversation(
        self,
        conversation_id: str,
        *,
        selected_data_source_id: str | None = None,
        selected_version_id: str | None = None,
        context_json: dict | None = None,
        title: str | None = None,
    ) -> Conversation:
        conversation = self.get_or_create_conversation(
            conversation_id, selected_data_source_id, selected_version_id
        )
        conversation.selected_data_source_id = selected_data_source_id
        conversation.selected_version_id = selected_version_id
        if context_json is not None:
            conversation.context_json = context_json
        if title is not None and title.strip():
            conversation.title = title.strip()
        conversation.updated_at = _current_utc_time()
        self._database_session.add(conversation)
        self._database_session.commit()
        self._database_session.refresh(conversation)
        return self.get_conversation(conversation_id) or conversation

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata_json: dict | None = None,
    ) -> ConversationMessageModel:
        conversation = self.get_or_create_conversation(conversation_id)
        message = ConversationMessageModel(
            conversation_id=conversation.id,
            role=role,
            content=content,
            metadata_json=metadata_json or {},
        )
        conversation.updated_at = _current_utc_time()
        if not conversation.title and role == "user":
            conversation.title = content.strip()[:80]
        self._database_session.add(message)
        self._database_session.add(conversation)
        self._database_session.commit()
        self._database_session.refresh(message)
        return message

    def add_artifact(
        self,
        conversation_id: str,
        *,
        message_id: str | None,
        artifact_type: str,
        title: str,
        payload_json: dict,
    ) -> ConversationArtifactModel:
        artifact = ConversationArtifactModel(
            conversation_id=conversation_id,
            message_id=message_id,
            artifact_type=artifact_type,
            title=title,
            payload_json=payload_json,
        )
        conversation = self.get_or_create_conversation(conversation_id)
        conversation.updated_at = _current_utc_time()
        self._database_session.add(artifact)
        self._database_session.add(conversation)
        self._database_session.commit()
        self._database_session.refresh(artifact)
        return artifact
