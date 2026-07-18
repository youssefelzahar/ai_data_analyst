from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


def _build_engine_arguments(database_url: str) -> dict:
    # SQLite needs this flag because FastAPI may touch the session
    # from different threads within one request lifecycle.
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


_settings = get_settings()
engine = create_engine(_settings.database_url, **_build_engine_arguments(_settings.database_url))

SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_database_tables() -> None:
    """Create all tables that do not exist yet.

    Sufficient while the schema is young; will be replaced by Alembic
    migrations once the schema needs versioned evolution.
    """
    # Import models so they register themselves on Base.metadata.
    from app.db.models import conversation_model  # noqa: F401
    from app.db.models import data_source_model  # noqa: F401
    from app.db.models import dataset_version_model  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """Adds columns introduced after a table already exists.

    Sufficient while the schema is young; will be replaced by Alembic
    migrations once the schema needs versioned evolution.
    """
    inspector = inspect(engine)
    if "conversations" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("conversations")}
    if "selected_version_id" in existing_columns:
        return
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE conversations ADD COLUMN selected_version_id VARCHAR(36)")
        )


def get_database_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a session and always closes it."""
    database_session = SessionFactory()
    try:
        yield database_session
    finally:
        database_session.close()
