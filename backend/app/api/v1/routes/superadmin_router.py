from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import SuperadminUserDep
from app.api.v1.routes.users_router import get_user_service
from app.schemas.auth_schema import AdminCreate, UserResponse
from app.services.user_service import (
    UserManagementError,
    UserNotFoundError,
    UserService,
)

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


@router.get("/admins", response_model=list[UserResponse])
def list_admins(
    _superadmin: SuperadminUserDep,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> list[UserResponse]:
    """List every admin across all companies (superadmin only)."""
    return [UserResponse.model_validate(admin) for admin in user_service.list_admins()]


@router.post("/admins", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_admin(
    payload: AdminCreate,
    _superadmin: SuperadminUserDep,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Create an admin and their company (superadmin only). Users the admin
    later creates inherit this company."""
    try:
        admin = user_service.create_admin(payload)
    except UserManagementError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error
    return UserResponse.model_validate(admin)


@router.delete("/admins/{admin_id}", response_model=UserResponse)
def deactivate_admin(
    admin_id: str,
    _superadmin: SuperadminUserDep,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Deactivate an admin account (superadmin only)."""
    try:
        admin = user_service.set_admin_active(admin_id, is_active=False)
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    return UserResponse.model_validate(admin)
