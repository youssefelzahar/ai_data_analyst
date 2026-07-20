"""Authentication use-cases: login, token refresh (with rotation), and logout.

Tokens are minted by ``app.core.security``. Refresh tokens are persisted as
hashes via ``RefreshTokenRepository`` so they can be revoked on logout and
rotated on every refresh (a used refresh token is revoked and replaced).
"""

from datetime import datetime, timezone

from app.core.security import (
    TOKEN_TYPE_REFRESH,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    verify_password,
)
from app.db.models.user_model import User
from app.repositories.company_repository import CompanyRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import TokenResponse


class AuthenticationError(Exception):
    """Raised when credentials are invalid or a refresh token is unusable."""


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        company_repository: CompanyRepository,
        refresh_token_repository: RefreshTokenRepository,
    ) -> None:
        self._user_repository = user_repository
        self._company_repository = company_repository
        self._refresh_token_repository = refresh_token_repository

    def login(self, username: str, password: str) -> TokenResponse:
        user = self._user_repository.get_by_username(username)
        if user is None or not user.is_active or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid username or password")
        return self._issue_tokens(user)

    def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)
        except TokenError as error:
            raise AuthenticationError("Invalid refresh token") from error

        stored = self._refresh_token_repository.get_by_hash(hash_token(refresh_token))
        if stored is None or stored.revoked:
            raise AuthenticationError("Refresh token is not recognized or has been revoked")
        if _as_utc(stored.expires_at) < datetime.now(timezone.utc):
            raise AuthenticationError("Refresh token has expired")

        user = self._user_repository.get_by_id(str(payload.get("sub")))
        if user is None or not user.is_active:
            raise AuthenticationError("Account is no longer active")

        # Rotate: revoke the presented token and issue a fresh pair.
        self._refresh_token_repository.revoke(stored)
        return self._issue_tokens(user)

    def logout(self, refresh_token: str) -> None:
        stored = self._refresh_token_repository.get_by_hash(hash_token(refresh_token))
        if stored is not None and not stored.revoked:
            self._refresh_token_repository.revoke(stored)

    def _issue_tokens(self, user: User) -> TokenResponse:
        company = self._company_repository.get_by_id(user.company_id)
        company_name = company.name if company is not None else ""
        access_token = create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
            company_id=user.company_id,
            company_name=company_name,
        )
        refresh_token, expires_at = create_refresh_token(user.id)
        self._refresh_token_repository.create(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=expires_at,
        )
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)


def _as_utc(moment: datetime) -> datetime:
    """SQLite may return naive datetimes; treat them as UTC for comparison."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment
