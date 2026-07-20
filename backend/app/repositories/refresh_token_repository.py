from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.refresh_token_model import RefreshToken


class RefreshTokenRepository:
    """Persistence operations for revocable refresh tokens. No business logic."""

    def __init__(self, database_session: Session) -> None:
        self._database_session = database_session

    def create(self, *, user_id: str, token_hash: str, expires_at: datetime) -> RefreshToken:
        token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._database_session.add(token)
        self._database_session.commit()
        self._database_session.refresh(token)
        return token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        query = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return self._database_session.scalar(query)

    def revoke(self, token: RefreshToken) -> None:
        token.revoked = True
        self._database_session.add(token)
        self._database_session.commit()

    def revoke_all_for_user(self, user_id: str) -> None:
        self._database_session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        self._database_session.commit()
