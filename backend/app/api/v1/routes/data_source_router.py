from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.database import get_database_session
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.data_profile_schema import DataProfileResponse, OutlierRowsResponse
from app.schemas.data_source_schema import (
    ConnectionTestResult,
    DataSourceResponse,
    DataSourceType,
    DatasetPreviewResponse,
    SqlServerConnectionCreate,
)
from app.schemas.sql_query_schema import (
    QueryAnalysisResponse,
    QueryResultResponse,
    SqlQueryRequest,
)
from app.services.dataset_preview_service import DatasetPreviewService
from app.services.file_upload_service import FileUploadService
from app.services.profiling.loaders import DatasetLoadError, DatasetLoader, UnsupportedDataSourceError
from app.services.profiling.outliers import UnknownOutlierMethodError
from app.services.profiling.service import (
    DataProfileService,
    MissingTableNameError,
    NonNumericColumnError,
    UnknownColumnError,
    UnknownTableError,
)
from app.services.sql_query_service import NonSelectStatementError, SqlQueryService
from app.services.sql_server_connection_service import (
    SqlServerConnectionService,
    SqlServerDriverNotFoundError,
    SqlServerQueryError,
)
from app.storage.base import FileTooLargeError
from app.storage.local import LocalFileStorage
from app.validators.file_upload_validator import FileUploadValidator, UploadValidationError

router = APIRouter(prefix="/data-sources", tags=["data-sources"])

_BAD_REQUEST_ERRORS = (
    UnsupportedDataSourceError,
    MissingTableNameError,
    UnknownTableError,
    UnknownColumnError,
    NonNumericColumnError,
    UnknownOutlierMethodError,
    NonSelectStatementError,
)
_UNPROCESSABLE_ERRORS = (DatasetLoadError, SqlServerDriverNotFoundError, SqlServerQueryError)


def get_data_source_repository(
    database_session: Annotated[Session, Depends(get_database_session)],
) -> DataSourceRepository:
    return DataSourceRepository(database_session)


def get_file_upload_service(
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileUploadService:
    return FileUploadService(
        data_source_repository=data_source_repository,
        file_storage=LocalFileStorage(settings.upload_directory),
        upload_validator=FileUploadValidator(),
        max_upload_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )


def get_sql_server_connection_service(
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
) -> SqlServerConnectionService:
    return SqlServerConnectionService(data_source_repository)


def get_dataset_loader(
    settings: Annotated[Settings, Depends(get_settings)],
    sql_server_connection_service: Annotated[
        SqlServerConnectionService, Depends(get_sql_server_connection_service)
    ],
) -> DatasetLoader:
    return DatasetLoader(
        file_storage=LocalFileStorage(settings.upload_directory),
        sql_server_connection_service=sql_server_connection_service,
    )


def get_dataset_preview_service(
    dataset_loader: Annotated[DatasetLoader, Depends(get_dataset_loader)],
) -> DatasetPreviewService:
    return DatasetPreviewService(dataset_loader=dataset_loader)


def get_data_profile_service(
    dataset_loader: Annotated[DatasetLoader, Depends(get_dataset_loader)],
    sql_server_connection_service: Annotated[
        SqlServerConnectionService, Depends(get_sql_server_connection_service)
    ],
) -> DataProfileService:
    return DataProfileService(
        dataset_loader=dataset_loader,
        sql_server_connection_service=sql_server_connection_service,
    )


def get_sql_query_service(
    sql_server_connection_service: Annotated[
        SqlServerConnectionService, Depends(get_sql_server_connection_service)
    ],
    data_profile_service: Annotated[DataProfileService, Depends(get_data_profile_service)],
    file_upload_service: Annotated[FileUploadService, Depends(get_file_upload_service)],
) -> SqlQueryService:
    return SqlQueryService(
        sql_server_connection_service=sql_server_connection_service,
        data_profile_service=data_profile_service,
        file_upload_service=file_upload_service,
    )


@router.post(
    "/upload",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_dataset(
    uploaded_file: UploadFile,
    file_upload_service: Annotated[FileUploadService, Depends(get_file_upload_service)],
) -> DataSourceResponse:
    """Upload a CSV or Excel file and register it as a data source."""
    try:
        saved_data_source = file_upload_service.upload_dataset(
            original_filename=uploaded_file.filename,
            file_stream=uploaded_file.file,
        )
    except UploadValidationError as validation_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(validation_error)
        ) from validation_error
    except FileTooLargeError as size_error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(size_error)
        ) from size_error
    return DataSourceResponse.model_validate(saved_data_source)


@router.post(
    "/sql-server",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_sql_server_data_source(
    connection_config: SqlServerConnectionCreate,
    sql_server_connection_service: Annotated[
        SqlServerConnectionService, Depends(get_sql_server_connection_service)
    ],
) -> DataSourceResponse:
    """Save a SQL Server connection configuration as a data source."""
    saved_data_source = sql_server_connection_service.create_data_source(connection_config)
    return DataSourceResponse.model_validate(saved_data_source)


@router.post("/sql-server/test", response_model=ConnectionTestResult)
def test_sql_server_connection(
    connection_config: SqlServerConnectionCreate,
    sql_server_connection_service: Annotated[
        SqlServerConnectionService, Depends(get_sql_server_connection_service)
    ],
) -> ConnectionTestResult:
    """Attempt to connect with the given configuration without saving it."""
    return sql_server_connection_service.test_data_source_connection(connection_config)


@router.get("", response_model=list[DataSourceResponse])
def list_data_sources(
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    source_type: DataSourceType | None = None,
) -> list[DataSourceResponse]:
    """List registered data sources, optionally filtered by type."""
    data_sources = data_source_repository.list_data_sources(
        source_type.value if source_type else None
    )
    return [DataSourceResponse.model_validate(data_source) for data_source in data_sources]


@router.get("/{data_source_id}", response_model=DataSourceResponse)
def get_data_source_by_id(
    data_source_id: str,
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
) -> DataSourceResponse:
    data_source = data_source_repository.get_data_source_by_id(data_source_id)
    if data_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    return DataSourceResponse.model_validate(data_source)


@router.get("/{data_source_id}/tables", response_model=list[str])
def list_data_source_tables(
    data_source_id: str,
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    sql_server_connection_service: Annotated[
        SqlServerConnectionService, Depends(get_sql_server_connection_service)
    ],
) -> list[str]:
    """List the tables available in a SQL Server data source's database."""
    data_source = data_source_repository.get_data_source_by_id(data_source_id)
    if data_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    if data_source.source_type != DataSourceType.SQL_SERVER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Listing tables is only available for SQL Server data sources.",
        )
    try:
        return sql_server_connection_service.list_tables(data_source)
    except _UNPROCESSABLE_ERRORS as read_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(read_error)
        ) from read_error


@router.get("/{data_source_id}/preview", response_model=DatasetPreviewResponse)
def preview_data_source(
    data_source_id: str,
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    dataset_preview_service: Annotated[DatasetPreviewService, Depends(get_dataset_preview_service)],
    preview_row_count: int = 10,
) -> DatasetPreviewResponse:
    """Read the underlying file and return its shape, columns, dtypes, and a sample of rows."""
    data_source = data_source_repository.get_data_source_by_id(data_source_id)
    if data_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    try:
        return dataset_preview_service.get_preview(data_source, preview_row_count)
    except UnsupportedDataSourceError as unsupported_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(unsupported_error)
        ) from unsupported_error
    except DatasetLoadError as read_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(read_error)
        ) from read_error


@router.get("/{data_source_id}/profile", response_model=DataProfileResponse)
def profile_data_source(
    data_source_id: str,
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    data_profile_service: Annotated[DataProfileService, Depends(get_data_profile_service)],
    table_name: str | None = None,
) -> DataProfileResponse:
    """Build a full statistical profile: overview, columns, numeric/categorical stats,
    data-quality checks, and outlier reports — for a file or a SQL Server table."""
    data_source = data_source_repository.get_data_source_by_id(data_source_id)
    if data_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    try:
        return data_profile_service.get_profile(data_source, table_name)
    except _BAD_REQUEST_ERRORS as bad_request_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(bad_request_error)
        ) from bad_request_error
    except _UNPROCESSABLE_ERRORS as read_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(read_error)
        ) from read_error


@router.get("/{data_source_id}/profile/outliers", response_model=OutlierRowsResponse)
def get_data_source_outlier_rows(
    data_source_id: str,
    column_name: str,
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    data_profile_service: Annotated[DataProfileService, Depends(get_data_profile_service)],
    table_name: str | None = None,
    method: str = "iqr",
) -> OutlierRowsResponse:
    """Return the actual rows flagged as outliers for one numeric column."""
    data_source = data_source_repository.get_data_source_by_id(data_source_id)
    if data_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    try:
        return data_profile_service.get_outlier_rows(data_source, column_name, table_name, method)
    except _BAD_REQUEST_ERRORS as bad_request_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(bad_request_error)
        ) from bad_request_error
    except _UNPROCESSABLE_ERRORS as read_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(read_error)
        ) from read_error


def _require_sql_server_data_source(data_source_repository: DataSourceRepository, data_source_id: str):
    data_source = data_source_repository.get_data_source_by_id(data_source_id)
    if data_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    if data_source.source_type != DataSourceType.SQL_SERVER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Running queries is only available for SQL Server data sources.",
        )
    return data_source


@router.post("/{data_source_id}/query", response_model=QueryResultResponse)
def run_data_source_query(
    data_source_id: str,
    query_request: SqlQueryRequest,
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    sql_query_service: Annotated[SqlQueryService, Depends(get_sql_query_service)],
) -> QueryResultResponse:
    """Execute a read-only SELECT query and return a row-capped result grid."""
    data_source = _require_sql_server_data_source(data_source_repository, data_source_id)
    try:
        return sql_query_service.execute_query(data_source, query_request.sql)
    except _BAD_REQUEST_ERRORS as bad_request_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(bad_request_error)
        ) from bad_request_error
    except _UNPROCESSABLE_ERRORS as read_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(read_error)
        ) from read_error


@router.post("/{data_source_id}/query/analyze", response_model=QueryAnalysisResponse)
def analyze_data_source_query(
    data_source_id: str,
    query_request: SqlQueryRequest,
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    sql_query_service: Annotated[SqlQueryService, Depends(get_sql_query_service)],
) -> QueryAnalysisResponse:
    """Run the query via pd.read_sql and return the standard preview + profile."""
    data_source = _require_sql_server_data_source(data_source_repository, data_source_id)
    try:
        return sql_query_service.analyze_query(data_source, query_request.sql)
    except _BAD_REQUEST_ERRORS as bad_request_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(bad_request_error)
        ) from bad_request_error
    except _UNPROCESSABLE_ERRORS as read_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(read_error)
        ) from read_error


@router.post(
    "/{data_source_id}/query/convert",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def convert_data_source_query_to_dataset(
    data_source_id: str,
    query_request: SqlQueryRequest,
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    sql_query_service: Annotated[SqlQueryService, Depends(get_sql_query_service)],
) -> DataSourceResponse:
    """Run the query and save the result as a file data source for preview/profile workflows."""
    data_source = _require_sql_server_data_source(data_source_repository, data_source_id)
    try:
        return sql_query_service.convert_query_to_dataset(data_source, query_request.sql)
    except _BAD_REQUEST_ERRORS as bad_request_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(bad_request_error)
        ) from bad_request_error
    except _UNPROCESSABLE_ERRORS as read_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(read_error)
        ) from read_error


@router.delete("/{data_source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_data_source(
    data_source_id: str,
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    file_upload_service: Annotated[FileUploadService, Depends(get_file_upload_service)],
) -> None:
    """Delete a data source and, for uploaded files, its stored file."""
    data_source = data_source_repository.get_data_source_by_id(data_source_id)
    if data_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    file_upload_service.delete_uploaded_file(data_source)
    data_source_repository.delete_data_source(data_source)
