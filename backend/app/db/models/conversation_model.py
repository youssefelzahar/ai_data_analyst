import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _generate_id() -> str:
    return str(uuid.uuid4())


def _current_utc_time() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_id)
    title: Mapped[str | None] = mapped_column(String(255))
    selected_data_source_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("data_sources.id"),
        nullable=True,
    )
    context_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_current_utc_time)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_current_utc_time,
    )

    messages: Mapped[list["ConversationMessageModel"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessageModel.created_at",
    )
    artifacts: Mapped[list["ConversationArtifactModel"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationArtifactModel.created_at",
    )


class ConversationMessageModel(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_id)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_current_utc_time)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    artifacts: Mapped[list["ConversationArtifactModel"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="ConversationArtifactModel.created_at",
    )


class ConversationArtifactModel(Base):
    __tablename__ = "conversation_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_id)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_current_utc_time)

    conversation: Mapped[Conversation] = relationship(back_populates="artifacts")
    message: Mapped[ConversationMessageModel | None] = relationship(back_populates="artifacts")
