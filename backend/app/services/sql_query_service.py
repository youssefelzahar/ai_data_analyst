import re
from io import BytesIO

from app.db.models.data_source_model import DataSource
from app.schemas.data_source_schema import DataSourceResponse
from app.schemas.sql_query_schema import QueryAnalysisResponse, QueryResultResponse
from app.services.file_upload_service import FileUploadService
from app.services.dataset_preview_service import build_preview_response
from app.services.json_safe import to_json_safe
from app.services.profiling.service import DataProfileService
from app.services.sql_server_connection_service import SqlServerConnectionService

# Rows returned to the results grid; the full result is still used for profiling.
DEFAULT_ROW_LIMIT = 1000
# Rows sampled into the preview panel after "Convert to pandas".
PREVIEW_ROW_COUNT = 10

_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


class NonSelectStatementError(Exception):
    """Raised when a query is not a single read-only SELECT statement."""


def _strip_comments(sql: str) -> str:
    return _BLOCK_COMMENT.sub(" ", _LINE_COMMENT.sub("", sql))


def ensure_read_only(sql: str) -> None:
    """Guard against anything that is not a single read-only SELECT.

    This is defense-in-depth for an analysis tool — the real boundary is the
    permissions of the SQL Server login used by the connection. Use a
    read-only database account for the connection where possible.
    """
    cleaned = _strip_comments(sql).strip()
    if not cleaned:
        raise NonSelectStatementError("The query is empty.")

    # Reject stacked statements: only a single trailing ';' is allowed.
    if ";" in cleaned.rstrip().rstrip(";"):
        raise NonSelectStatementError(
            "Only a single statement is allowed. Remove extra ';'-separated statements."
        )

    first_keyword = re.match(r"\s*([A-Za-z]+)", cleaned)
    keyword = first_keyword.group(1).upper() if first_keyword else ""
    if keyword not in {"SELECT", "WITH"}:
        raise NonSelectStatementError(
            "Only read-only SELECT queries are allowed "
            "(INSERT, UPDATE, DELETE, and DDL statements are blocked)."
        )


class SqlQueryService:
    """Runs ad-hoc read-only SQL against a saved SQL Server connection and,
    on request, turns the result into the standard preview + profile."""

    def __init__(
        self,
        sql_server_connection_service: SqlServerConnectionService,
        data_profile_service: DataProfileService,
        file_upload_service: FileUploadService,
    ) -> None:
        self._sql_server_connection_service = sql_server_connection_service
        self._data_profile_service = data_profile_service
        self._file_upload_service = file_upload_service

    def execute_query(
        self,
        data_source: DataSource,
        sql: str,
        row_limit: int = DEFAULT_ROW_LIMIT,
    ) -> QueryResultResponse:
        ensure_read_only(sql)
        dataframe = self._sql_server_connection_service.run_query(data_source, sql)

        total_rows = len(dataframe)
        rows = [
            {column: to_json_safe(value) for column, value in row.items()}
            for row in dataframe.head(row_limit).to_dict(orient="records")
        ]
        return QueryResultResponse(
            columns=list(dataframe.columns),
            rows=rows,
            row_count=total_rows,
            truncated=total_rows > row_limit,
        )

    def analyze_query(self, data_source: DataSource, sql: str) -> QueryAnalysisResponse:
        ensure_read_only(sql)
        dataframe = self._sql_server_connection_service.run_query(data_source, sql)

        preview = build_preview_response(dataframe, PREVIEW_ROW_COUNT)
        profile = self._data_profile_service.build_profile_from_dataframe(
            dataframe,
            dataset_name=f"{data_source.name} · query",
            source_type=data_source.source_type,
        )
        return QueryAnalysisResponse(preview=preview, profile=profile)

    def convert_query_to_dataset(self, data_source: DataSource, sql: str) -> DataSourceResponse:
        """Persist a query result as a file data source so it appears with uploaded datasets."""
        ensure_read_only(sql)
        dataframe = self._sql_server_connection_service.run_query(data_source, sql)

        csv_payload = dataframe.to_csv(index=False).encode("utf-8")
        saved_data_source = self._file_upload_service.upload_dataset(
            original_filename=f"{data_source.name}-query-result.csv",
            file_stream=BytesIO(csv_payload),
        )
        return DataSourceResponse.model_validate(saved_data_source)
