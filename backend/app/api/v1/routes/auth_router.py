from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUserDep
from app.db.database import get_database_session
from app.repositories.company_repository import CompanyRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import (
    CurrentUser,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services.auth_service import AuthenticationError, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(
    database_session: Annotated[Session, Depends(get_database_session)],
) -> AuthService:
    return AuthService(
        user_repository=UserRepository(database_session),
        company_repository=CompanyRepository(database_session),
        refresh_token_repository=RefreshTokenRepository(database_session),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    try:
        return auth_service.login(credentials.username, credentials.password)
    except AuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)
        ) from error


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(
    payload: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    try:
        return auth_service.refresh(payload.refresh_token)
    except AuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)
        ) from error


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: LogoutRequest,
    _current_user: CurrentUserDep,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    auth_service.logout(payload.refresh_token)


@router.get("/me", response_model=CurrentUser)
def read_current_user(current_user: CurrentUserDep) -> CurrentUser:
    return current_user
