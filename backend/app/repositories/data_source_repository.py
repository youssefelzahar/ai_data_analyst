from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.data_source_model import DataSource


class DataSourceRepository:
    """Persistence operations for data sources. No business logic."""

    def __init__(self, database_session: Session) -> None:
        self._database_session = database_session

    def add_data_source(self, data_source: DataSource) -> DataSource:
        self._database_session.add(data_source)
        self._database_session.commit()
        self._database_session.refresh(data_source)
        return data_source

    def list_data_sources(
        self,
        source_type: str | None = None,
        company_id: str | None = None,
    ) -> list[DataSource]:
        query = select(DataSource).order_by(DataSource.created_at.desc())
        if source_type is not None:
            query = query.where(DataSource.source_type == source_type)
        if company_id is not None:
            query = query.where(DataSource.company_id == company_id)
        return list(self._database_session.scalars(query).all())

    def get_data_source_by_id(self, data_source_id: str) -> DataSource | None:
        return self._database_session.get(DataSource, data_source_id)

    def delete_data_source(self, data_source: DataSource) -> None:
        self._database_session.delete(data_source)
        self._database_session.commit()