from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    content: str
    message_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationSession:
    session_id: str
    messages: list[ConversationMessage] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    selected_data_source_id: str | None = None
    selected_version_id: str | None = None


class ConversationMemory:
    """In-memory conversation store for active analyst sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationSession] = {}

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    def get_or_create_session(self, session_id: str | None = None) -> ConversationSession:
        resolved_session_id = session_id or str(uuid4())
        if resolved_session_id not in self._sessions:
            self._sessions[resolved_session_id] = ConversationSession(
                session_id=resolved_session_id
            )
        return self._sessions[resolved_session_id]

    def load_session(
        self,
        session_id: str,
        messages: list[ConversationMessage],
        context: dict[str, Any],
        selected_data_source_id: str | None,
        selected_version_id: str | None = None,
    ) -> ConversationSession:
        session = ConversationSession(
            session_id=session_id,
            messages=list(messages),
            context=dict(context),
            selected_data_source_id=selected_data_source_id,
            selected_version_id=selected_version_id,
        )
        self._sessions[session_id] = session
        return session

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        message_id: str | None = None,
    ) -> ConversationMessage:
        session = self.get_or_create_session(session_id)
        message = ConversationMessage(
            message_id=message_id,
            role=role,
            content=content,
            metadata=metadata or {},
        )
        session.messages.append(message)
        return message

    def set_selected_data_source(
        self, session_id: str, selected_data_source_id: str | None
    ) -> None:
        session = self.get_or_create_session(session_id)
        session.selected_data_source_id = selected_data_source_id

    def set_selected_version(
        self, session_id: str, selected_version_id: str | None
    ) -> None:
        session = self.get_or_create_session(session_id)
        session.selected_version_id = selected_version_id

    def update_context(self, session_id: str, **context_values: Any) -> None:
        session = self.get_or_create_session(session_id)
        session.context.update(context_values)

    def get_recent_messages(
        self, session_id: str, message_limit: int = 12
    ) -> list[ConversationMessage]:
        session = self.get_or_create_session(session_id)
        return session.messages[-message_limit:]
