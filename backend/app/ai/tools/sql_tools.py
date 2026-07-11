import json
import re
from typing import Any

from app.ai.tools.dataset_tools import DatasetToolExecutionError
from app.ai.tools.registry import ToolContext, ToolResult
from app.db.models.data_source_model import DataSource
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.data_source_schema import DataSourceType
from app.services.dataset_frame_service import UnknownTableError
from app.services.profiling.loaders import DatasetLoadError
from app.services.sql_query_service import NonSelectStatementError, SqlQueryService
from app.services.sql_server_connection_service import (
    SqlServerDriverNotFoundError,
    SqlServerConnectionService,
    SqlServerQueryError,
)

_MAX_PAGE_SIZE = 100


class SqlToolBase:
    name = ""
    description = ""
    intents: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    def __init__(
        self,
        data_source_repository: DataSourceRepository,
        sql_server_connection_service: SqlServerConnectionService,
        sql_query_service: SqlQueryService,
    ) -> None:
        self._data_source_repository = data_source_repository
        self._sql_server_connection_service = sql_server_connection_service
        self._sql_query_service = sql_query_service

    def execute(self, context: ToolContext) -> ToolResult:
        try:
            data_source = self._require_sql_data_source(context)
            payload = self._run(context, data_source)
            return ToolResult(
                tool_name=self.name,
                content=json.dumps(payload, indent=2, sort_keys=True),
                metadata={"status": "ok", "result": payload},
            )
        except (
            DatasetToolExecutionError,
            NonSelectStatementError,
            SqlServerDriverNotFoundError,
            SqlServerQueryError,
            DatasetLoadError,
            UnknownTableError,
        ) as error:
            payload = {"error": str(error)}
            return ToolResult(
                tool_name=self.name,
                content=json.dumps(payload, indent=2, sort_keys=True),
                metadata={"status": "error", "result": payload},
            )

    def _run(self, context: ToolContext, data_source: DataSource) -> dict[str, Any]:
        raise NotImplementedError

    def _require_sql_data_source(self, context: ToolContext) -> DataSource:
        if not context.selected_data_source_id:
            raise DatasetToolExecutionError("Select a SQL Server data source first.")
        data_source = self._data_source_repository.get_data_source_by_id(
            context.selected_data_source_id
        )
        if data_source is None:
            raise DatasetToolExecutionError(
                f"Data source '{context.selected_data_source_id}' was not found."
            )
        if data_source.source_type != DataSourceType.SQL_SERVER.value:
            raise DatasetToolExecutionError(
                "These database tools only work with SQL Server data sources."
            )
        return data_source

    @staticmethod
    def _resolve_table_name(context: ToolContext) -> str | None:
        active_table = context.session_context.get("active_table")
        if isinstance(active_table, str) and active_table.strip():
            return active_table.strip()
        table_match = re.search(
            r"\btable\s+([A-Za-z_][\w$#@-]*)",
            context.user_request,
            re.IGNORECASE,
        )
        if table_match:
            return table_match.group(1)
        return None


class SqlListTablesTool(SqlToolBase):
    name = "sql_list_tables"
    description = "Lists the tables available in the selected SQL Server database."
    intents = ("sql_list_tables",)
    keywords = ("list tables", "show tables", "database tables", "available tables")

    def _run(self, context: ToolContext, data_source: DataSource) -> dict[str, Any]:
        del context
        tables = self._sql_server_connection_service.list_tables(data_source)
        return {"table_count": len(tables), "tables": tables}


class SqlColumnMetadataTool(SqlToolBase):
    name = "sql_column_metadata"
    description = "Returns column definitions for a SQL Server table."
    intents = ("sql_column_metadata",)
    keywords = ("column metadata", "table schema", "table columns", "column types")

    def _run(self, context: ToolContext, data_source: DataSource) -> dict[str, Any]:
        table_name = self._resolve_table_name(context)
        if not table_name:
            raise DatasetToolExecutionError("Specify which table you want column metadata for.")
        metadata = self._sql_query_service.get_table_metadata(data_source, table_name)
        return metadata.model_dump(mode="json")


class SqlPreviewTableTool(SqlToolBase):
    name = "sql_preview_table"
    description = "Returns a paginated preview of rows from a SQL Server table."
    intents = ("sql_preview_table",)
    keywords = ("preview table", "show table", "table preview", "first rows from table")

    def _run(self, context: ToolContext, data_source: DataSource) -> dict[str, Any]:
        table_name = self._resolve_table_name(context)
        if not table_name:
            raise DatasetToolExecutionError("Specify which table you want to preview.")
        page = _extract_page(context.user_request)
        page_size = _extract_page_size(context.user_request, default=25)
        preview = self._sql_query_service.preview_table(data_source, table_name, page, page_size)
        return preview.model_dump(mode="json")


class SqlExecuteQueryTool(SqlToolBase):
    name = "sql_execute_query"
    description = "Executes a validated read-only SQL query against the selected database."
    intents = ("sql_execute_query",)
    keywords = ("select", "with", "sql query", "run query", "execute query")

    def _run(self, context: ToolContext, data_source: DataSource) -> dict[str, Any]:
        sql = _extract_sql(context.user_request)
        if not sql:
            raise DatasetToolExecutionError(
                "Provide a read-only SQL query starting with SELECT or WITH."
            )
        page = _extract_page(context.user_request)
        page_size = _extract_page_size(context.user_request, default=50)
        result = self._sql_query_service.execute_query(
            data_source,
            sql,
            page=page,
            page_size=page_size,
        )
        return result.model_dump(mode="json")


def build_sql_tools(
    data_source_repository: DataSourceRepository,
    sql_server_connection_service: SqlServerConnectionService,
    sql_query_service: SqlQueryService,
) -> list[SqlToolBase]:
    return [
        SqlListTablesTool(
            data_source_repository,
            sql_server_connection_service,
            sql_query_service,
        ),
        SqlColumnMetadataTool(
            data_source_repository,
            sql_server_connection_service,
            sql_query_service,
        ),
        SqlPreviewTableTool(
            data_source_repository,
            sql_server_connection_service,
            sql_query_service,
        ),
        SqlExecuteQueryTool(
            data_source_repository,
            sql_server_connection_service,
            sql_query_service,
        ),
    ]


def _extract_sql(user_request: str) -> str | None:
    stripped_request = user_request.strip()
    sql_match = re.search(r"(?is)\b(select|with)\b.+", stripped_request)
    if sql_match is None:
        return None
    return sql_match.group(0).strip()


def _extract_page(user_request: str) -> int:
    match = re.search(r"\bpage\s+(\d+)\b", user_request, re.IGNORECASE)
    if match is None:
        return 1
    return max(1, int(match.group(1)))


def _extract_page_size(user_request: str, default: int) -> int:
    match = re.search(
        r"\b(?:page size|limit|top|first)\s+(\d+)\b",
        user_request,
        re.IGNORECASE,
    )
    if match is None:
        return default
    return max(1, min(int(match.group(1)), _MAX_PAGE_SIZE))
