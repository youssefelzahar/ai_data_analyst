import logging

import pyodbc

from app.core.encryption import encrypt_secret
from app.db.models.data_source_model import DataSource
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.data_source_schema import (
    AuthenticationType,
    ConnectionTestResult,
    DataSourceType,
    SqlServerConnectionCreate,
)

logger = logging.getLogger(__name__)

_CONNECTION_TIMEOUT_SECONDS = 5

# Newest driver first; fall back to whatever the host has installed.
_PREFERRED_ODBC_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
)


class SqlServerDriverNotFoundError(Exception):
    """Raised when no SQL Server ODBC driver is installed on the host."""


def _select_installed_odbc_driver() -> str:
    installed_drivers = set(pyodbc.drivers())
    for preferred_driver in _PREFERRED_ODBC_DRIVERS:
        if preferred_driver in installed_drivers:
            return preferred_driver
    raise SqlServerDriverNotFoundError(
        "No SQL Server ODBC driver is installed. "
        "Install 'ODBC Driver 18 for SQL Server' and try again."
    )


def _build_connection_string(connection_config: SqlServerConnectionCreate) -> str:
    connection_parts = [
        f"DRIVER={{{_select_installed_odbc_driver()}}}",
        f"SERVER={connection_config.server_host}",
        f"DATABASE={connection_config.database_name}",
        # Newer drivers default to encrypted connections; trust local/dev
        # certificates so connection tests don't fail on self-signed certs.
        "TrustServerCertificate=yes",
    ]
    if connection_config.authentication_type == AuthenticationType.WINDOWS:
        connection_parts.append("Trusted_Connection=yes")
    else:
        connection_parts.append(f"UID={connection_config.username}")
        connection_parts.append(f"PWD={connection_config.password}")
    return ";".join(connection_parts)


class SqlServerConnectionService:
    """Creates, tests, and persists SQL Server connection configurations."""

    def __init__(self, data_source_repository: DataSourceRepository) -> None:
        self._data_source_repository = data_source_repository

    def test_data_source_connection(
        self, connection_config: SqlServerConnectionCreate
    ) -> ConnectionTestResult:
        """Attempt a real connection and report success or a clear failure reason."""
        try:
            connection_string = _build_connection_string(connection_config)
        except SqlServerDriverNotFoundError as driver_error:
            return ConnectionTestResult(success=False, message=str(driver_error))

        try:
            with pyodbc.connect(connection_string, timeout=_CONNECTION_TIMEOUT_SECONDS):
                pass
        except pyodbc.Error as connection_error:
            failure_reason = _summarize_pyodbc_error(connection_error)
            logger.info(
                "Connection test failed for server %s / database %s: %s",
                connection_config.server_host,
                connection_config.database_name,
                failure_reason,
            )
            return ConnectionTestResult(success=False, message=failure_reason)

        return ConnectionTestResult(
            success=True,
            message=(
                f"Successfully connected to '{connection_config.database_name}' "
                f"on '{connection_config.server_host}'."
            ),
        )

    def create_data_source(self, connection_config: SqlServerConnectionCreate) -> DataSource:
        encrypted_password = (
            encrypt_secret(connection_config.password) if connection_config.password else None
        )
        sql_server_data_source = DataSource(
            name=connection_config.connection_name,
            source_type=DataSourceType.SQL_SERVER.value,
            server_host=connection_config.server_host,
            database_name=connection_config.database_name,
            authentication_type=connection_config.authentication_type.value,
            username=connection_config.username,
            encrypted_password=encrypted_password,
        )
        saved_data_source = self._data_source_repository.add_data_source(sql_server_data_source)
        logger.info("Saved SQL Server connection %s", saved_data_source.id)
        return saved_data_source


def _summarize_pyodbc_error(connection_error: pyodbc.Error) -> str:
    """Extract a readable message from pyodbc's nested error tuples."""
    error_text = str(connection_error)
    # pyodbc messages look like: ('28000', "[28000] [Microsoft][...] Login failed ... (18456)")
    if "]" in error_text:
        readable_part = error_text.rsplit("]", 1)[-1].strip(" \"')(")
        if readable_part:
            return readable_part
    return error_text