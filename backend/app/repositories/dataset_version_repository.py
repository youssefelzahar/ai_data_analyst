from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.dataset_version_model import DatasetVersion


class DatasetVersionRepository:
    """Persistence operations for dataset versions. No business logic."""

    def __init__(self, database_session: Session) -> None:
        self._database_session = database_session

    def add_version(self, version: DatasetVersion) -> DatasetVersion:
        self._database_session.add(version)
        self._database_session.commit()
        self._database_session.refresh(version)
        return version

    def list_for_data_source(self, data_source_id: str) -> list[DatasetVersion]:
        query = (
            select(DatasetVersion)
            .where(DatasetVersion.data_source_id == data_source_id)
            .order_by(DatasetVersion.version_number.asc())
        )
        return list(self._database_session.scalars(query).all())

    def get_latest(self, data_source_id: str) -> DatasetVersion | None:
        query = (
            select(DatasetVersion)
            .where(DatasetVersion.data_source_id == data_source_id)
            .order_by(DatasetVersion.version_number.desc())
            .limit(1)
        )
        return self._database_session.scalars(query).first()

    def get_by_id(self, version_id: str) -> DatasetVersion | None:
        return self._database_session.get(DatasetVersion, version_id)

    def delete(self, version: DatasetVersion) -> None:
        self._database_session.delete(version)
        self._database_session.commit()
