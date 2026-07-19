from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.ai.dependencies import (
    get_agent_data_profile_service,
    get_agent_dataset_operations_service,
    get_dataset_version_repository,
    get_visualization_service,
)
from app.api.v1.routes.data_source_router import get_data_source_repository
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.dataset_version_repository import DatasetVersionRepository
from app.schemas.export_schema import ExportFormatsResponse, ExportReport
from app.services.dataset_frame_service import (
    MissingTableNameError,
    UnknownDatasetVersionError,
    UnknownTableError,
)
from app.services.dataset_operations_service import DatasetOperationsService
from app.services.export.base import ExportArtifact, UnknownExportFormatError
from app.services.export.report_builder import ExportReportBuilder
from app.services.export.service import ExportService
from app.services.profiling.loaders import DatasetLoadError
from app.services.profiling.service import (
    DataProfileService,
    NonNumericColumnError,
    UnknownColumnError,
)
from app.services.sql_server_connection_service import (
    SqlServerDriverNotFoundError,
    SqlServerQueryError,
)
from app.services.visualization_service import VisualizationError, VisualizationService

router = APIRouter(prefix="/data-sources/{data_source_id}/export", tags=["export"])

_BAD_REQUEST_ERRORS = (
    MissingTableNameError,
    UnknownTableError,
    UnknownColumnError,
    NonNumericColumnError,
    UnknownDatasetVersionError,
    VisualizationError,
)
_UNPROCESSABLE_ERRORS = (
    DatasetLoadError,
    SqlServerDriverNotFoundError,
    SqlServerQueryError,
)


def get_export_service(
    data_profile_service: Annotated[
        DataProfileService, Depends(get_agent_data_profile_service)
    ],
    visualization_service: Annotated[
        VisualizationService, Depends(get_visualization_service)
    ],
    dataset_operations_service: Annotated[
        DatasetOperationsService, Depends(get_agent_dataset_operations_service)
    ],
    dataset_version_repository: Annotated[
        DatasetVersionRepository, Depends(get_dataset_version_repository)
    ],
) -> ExportService:
    report_builder = ExportReportBuilder(
        data_profile_service=data_profile_service,
        visualization_service=visualization_service,
        dataset_version_repository=dataset_version_repository,
    )
    return ExportService(
        report_builder=report_builder,
        dataset_operations_service=dataset_operations_service,
    )


def _require_data_source(data_source_repository: DataSourceRepository, data_source_id: str):
    data_source = data_source_repository.get_data_source_by_id(data_source_id)
    if data_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    return data_source


@router.get("/formats", response_model=ExportFormatsResponse)
def list_export_formats(
    data_source_id: str,
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    export_service: Annotated[ExportService, Depends(get_export_service)],
) -> ExportFormatsResponse:
    """List the available export formats (extensible via the exporter registry)."""
    _require_data_source(data_source_repository, data_source_id)
    return ExportFormatsResponse(formats=export_service.list_formats())


@router.get("/report", response_model=ExportReport)
def get_export_report(
    data_source_id: str,
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    export_service: Annotated[ExportService, Depends(get_export_service)],
    table_name: str | None = None,
    version_id: str | None = None,
) -> ExportReport:
    """Return the fully-assembled analysis report as JSON (for preview / reuse)."""
    data_source = _require_data_source(data_source_repository, data_source_id)
    try:
        return export_service.build_report(data_source, table_name, version_id)
    except _BAD_REQUEST_ERRORS as bad_request_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(bad_request_error)
        ) from bad_request_error
    except _UNPROCESSABLE_ERRORS as read_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(read_error)
        ) from read_error


@router.get("/{format_key}")
def download_export(
    data_source_id: str,
    format_key: str,
    data_source_repository: Annotated[DataSourceRepository, Depends(get_data_source_repository)],
    export_service: Annotated[ExportService, Depends(get_export_service)],
    table_name: str | None = None,
    version_id: str | None = None,
) -> Response:
    """Generate and stream a downloadable export in the requested format."""
    data_source = _require_data_source(data_source_repository, data_source_id)
    try:
        artifact = export_service.export(data_source, format_key, table_name, version_id)
    except UnknownExportFormatError as unknown_format_error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(unknown_format_error)
        ) from unknown_format_error
    except _BAD_REQUEST_ERRORS as bad_request_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(bad_request_error)
        ) from bad_request_error
    except _UNPROCESSABLE_ERRORS as read_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(read_error)
        ) from read_error
    return _artifact_response(artifact)


def _artifact_response(artifact: ExportArtifact) -> Response:
    encoded_name = quote(artifact.filename)
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{artifact.filename}"; '
                f"filename*=UTF-8''{encoded_name}"
            ),
            "Content-Length": str(len(artifact.content)),
        },
    )
