from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    AdminUserDep,
    CurrentUserDep,
    ensure_company_access,
    require_company_member,
)
from app.schemas.auth_schema import CurrentUser
from app.core.config import Settings, get_settings
from app.db.database import get_database_session
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.dataset_version_repository import DatasetVersionRepository
from app.schemas.data_cleaning_schema import (
    CleaningMethodsCatalog,
    CleaningPipelineRequest,
    CleaningRecommendationsResponse,
    DatasetVersionResponse,
    PipelinePreviewResponse,
)
from app.services.cleaning.recommendations import CleaningRecommendationService
from app.services.cleaning.registry import build_default_registry
from app.services.cleaning.service import DataCleaningService, NoVersionToUndoError
from app.services.cleaning.strategy import UnknownStrategyError
from app.services.dataset_frame_service import (
    DatasetFrameService,
    MissingTableNameError,
    UnknownTableError,
)
from app.services.profiling.loaders import DatasetLoadError, DatasetLoader
from app.services.profiling.service import (
    DataProfileService,
    NonNumericColumnError,
    UnknownColumnError,
)
from app.services.sql_server_connection_service import (
    SqlServerConnectionService,
    SqlServerDriverNotFoundError,
    SqlServerQueryError,
)
from app.storage.local import LocalFileStorage

router = APIRouter(
    prefix="/data-sources/{data_source_id}/cleaning",
    tags=["data-cleaning"],
    dependencies=[Depends(require_company_member)],
)

_BAD_REQUEST_ERRORS = (
    MissingTableNameError,
    UnknownTableError,
    UnknownColumnError,
    NonNumericColumnError,
    UnknownStrategyError,
    ValueError,
    NoVersionToUndoError,
)
_UNPROCESSABLE_ERRORS = (DatasetLoadError, SqlServerDriverNotFoundError, SqlServerQueryError)

# One registry per process: strategies are stateless, so building it once and
# sharing it across requests avoids re-importing every operations module per call.
_STRATEGY_REGISTRY = build_default_registry()


def _get_data_source_repository(
    database_session: Annotated[Session, Depends(get_database_session)],
) -> DataSourceRepository:
    return DataSourceRepository(database_session)


def _get_dataset_version_repository(
    database_session: Annotated[Session, Depends(get_database_session)],
) -> DatasetVersionRepository:
    return DatasetVersionRepository(database_session)


def _get_sql_server_connection_service(
    data_source_repository: Annotated[DataSourceRepository, Depends(_get_data_source_repository)],
) -> SqlServerConnectionService:
    return SqlServerConnectionService(data_source_repository)


def _get_dataset_loader(
    settings: Annotated[Settings, Depends(get_settings)],
    sql_server_connection_service: Annotated[
        SqlServerConnectionService, Depends(_get_sql_server_connection_service)
    ],
) -> DatasetLoader:
    return DatasetLoader(
        file_storage=LocalFileStorage(settings.upload_directory),
        sql_server_connection_service=sql_server_connection_service,
    )


def _get_dataset_frame_service(
    dataset_loader: Annotated[DatasetLoader, Depends(_get_dataset_loader)],
    sql_server_connection_service: Annotated[
        SqlServerConnectionService, Depends(_get_sql_server_connection_service)
    ],
) -> DatasetFrameService:
    return DatasetFrameService(
        dataset_loader=dataset_loader,
        sql_server_connection_service=sql_server_connection_service,
    )


def _get_data_profile_service(
    dataset_frame_service: Annotated[DatasetFrameService, Depends(_get_dataset_frame_service)],
) -> DataProfileService:
    return DataProfileService(dataset_frame_service=dataset_frame_service)


def _get_recommendation_service(
    data_profile_service: Annotated[DataProfileService, Depends(_get_data_profile_service)],
    dataset_frame_service: Annotated[DatasetFrameService, Depends(_get_dataset_frame_service)],
) -> CleaningRecommendationService:
    return CleaningRecommendationService(
        data_profile_service=data_profile_service,
        dataset_frame_service=dataset_frame_service,
    )


def get_data_cleaning_service(
    dataset_frame_service: Annotated[DatasetFrameService, Depends(_get_dataset_frame_service)],
    data_profile_service: Annotated[DataProfileService, Depends(_get_data_profile_service)],
    recommendation_service: Annotated[CleaningRecommendationService, Depends(_get_recommendation_service)],
    dataset_version_repository: Annotated[DatasetVersionRepository, Depends(_get_dataset_version_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DataCleaningService:
    return DataCleaningService(
        dataset_frame_service=dataset_frame_service,
        data_profile_service=data_profile_service,
        recommendation_service=recommendation_service,
        strategy_registry=_STRATEGY_REGISTRY,
        dataset_version_repository=dataset_version_repository,
        file_storage=LocalFileStorage(settings.upload_directory),
    )


def _require_data_source(
    data_source_repository: DataSourceRepository,
    data_source_id: str,
    current_user: CurrentUser,
):
    data_source = data_source_repository.get_data_source_by_id(data_source_id)
    if data_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    ensure_company_access(data_source.company_id, current_user)
    return data_source


@router.get("/recommendations", response_model=CleaningRecommendationsResponse)
def get_cleaning_recommendations(
    data_source_id: str,
    current_user: CurrentUserDep,
    data_source_repository: Annotated[DataSourceRepository, Depends(_get_data_source_repository)],
    data_cleaning_service: Annotated[DataCleaningService, Depends(get_data_cleaning_service)],
    table_name: str | None = None,
) -> CleaningRecommendationsResponse:
    """Suggest cleaning strategies per column, with a plain-language reason for each."""
    data_source = _require_data_source(data_source_repository, data_source_id, current_user)
    try:
        return data_cleaning_service.get_recommendations(data_source, table_name)
    except _BAD_REQUEST_ERRORS as bad_request_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(bad_request_error)
        ) from bad_request_error
    except _UNPROCESSABLE_ERRORS as read_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(read_error)
        ) from read_error


@router.get("/methods", response_model=CleaningMethodsCatalog)
def get_cleaning_methods(
    data_source_id: str,
    current_user: CurrentUserDep,
    data_source_repository: Annotated[DataSourceRepository, Depends(_get_data_source_repository)],
    data_cleaning_service: Annotated[DataCleaningService, Depends(get_data_cleaning_service)],
) -> CleaningMethodsCatalog:
    """List every available cleaning method, grouped by category."""
    _require_data_source(data_source_repository, data_source_id, current_user)
    return data_cleaning_service.list_available_methods()


@router.post("/preview", response_model=PipelinePreviewResponse)
def preview_cleaning_pipeline(
    data_source_id: str,
    pipeline_request: CleaningPipelineRequest,
    admin: AdminUserDep,
    data_source_repository: Annotated[DataSourceRepository, Depends(_get_data_source_repository)],
    data_cleaning_service: Annotated[DataCleaningService, Depends(get_data_cleaning_service)],
) -> PipelinePreviewResponse:
    """Run the selected operations against an in-memory copy and report the impact.
    Nothing is written to storage."""
    data_source = _require_data_source(data_source_repository, data_source_id, admin)
    try:
        return data_cleaning_service.preview_pipeline(
            data_source, pipeline_request.table_name, pipeline_request.operations
        )
    except _BAD_REQUEST_ERRORS as bad_request_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(bad_request_error)
        ) from bad_request_error
    except _UNPROCESSABLE_ERRORS as read_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(read_error)
        ) from read_error


@router.post("/apply", response_model=DatasetVersionResponse, status_code=status.HTTP_201_CREATED)
def apply_cleaning_pipeline(
    data_source_id: str,
    pipeline_request: CleaningPipelineRequest,
    admin: AdminUserDep,
    data_source_repository: Annotated[DataSourceRepository, Depends(_get_data_source_repository)],
    data_cleaning_service: Annotated[DataCleaningService, Depends(get_data_cleaning_service)],
) -> DatasetVersionResponse:
    """Apply the selected operations and persist the result as a new dataset version.
    The original data source file is never modified."""
    data_source = _require_data_source(data_source_repository, data_source_id, admin)
    try:
        return data_cleaning_service.apply_pipeline(
            data_source, pipeline_request.table_name, pipeline_request.operations
        )
    except _BAD_REQUEST_ERRORS as bad_request_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(bad_request_error)
        ) from bad_request_error
    except _UNPROCESSABLE_ERRORS as read_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(read_error)
        ) from read_error


@router.get("/versions", response_model=list[DatasetVersionResponse])
def list_dataset_versions(
    data_source_id: str,
    current_user: CurrentUserDep,
    data_source_repository: Annotated[DataSourceRepository, Depends(_get_data_source_repository)],
    data_cleaning_service: Annotated[DataCleaningService, Depends(get_data_cleaning_service)],
) -> list[DatasetVersionResponse]:
    """List every applied cleaning version for this data source, oldest first."""
    data_source = _require_data_source(data_source_repository, data_source_id, current_user)
    return data_cleaning_service.list_versions(data_source)


@router.delete("/versions/latest", status_code=status.HTTP_204_NO_CONTENT)
def undo_last_dataset_version(
    data_source_id: str,
    admin: AdminUserDep,
    data_source_repository: Annotated[DataSourceRepository, Depends(_get_data_source_repository)],
    data_cleaning_service: Annotated[DataCleaningService, Depends(get_data_cleaning_service)],
) -> None:
    """Undo the most recently applied cleaning version, reverting to the one before it."""
    data_source = _require_data_source(data_source_repository, data_source_id, admin)
    try:
        data_cleaning_service.undo_last_version(data_source)
    except NoVersionToUndoError as undo_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(undo_error)
        ) from undo_error
