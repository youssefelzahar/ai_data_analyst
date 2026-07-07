import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _generate_data_source_id() -> str:
    return str(uuid.uuid4())


def _current_utc_time() -> datetime:
    return datetime.now(timezone.utc)


class DataSource(Base):
    """A registered data source: an uploaded file or a database connection.

    Single table with a `source_type` discriminator. Type-specific columns
    are nullable and only populated for the matching source type. The rest
    of the application interacts with data sources through this one
    abstraction and never needs to know the underlying kind.
    """

    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_data_source_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_current_utc_time)

    # --- Uploaded file fields ---
    original_filename: Mapped[str | None] = mapped_column(String(255))
    stored_filename: Mapped[str | None] = mapped_column(String(255))
    file_format: Mapped[str | None] = mapped_column(String(20))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)

    # --- SQL Server connection fields ---
    server_host: Mapped[str | None] = mapped_column(String(255))
    database_name: Mapped[str | None] = mapped_column(String(255))
    authentication_type: Mapped[str | None] = mapped_column(String(50))
    username: Mapped[str | None] = mapped_column(String(255))
    encrypted_password: Mapped[str | None] = mapped_column(String(1024))