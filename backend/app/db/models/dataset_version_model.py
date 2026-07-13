import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _generate_dataset_version_id() -> str:
    return str(uuid.uuid4())


def _current_utc_time() -> datetime:
    return datetime.now(timezone.utc)


class DatasetVersion(Base):
    """A cleaned snapshot of a DataSource, produced by applying a cleaning pipeline.

    The original DataSource file is never modified. Applying a pipeline always
    writes a brand-new file (via FileStorage) and records it here, so the
    dataset's history is a simple append-only list of versions. "Current" is
    whichever version has the highest `version_number` for a data source;
    "undo" deletes that row (and its file), reverting current to the one before it.
    """

    __tablename__ = "dataset_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_dataset_version_id)
    data_source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_sources.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    operations_summary: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    label: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_current_utc_time)
