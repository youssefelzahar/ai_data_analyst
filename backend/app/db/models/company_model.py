import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _generate_id() -> str:
    return str(uuid.uuid4())


def _current_utc_time() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    """A tenant. Every user, data source, and conversation belongs to one company."""

    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_current_utc_time)
