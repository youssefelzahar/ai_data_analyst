import re
from io import BytesIO

from app.db.models.data_source_model import DataSource
from app.schemas.data_source_schema import DataSourceResponse
from app.schemas.sql_query_schema import (
    QueryAnalysisResponse,
    QueryPagination,
    QueryResultResponse,
    QueryValidationResponse,
    SqlTableMetadataResponse,
    SqlTablePreviewResponse,
)
from app.services.file_upload_service import FileUploadService
from app.services.dataset_preview_service import build_preview_response
from app.services.dataset_frame_service import UnknownTableError
from app.services.json_safe import to_json_safe
from app.services.profiling.service import DataProfileService
from app.services.sql_server_connection_service import SqlServerConnectionService

# Rows returned to the results grid; the full result is still used for profiling.
DEFAULT_ROW_LIMIT = 1000
# Rows sampled into the preview panel after "Convert to pandas".
PREVIEW_ROW_COUNT = 10

_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_FORBIDDEN_SQL_KEYWORDS = ("DROP", "DELETE", "UPDATE", "ALTER", "TRUNCATE", "INSERT", "MERGE", "EXEC")


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

    for forbidden_keyword in _FORBIDDEN_SQL_KEYWORDS:
        if re.search(rf"\b{forbidden_keyword}\b", cleaned, re.IGNORECASE):
            raise NonSelectStatementError(
                f"Forbidden SQL keyword detected: {forbidden_keyword}. Only read operations are allowed."
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
        page: int = 1,
        page_size: int = DEFAULT_ROW_LIMIT,
        row_limit: int = DEFAULT_ROW_LIMIT,
    ) -> QueryResultResponse:
        ensure_read_only(sql)
        dataframe = self._sql_server_connection_service.run_query(data_source, sql)

        total_rows = len(dataframe)
        bounded_page_size = max(1, min(page_size, row_limit))
        bounded_page = max(1, page)
        start_index = (bounded_page - 1) * bounded_page_size
        end_index = start_index + bounded_page_size
        paged_dataframe = dataframe.iloc[start_index:end_index]
        rows = [
            {column: to_json_safe(value) for column, value in row.items()}
            for row in paged_dataframe.to_dict(orient="records")
        ]
        total_pages = max(1, (total_rows + bounded_page_size - 1) // bounded_page_size)
        return QueryResultResponse(
            columns=list(dataframe.columns),
            rows=rows,
            row_count=total_rows,
            truncated=total_rows > len(rows),
            pagination=QueryPagination(
                page=bounded_page,
                page_size=bounded_page_size,
                total_pages=total_pages,
                total_rows=total_rows,
            ),
        )

    def validate_query(self, sql: str) -> QueryValidationResponse:
        normalized_sql = _strip_comments(sql).strip().rstrip(";")
        ensure_read_only(sql)
        return QueryValidationResponse(
            is_valid=True,
            normalized_sql=normalized_sql,
            message="The query is valid for read-only execution.",
        )

    def get_table_metadata(
        self,
        data_source: DataSource,
        table_name: str,
    ) -> SqlTableMetadataResponse:
        self._ensure_known_table(data_source, table_name)
        columns = self._sql_server_connection_service.list_columns(data_source, table_name)
        return SqlTableMetadataResponse(table_name=table_name, columns=columns)

    def preview_table(
        self,
        data_source: DataSource,
        table_name: str,
        page: int = 1,
        page_size: int = 25,
    ) -> SqlTablePreviewResponse:
        self._ensure_known_table(data_source, table_name)
        bounded_page_size = max(1, min(page_size, 100))
        bounded_page = max(1, page)
        offset = (bounded_page - 1) * bounded_page_size
        total_rows = self._sql_server_connection_service.get_table_row_count(data_source, table_name)
        dataframe = self._sql_server_connection_service.preview_table(
            data_source=data_source,
            table_name=table_name,
            offset=offset,
            limit=bounded_page_size,
        )
        rows = [
            {column: to_json_safe(value) for column, value in row.items()}
            for row in dataframe.to_dict(orient="records")
        ]
        total_pages = max(1, (total_rows + bounded_page_size - 1) // bounded_page_size)
        return SqlTablePreviewResponse(
            table_name=table_name,
            columns=list(dataframe.columns),
            rows=rows,
            pagination=QueryPagination(
                page=bounded_page,
                page_size=bounded_page_size,
                total_pages=total_pages,
                total_rows=total_rows,
            ),
        )

    def _ensure_known_table(self, data_source: DataSource, table_name: str) -> None:
        available_tables = self._sql_server_connection_service.list_tables(data_source)
        if table_name not in available_tables:
            raise UnknownTableError(f"Table '{table_name}' was not found in this data source.")

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
