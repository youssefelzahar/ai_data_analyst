from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import AdminUserDep
from app.db.database import get_database_session
from app.repositories.company_repository import CompanyRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import UserCreate, UserResponse, UserUpdate
from app.services.user_service import (
    UserManagementError,
    UserNotFoundError,
    UserService,
)

router = APIRouter(prefix="/users", tags=["users"])


def get_user_service(
    database_session: Annotated[Session, Depends(get_database_session)],
) -> UserService:
    return UserService(
        user_repository=UserRepository(database_session),
        refresh_token_repository=RefreshTokenRepository(database_session),
        company_repository=CompanyRepository(database_session),
    )


@router.get("", response_model=list[UserResponse])
def list_users(
    admin: AdminUserDep,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> list[UserResponse]:
    users = user_service.list_company_users(admin.company_id)
    return [UserResponse.model_validate(user) for user in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    admin: AdminUserDep,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    try:
        user = user_service.create_user(admin.company_id, payload)
    except UserManagementError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdate,
    admin: AdminUserDep,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    try:
        user = user_service.update_user(admin.company_id, user_id, payload)
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except UserManagementError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", response_model=UserResponse)
def deactivate_user(
    user_id: str,
    admin: AdminUserDep,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Deactivate a user (soft delete) and revoke their refresh tokens."""
    try:
        user = user_service.deactivate_user(admin.company_id, user_id, admin.id)
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except UserManagementError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error
    return UserResponse.model_validate(user)
