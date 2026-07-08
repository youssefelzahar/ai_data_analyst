from typing import Callable

import pandas as pd
import pyodbc

from app.db.models.data_source_model import DataSource
from app.schemas.data_source_schema import DataSourceType, FileFormat
from app.services.sql_server_connection_service import SqlServerConnectionService
from app.storage.base import FileStorage

_FILE_READERS = {
    FileFormat.CSV.value: pd.read_csv,
    FileFormat.EXCEL.value: pd.read_excel,
}

_QUERY_TIMEOUT_SECONDS = 30


class UnsupportedDataSourceError(Exception):
    """Raised when a data source type has no registered loader."""


class DatasetLoadError(Exception):
    """Raised when the underlying file or table cannot be read."""


class DatasetLoader:
    """Loads any supported data source into a pandas DataFrame.

    Callers depend only on `load()`; adding a new source type (PostgreSQL,
    MySQL, Oracle, SQLite, ...) means adding one more loader method and one
    more registry entry here, without touching anything downstream.
    """

    def __init__(
        self,
        file_storage: FileStorage,
        sql_server_connection_service: SqlServerConnectionService,
    ) -> None:
        self._file_storage = file_storage
        self._sql_server_connection_service = sql_server_connection_service
        self._loaders: dict[str, Callable[[DataSource, str | None], pd.DataFrame]] = {
            DataSourceType.FILE.value: lambda data_source, _table_name: self.load_file(data_source),
            DataSourceType.SQL_SERVER.value: lambda data_source, table_name: self.load_sql_table(
                data_source, table_name
            ),
        }

    def load(self, data_source: DataSource, table_name: str | None = None) -> pd.DataFrame:
        loader = self._loaders.get(data_source.source_type)
        if loader is None:
            raise UnsupportedDataSourceError(
                f"No dataset loader is registered for source type '{data_source.source_type}'."
            )
        return loader(data_source, table_name)

    def load_file(self, data_source: DataSource) -> pd.DataFrame:
        if data_source.source_type != DataSourceType.FILE.value or not data_source.stored_filename:
            raise UnsupportedDataSourceError(
                "This operation is only available for uploaded file data sources."
            )

        reader = _FILE_READERS.get(data_source.file_format or "")
        if reader is None:
            raise UnsupportedDataSourceError(
                f"Reading is not supported for file format '{data_source.file_format}'."
            )

        file_path = self._file_storage.get_file_path(data_source.stored_filename)
        try:
            return reader(file_path)
        except Exception as read_error:
            raise DatasetLoadError(f"Could not read dataset file: {read_error}") from read_error

    def load_sql_table(self, data_source: DataSource, table_name: str | None) -> pd.DataFrame:
        if not table_name:
            raise DatasetLoadError("A table name is required to read a SQL Server data source.")

        connection_string = self._sql_server_connection_service.build_connection_string(
            data_source
        )
        try:
            with pyodbc.connect(
                connection_string, timeout=_QUERY_TIMEOUT_SECONDS
            ) as connection:
                return pd.read_sql(f"SELECT * FROM [{table_name}]", connection)
        except Exception as read_error:
            raise DatasetLoadError(f"Could not read table '{table_name}': {read_error}") from read_error
