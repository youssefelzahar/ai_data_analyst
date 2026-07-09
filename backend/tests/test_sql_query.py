from types import SimpleNamespace
from datetime import datetime, timezone

import pandas as pd
import pytest

from app.services.profiling.service import DataProfileService
from app.services.sql_query_service import (
    NonSelectStatementError,
    SqlQueryService,
    ensure_read_only,
)
from app.storage.base import FileTooLargeError


class _StubConnectionService:
    """Stands in for SqlServerConnectionService — returns a fixed DataFrame."""

    def __init__(self, dataframe: pd.DataFrame) -> None:
        self._dataframe = dataframe
        self.received_sql: str | None = None

    def run_query(self, data_source, sql: str) -> pd.DataFrame:
        self.received_sql = sql
        return self._dataframe


class _StubFileUploadService:
    def __init__(self) -> None:
        self.last_original_filename: str | None = None

    def upload_dataset(self, original_filename: str | None, file_stream):
        self.last_original_filename = original_filename
        return SimpleNamespace(
            id="saved-id",
            name=original_filename or "query-result.csv",
            source_type="file",
            created_at=datetime.now(timezone.utc),
            original_filename=original_filename,
            file_format="csv",
            file_size_bytes=1,
            server_host=None,
            database_name=None,
            authentication_type=None,
            username=None,
        )


def _sql_server_data_source():
    return SimpleNamespace(name="warehouse", source_type="sql_server", file_size_bytes=None)


def _build_service(
    dataframe: pd.DataFrame,
) -> tuple[SqlQueryService, _StubConnectionService, _StubFileUploadService]:
    connection_service = _StubConnectionService(dataframe)
    file_upload_service = _StubFileUploadService()
    # build_profile_from_dataframe never touches the loader/connection deps.
    profile_service = DataProfileService(dataset_loader=None, sql_server_connection_service=None)
    return (
        SqlQueryService(connection_service, profile_service, file_upload_service),
        connection_service,
        file_upload_service,
    )


# --- ensure_read_only guard -------------------------------------------------

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM sales",
        "  select id from sales  ",
        "-- a comment\nSELECT 1",
        "WITH recent AS (SELECT * FROM sales) SELECT * FROM recent",
        "SELECT * FROM sales;",  # single trailing semicolon is fine
    ],
)
def test_ensure_read_only_accepts_select_queries(sql: str) -> None:
    ensure_read_only(sql)  # should not raise


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM sales",
        "INSERT INTO sales VALUES (1)",
        "UPDATE sales SET price = 0",
        "DROP TABLE sales",
        "TRUNCATE TABLE sales",
        "SELECT 1; DROP TABLE sales",  # stacked statements
        "   ",  # empty after trim
        "/* SELECT */ DELETE FROM sales",  # comment can't disguise a DELETE
    ],
)
def test_ensure_read_only_rejects_non_select(sql: str) -> None:
    with pytest.raises(NonSelectStatementError):
        ensure_read_only(sql)


# --- execute_query ----------------------------------------------------------

def test_execute_query_returns_result_grid() -> None:
    dataframe = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
    service, connection_service, _ = _build_service(dataframe)

    result = service.execute_query(_sql_server_data_source(), "SELECT * FROM t")

    assert connection_service.received_sql == "SELECT * FROM t"
    assert result.columns == ["id", "name"]
    assert result.row_count == 3
    assert result.truncated is False
    assert result.rows[0] == {"id": 1, "name": "a"}


def test_execute_query_caps_rows_and_flags_truncation() -> None:
    dataframe = pd.DataFrame({"n": range(50)})
    service, _, _ = _build_service(dataframe)

    result = service.execute_query(_sql_server_data_source(), "SELECT n FROM t", row_limit=10)

    assert result.row_count == 50
    assert len(result.rows) == 10
    assert result.truncated is True


def test_execute_query_rejects_non_select_before_running() -> None:
    service, connection_service, _ = _build_service(pd.DataFrame({"n": [1]}))

    with pytest.raises(NonSelectStatementError):
        service.execute_query(_sql_server_data_source(), "DELETE FROM t")

    assert connection_service.received_sql is None  # guard ran before the DB


# --- analyze_query ----------------------------------------------------------

def test_analyze_query_returns_preview_and_profile() -> None:
    dataframe = pd.DataFrame({"value": [10, 11, 9, 1000], "label": ["a", "a", "b", "c"]})
    service, _, _ = _build_service(dataframe)

    analysis = service.analyze_query(_sql_server_data_source(), "SELECT * FROM t")

    assert analysis.preview.row_count == 4
    assert analysis.preview.column_names == ["value", "label"]
    assert analysis.profile.overview.row_count == 4
    assert analysis.profile.overview.column_count == 2
    numeric_columns = {s.column_name for s in analysis.profile.numeric_statistics}
    assert "value" in numeric_columns


def test_convert_query_to_dataset_saves_file_data_source() -> None:
    dataframe = pd.DataFrame({"id": [1, 2]})
    service, connection_service, file_upload_service = _build_service(dataframe)

    converted = service.convert_query_to_dataset(_sql_server_data_source(), "SELECT id FROM t")

    assert connection_service.received_sql == "SELECT id FROM t"
    assert file_upload_service.last_original_filename == "warehouse-query-result.csv"
    assert converted.source_type == "file"
    assert converted.original_filename == "warehouse-query-result.csv"


# --- API-level guard (no live DB needed) ------------------------------------

def _create_sql_server_source(api_client) -> str:
    response = api_client.post(
        "/api/v1/data-sources/sql-server",
        json={
            "connection_name": "warehouse",
            "server_host": "sql.example.internal",
            "database_name": "warehouse",
            "authentication_type": "windows",
        },
    )
    return response.json()["id"]


def test_query_endpoint_rejects_non_select_with_400(api_client) -> None:
    data_source_id = _create_sql_server_source(api_client)

    response = api_client.post(
        f"/api/v1/data-sources/{data_source_id}/query",
        json={"sql": "DELETE FROM sales"},
    )
    assert response.status_code == 400


def test_query_endpoint_on_file_source_returns_400(api_client) -> None:
    import io

    upload = api_client.post(
        "/api/v1/data-sources/upload",
        files={"uploaded_file": ("q.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")},
    )
    file_source_id = upload.json()["id"]

    response = api_client.post(
        f"/api/v1/data-sources/{file_source_id}/query",
        json={"sql": "SELECT 1"},
    )
    assert response.status_code == 400


def test_query_endpoint_unknown_source_returns_404(api_client) -> None:
    response = api_client.post(
        "/api/v1/data-sources/does-not-exist/query",
        json={"sql": "SELECT 1"},
    )
    assert response.status_code == 404


def test_convert_query_endpoint_returns_413_when_saved_result_exceeds_upload_limit(
    api_client, monkeypatch
) -> None:
    data_source_id = _create_sql_server_source(api_client)

    def _raise_file_too_large(*args, **kwargs):
        del args, kwargs
        raise FileTooLargeError(1024)

    monkeypatch.setattr(SqlQueryService, "convert_query_to_dataset", _raise_file_too_large)

    response = api_client.post(
        f"/api/v1/data-sources/{data_source_id}/query/convert",
        json={"sql": "SELECT 1"},
    )
    assert response.status_code == 413
    assert "maximum allowed size" in response.json()["detail"]
