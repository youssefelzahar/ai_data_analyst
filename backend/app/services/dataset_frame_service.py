import pandas as pd

from app.db.models.data_source_model import DataSource
from app.schemas.data_source_schema import DataSourceType
from app.services.profiling.loaders import DatasetLoader
from app.services.sql_server_connection_service import SqlServerConnectionService


class MissingTableNameError(Exception):
    """Raised when an operation targets a SQL Server source without a table name."""


class UnknownTableError(Exception):
    """Raised when the requested table does not exist in the SQL Server source."""


class DatasetFrameService:
    """Loads validated data-source content into a pandas DataFrame."""

    def __init__(
        self,
        dataset_loader: DatasetLoader,
        sql_server_connection_service: SqlServerConnectionService,
    ) -> None:
        self._dataset_loader = dataset_loader
        self._sql_server_connection_service = sql_server_connection_service

    def load_dataframe(
        self,
        data_source: DataSource,
        table_name: str | None = None,
    ) -> pd.DataFrame:
        if data_source.source_type == DataSourceType.SQL_SERVER.value:
            if not table_name:
                raise MissingTableNameError(
                    "A table_name is required for SQL Server data sources."
                )
            available_tables = self._sql_server_connection_service.list_tables(data_source)
            if table_name not in available_tables:
                raise UnknownTableError(
                    f"Table '{table_name}' was not found in this data source."
                )

        return self._dataset_loader.load(data_source, table_name)
