from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user_model import User


class UserRepository:
    """Persistence operations for users. No business logic."""

    def __init__(self, database_session: Session) -> None:
        self._database_session = database_session

    def get_by_id(self, user_id: str) -> User | None:
        return self._database_session.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        query = select(User).where(User.username == username)
        return self._database_session.scalar(query)

    def list_by_company(self, company_id: str) -> list[User]:
        query = (
            select(User)
            .where(User.company_id == company_id)
            .order_by(User.created_at.desc())
        )
        return list(self._database_session.scalars(query).all())

    def list_by_role(self, role: str) -> list[User]:
        """List users of a role across all companies (used by the superadmin)."""
        query = (
            select(User).where(User.role == role).order_by(User.created_at.desc())
        )
        return list(self._database_session.scalars(query).all())

    def add(self, user: User) -> User:
        self._database_session.add(user)
        self._database_session.commit()
        self._database_session.refresh(user)
        return user

    def save(self, user: User) -> User:
        self._database_session.add(user)
        self._database_session.commit()
        self._database_session.refresh(user)
        return user
