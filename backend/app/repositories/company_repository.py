from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.company_model import Company


class CompanyRepository:
    """Persistence operations for companies. No business logic."""

    def __init__(self, database_session: Session) -> None:
        self._database_session = database_session

    def get_by_id(self, company_id: str) -> Company | None:
        return self._database_session.get(Company, company_id)

    def get_by_name(self, name: str) -> Company | None:
        query = select(Company).where(Company.name == name)
        return self._database_session.scalar(query)

    def create(self, name: str) -> Company:
        company = Company(name=name)
        self._database_session.add(company)
        self._database_session.commit()
        self._database_session.refresh(company)
        return company

    def get_or_create_by_name(self, name: str) -> Company:
        existing = self.get_by_name(name)
        if existing is not None:
            return existing
        return self.create(name)

    def list_companies(self) -> list[Company]:
        return list(self._database_session.scalars(select(Company)).all())
