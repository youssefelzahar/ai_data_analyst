"""Password hashing and JWT helpers for authentication.

Passwords are hashed with bcrypt (used directly). Access and refresh tokens are
signed JWTs; the refresh token is additionally persisted (as a hash) so it can
be revoked. Access-token claims carry the identity and authorization context the
API needs on every request: user id, username, role, company id, and company name.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# bcrypt rejects passwords longer than 72 bytes; truncate defensively.
_BCRYPT_MAX_BYTES = 72


class TokenError(Exception):
    """Raised when a JWT is missing, malformed, expired, or of the wrong type."""


def hash_password(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    *,
    user_id: str,
    username: str,
    role: str,
    company_id: str,
    company_name: str,
) -> str:
    settings = get_settings()
    expires_at = _now() + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "role": role,
        "company_id": company_id,
        "company_name": company_name,
        "type": TOKEN_TYPE_ACCESS,
        "exp": expires_at,
        "iat": _now(),
    }
    return jwt.encode(
        payload,
        settings.effective_jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: str) -> tuple[str, datetime]:
    """Return a signed refresh JWT and its expiry.

    A random ``jti`` makes each token unique so its hash can be stored and
    revoked independently.
    """
    settings = get_settings()
    expires_at = _now() + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": TOKEN_TYPE_REFRESH,
        "jti": f"{uuid.uuid4()}.{secrets.token_urlsafe(16)}",
        "exp": expires_at,
        "iat": _now(),
    }
    token = jwt.encode(
        payload,
        settings.effective_jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.effective_jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as error:
        raise TokenError(str(error)) from error
    if expected_type is not None and payload.get("type") != expected_type:
        raise TokenError("Unexpected token type")
    return payload


def hash_token(token: str) -> str:
    """Deterministic hash of a raw token for storage/lookup (not for passwords)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
