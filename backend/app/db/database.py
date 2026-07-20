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
    from app.db.models import company_model  # noqa: F401
    from app.db.models import conversation_model  # noqa: F401
    from app.db.models import data_source_model  # noqa: F401
    from app.db.models import dataset_version_model  # noqa: F401
    from app.db.models import refresh_token_model  # noqa: F401
    from app.db.models import user_model  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    _seed_bootstrap()


# Columns added to tables that may already exist from an earlier schema version.
# Each entry is (table, column, DDL type). Applied only when the column is absent.
_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    ("conversations", "selected_version_id", "VARCHAR(36)"),
    ("conversations", "company_id", "VARCHAR(36)"),
    ("conversations", "user_id", "VARCHAR(36)"),
    ("data_sources", "company_id", "VARCHAR(36)"),
    ("data_sources", "created_by_user_id", "VARCHAR(36)"),
]


def _add_missing_columns() -> None:
    """Adds columns introduced after a table already exists.

    Sufficient while the schema is young; will be replaced by Alembic
    migrations once the schema needs versioned evolution.
    """
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    for table, column, ddl_type in _ADDED_COLUMNS:
        if table not in table_names:
            continue
        existing_columns = {c["name"] for c in inspector.get_columns(table)}
        if column in existing_columns:
            continue
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def _seed_bootstrap() -> None:
    """Idempotently seed a default company + admin user and backfill legacy rows.

    Runs on every startup. If any company already exists it does nothing beyond
    backfilling; otherwise it creates the configured default company and admin
    account so the system is usable on first boot (there is no self-signup).
    """
    from app.core.config import get_settings
    from app.core.security import hash_password
    from app.db.models.company_model import Company
    from app.db.models.user_model import USER_ROLE_ADMIN, USER_ROLE_SUPERADMIN, User

    settings = get_settings()
    with SessionFactory() as session:

        def _get_or_create_company(name: str) -> Company:
            company = session.query(Company).filter(Company.name == name).first()
            if company is None:
                company = Company(name=name)
                session.add(company)
                session.flush()
            return company

        def _ensure_user(username: str, password: str, role: str, company: Company, full_name: str) -> None:
            existing = session.query(User).filter(User.username == username).first()
            if existing is None:
                session.add(
                    User(
                        company_id=company.id,
                        username=username,
                        hashed_password=hash_password(password),
                        role=role,
                        full_name=full_name,
                    )
                )

        default_company = _get_or_create_company(settings.bootstrap_company_name)
        _ensure_user(
            settings.bootstrap_admin_username,
            settings.bootstrap_admin_password,
            USER_ROLE_ADMIN,
            default_company,
            "Administrator",
        )

        # Platform superadmin, whose only capability is creating admins.
        superadmin_company = _get_or_create_company(settings.bootstrap_superadmin_company)
        _ensure_user(
            settings.bootstrap_superadmin_username,
            settings.bootstrap_superadmin_password,
            USER_ROLE_SUPERADMIN,
            superadmin_company,
            "Super Administrator",
        )

        company = default_company

        # Backfill legacy rows created before company scoping existed.
        session.execute(
            text("UPDATE data_sources SET company_id = :cid WHERE company_id IS NULL"),
            {"cid": company.id},
        )
        session.execute(
            text("UPDATE conversations SET company_id = :cid WHERE company_id IS NULL"),
            {"cid": company.id},
        )
        session.commit()


def get_database_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a session and always closes it."""
    database_session = SessionFactory()
    try:
        yield database_session
    finally:
        database_session.close()
