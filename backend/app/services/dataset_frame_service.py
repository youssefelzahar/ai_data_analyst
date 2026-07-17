import pandas as pd

from app.db.models.data_source_model import DataSource
from app.repositories.dataset_version_repository import DatasetVersionRepository
from app.schemas.data_source_schema import DataSourceType
from app.services.profiling.loaders import DatasetLoadError, DatasetLoader
from app.services.sql_server_connection_service import SqlServerConnectionService
from app.storage.base import FileStorage


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
        dataset_version_repository: DatasetVersionRepository | None = None,
        file_storage: FileStorage | None = None,
        use_latest_version: bool = False,
    ) -> None:
        self._dataset_loader = dataset_loader
        self._sql_server_connection_service = sql_server_connection_service
        self._dataset_version_repository = dataset_version_repository
        self._file_storage = file_storage
        self._use_latest_version = use_latest_version

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

        if (
            self._use_latest_version
            and data_source.source_type == DataSourceType.FILE.value
            and self._dataset_version_repository is not None
            and self._file_storage is not None
        ):
            latest_version = self._dataset_version_repository.get_latest(data_source.id)
            if latest_version is not None:
                file_path = self._file_storage.get_file_path(latest_version.stored_filename)
                try:
                    return pd.read_csv(file_path)
                except Exception as read_error:
                    raise DatasetLoadError(
                        f"Could not read cleaned dataset version: {read_error}"
                    ) from read_error

        return self._dataset_loader.load(data_source, table_name)
