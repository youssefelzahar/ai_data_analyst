import uuid
from datetime import datetime, timezone

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.db.models.company_model import Company

# superadmin: platform-level, may only create admins (each with a company).
# admin: manages their own company (users + data). user: regular company member.
USER_ROLE_SUPERADMIN = "superadmin"
USER_ROLE_ADMIN = "admin"
USER_ROLE_USER = "user"
VALID_USER_ROLES = frozenset({USER_ROLE_SUPERADMIN, USER_ROLE_ADMIN, USER_ROLE_USER})


def _generate_id() -> str:
    return str(uuid.uuid4())


def _current_utc_time() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """An authenticated account scoped to a single company, with an RBAC role."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_id)
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=USER_ROLE_USER)
    full_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_current_utc_time)

    company: Mapped["Company"] = relationship(lazy="joined")

    @property
    def company_name(self) -> str:
        return self.company.name if self.company is not None else ""
