from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.database import get_database_session
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.data_source_schema import (
    ConnectionTestResult,
    DataSourceResponse,
    DataSourceType,
    SqlServerConnectionCreate,
)
from app.services.file_upload_service import FileUploadService
from app.services.sql_server_connection_service import SqlServerConnectionService
from app.storage.base import FileTooLargeError
from app.storage.local import LocalFileStorage
from app.validators.file_upload_validator import FileUploadValidator, UploadValidationError

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


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