"""Shared FastAPI dependencies for authentication, RBAC, and company scoping.

``get_current_user`` resolves and validates the bearer token on every protected
request. ``require_admin`` gates admin-only endpoints. ``ensure_company_access``
enforces tenant isolation, raising 404 (not 403) on a company mismatch so the
existence of another company's resources is never revealed.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TOKEN_TYPE_ACCESS, TokenError, decode_token
from app.db.database import get_database_session
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import CurrentUser

_bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    database_session: Annotated[Session, Depends(get_database_session)],
) -> CurrentUser:
    if credentials is None or not credentials.credentials:
        raise _CREDENTIALS_EXCEPTION
    try:
        payload = decode_token(credentials.credentials, expected_type=TOKEN_TYPE_ACCESS)
    except TokenError as error:
        raise _CREDENTIALS_EXCEPTION from error

    user_id = payload.get("sub")
    if not user_id:
        raise _CREDENTIALS_EXCEPTION

    # Confirm the account still exists and is active; claims alone are not trusted
    # for account state (a deactivated user must lose access immediately).
    user = UserRepository(database_session).get_by_id(str(user_id))
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXCEPTION

    return CurrentUser(
        id=user.id,
        username=user.username,
        role=user.role,
        company_id=user.company_id,
        company_name=str(payload.get("company_name") or ""),
    )


def require_admin(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges are required for this action.",
        )
    return current_user


def require_superadmin(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin privileges are required for this action.",
        )
    return current_user


def require_company_member(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Allow admins and users into company workspaces; keep the superadmin out.

    The superadmin is a platform role whose only capability is creating admins,
    so it must not reach company data, conversations, or exports.
    """
    if current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The superadmin account cannot access company workspaces.",
        )
    return current_user


def ensure_company_access(resource_company_id: str | None, current_user: CurrentUser) -> None:
    """Raise 404 if the resource is not owned by the caller's company."""
    if resource_company_id != current_user.company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
AdminUserDep = Annotated[CurrentUser, Depends(require_admin)]
SuperadminUserDep = Annotated[CurrentUser, Depends(require_superadmin)]
CompanyMemberDep = Annotated[CurrentUser, Depends(require_company_member)]
