import logging

import pandas as pd
import pyodbc

from app.core.encryption import decrypt_secret, encrypt_secret
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
_QUERY_TIMEOUT_SECONDS = 30

# Newest driver first; fall back to whatever the host has installed.
_PREFERRED_ODBC_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
)


class SqlServerDriverNotFoundError(Exception):
    """Raised when no SQL Server ODBC driver is installed on the host."""


class SqlServerQueryError(Exception):
    """Raised when a query against a saved SQL Server connection fails."""


def _escape_sql_identifier(identifier: str) -> str:
    return f"[{identifier.replace(']', ']]')}]"


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

    def build_connection_string(self, data_source: DataSource) -> str:
        """Build an ODBC connection string from a saved SQL Server data source."""
        connection_parts = [
            f"DRIVER={{{_select_installed_odbc_driver()}}}",
            f"SERVER={data_source.server_host}",
            f"DATABASE={data_source.database_name}",
            "TrustServerCertificate=yes",
        ]
        if data_source.authentication_type == AuthenticationType.WINDOWS.value:
            connection_parts.append("Trusted_Connection=yes")
        else:
            connection_parts.append(f"UID={data_source.username}")
            password = decrypt_secret(data_source.encrypted_password) if data_source.encrypted_password else ""
            connection_parts.append(f"PWD={password}")
        return ";".join(connection_parts)

    def list_tables(self, data_source: DataSource) -> list[str]:
        """List base table names available in the connected database."""
        try:
            connection_string = self.build_connection_string(data_source)
        except SqlServerDriverNotFoundError:
            raise

        try:
            with pyodbc.connect(connection_string, timeout=_CONNECTION_TIMEOUT_SECONDS) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
                )
                return [row.TABLE_NAME for row in cursor.fetchall()]
        except pyodbc.Error as query_error:
            raise SqlServerQueryError(_summarize_pyodbc_error(query_error)) from query_error

    def list_columns(self, data_source: DataSource, table_name: str) -> list[dict[str, object]]:
        connection_string = self.build_connection_string(data_source)
        try:
            with pyodbc.connect(connection_string, timeout=_CONNECTION_TIMEOUT_SECONDS) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT
                        COLUMN_NAME,
                        DATA_TYPE,
                        IS_NULLABLE,
                        ORDINAL_POSITION,
                        CHARACTER_MAXIMUM_LENGTH,
                        NUMERIC_PRECISION,
                        NUMERIC_SCALE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = ?
                    ORDER BY ORDINAL_POSITION
                    """,
                    table_name,
                )
                return [
                    {
                        "column_name": row.COLUMN_NAME,
                        "data_type": row.DATA_TYPE,
                        "is_nullable": row.IS_NULLABLE == "YES",
                        "ordinal_position": int(row.ORDINAL_POSITION),
                        "character_maximum_length": (
                            int(row.CHARACTER_MAXIMUM_LENGTH)
                            if row.CHARACTER_MAXIMUM_LENGTH is not None
                            else None
                        ),
                        "numeric_precision": (
                            int(row.NUMERIC_PRECISION)
                            if row.NUMERIC_PRECISION is not None
                            else None
                        ),
                        "numeric_scale": (
                            int(row.NUMERIC_SCALE) if row.NUMERIC_SCALE is not None else None
                        ),
                    }
                    for row in cursor.fetchall()
                ]
        except pyodbc.Error as query_error:
            raise SqlServerQueryError(_summarize_pyodbc_error(query_error)) from query_error

    def get_table_row_count(self, data_source: DataSource, table_name: str) -> int:
        connection_string = self.build_connection_string(data_source)
        escaped_table_name = _escape_sql_identifier(table_name)
        try:
            with pyodbc.connect(connection_string, timeout=_QUERY_TIMEOUT_SECONDS) as connection:
                cursor = connection.cursor()
                cursor.execute(f"SELECT COUNT(*) AS row_count FROM {escaped_table_name}")
                row = cursor.fetchone()
                return int(row.row_count if hasattr(row, "row_count") else row[0])
        except pyodbc.Error as query_error:
            raise SqlServerQueryError(_summarize_pyodbc_error(query_error)) from query_error

    def preview_table(
        self,
        data_source: DataSource,
        table_name: str,
        offset: int,
        limit: int,
    ) -> pd.DataFrame:
        connection_string = self.build_connection_string(data_source)
        escaped_table_name = _escape_sql_identifier(table_name)
        sql = (
            f"SELECT * FROM {escaped_table_name} "
            "ORDER BY (SELECT NULL) "
            f"OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"
        )
        try:
            with pyodbc.connect(connection_string, timeout=_QUERY_TIMEOUT_SECONDS) as connection:
                return pd.read_sql(sql, connection)
        except pyodbc.Error as query_error:
            raise SqlServerQueryError(_summarize_pyodbc_error(query_error)) from query_error

    def run_query(self, data_source: DataSource, sql: str) -> pd.DataFrame:
        """Execute a SQL query against a saved connection and return the rows as a DataFrame.

        The caller is responsible for enforcing read-only access; this method
        runs whatever SQL it is given.
        """
        connection_string = self.build_connection_string(data_source)
        try:
            with pyodbc.connect(connection_string, timeout=_QUERY_TIMEOUT_SECONDS) as connection:
                return pd.read_sql(sql, connection)
        except pyodbc.Error as query_error:
            raise SqlServerQueryError(_summarize_pyodbc_error(query_error)) from query_error

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

    def create_data_source(
        self,
        connection_config: SqlServerConnectionCreate,
        company_id: str | None = None,
        created_by_user_id: str | None = None,
    ) -> DataSource:
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
            company_id=company_id,
            created_by_user_id=created_by_user_id,
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
