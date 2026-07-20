"""User-management use-cases.

Admins manage regular users within their own company. The superadmin is a
platform role whose only capability is creating admins — each admin gets their
own company, and the users that admin later creates inherit that company.
"""

from app.core.security import hash_password
from app.db.models.user_model import USER_ROLE_ADMIN, USER_ROLE_USER, User
from app.repositories.company_repository import CompanyRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import AdminCreate, UserCreate, UserUpdate


class UserManagementError(Exception):
    """Raised for invalid user-management operations (e.g. duplicate username)."""


class UserNotFoundError(Exception):
    """Raised when a target user does not exist within the caller's scope."""


class UserService:
    def __init__(
        self,
        user_repository: UserRepository,
        refresh_token_repository: RefreshTokenRepository,
        company_repository: CompanyRepository,
    ) -> None:
        self._user_repository = user_repository
        self._refresh_token_repository = refresh_token_repository
        self._company_repository = company_repository

    # --- Admin: manage regular users within their own company ---------------

    def list_company_users(self, company_id: str) -> list[User]:
        return self._user_repository.list_by_company(company_id)

    def create_user(self, company_id: str, payload: UserCreate) -> User:
        if self._user_repository.get_by_username(payload.username) is not None:
            raise UserManagementError("A user with that username already exists")
        # Admins may only create regular users; the requested role is ignored.
        # Admin accounts are created solely by the superadmin.
        user = User(
            company_id=company_id,
            username=payload.username,
            hashed_password=hash_password(payload.password),
            role=USER_ROLE_USER,
            full_name=payload.full_name,
        )
        return self._user_repository.add(user)

    def _require_company_user(self, company_id: str, user_id: str) -> User:
        user = self._user_repository.get_by_id(user_id)
        if user is None or user.company_id != company_id:
            raise UserNotFoundError("User not found")
        return user

    def update_user(self, company_id: str, user_id: str, payload: UserUpdate) -> User:
        user = self._require_company_user(company_id, user_id)
        if payload.password is not None:
            user.hashed_password = hash_password(payload.password)
        if payload.role is not None:
            # Admins cannot elevate a user to admin/superadmin.
            if payload.role != USER_ROLE_USER:
                raise UserManagementError("Admins may only assign the 'user' role")
            user.role = payload.role
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.is_active is not None:
            user.is_active = payload.is_active
            if not payload.is_active:
                self._refresh_token_repository.revoke_all_for_user(user.id)
        return self._user_repository.save(user)

    def deactivate_user(self, company_id: str, user_id: str, acting_user_id: str) -> User:
        if user_id == acting_user_id:
            raise UserManagementError("You cannot deactivate your own account")
        user = self._require_company_user(company_id, user_id)
        user.is_active = False
        self._refresh_token_repository.revoke_all_for_user(user.id)
        return self._user_repository.save(user)

    # --- Superadmin: manage admins (each with their own company) ------------

    def list_admins(self) -> list[User]:
        return self._user_repository.list_by_role(USER_ROLE_ADMIN)

    def create_admin(self, payload: AdminCreate) -> User:
        if self._user_repository.get_by_username(payload.username) is not None:
            raise UserManagementError("A user with that username already exists")
        company = self._company_repository.get_or_create_by_name(payload.company_name.strip())
        admin = User(
            company_id=company.id,
            username=payload.username,
            hashed_password=hash_password(payload.password),
            role=USER_ROLE_ADMIN,
            full_name=payload.full_name,
        )
        return self._user_repository.add(admin)

    def set_admin_active(self, user_id: str, is_active: bool) -> User:
        admin = self._user_repository.get_by_id(user_id)
        if admin is None or admin.role != USER_ROLE_ADMIN:
            raise UserNotFoundError("Admin not found")
        admin.is_active = is_active
        if not is_active:
            self._refresh_token_repository.revoke_all_for_user(admin.id)
        return self._user_repository.save(admin)
