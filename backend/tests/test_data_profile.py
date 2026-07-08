import io

import pandas as pd

from app.services.profiling.outliers import detect_outliers_iqr
from app.services.profiling.quality_checks import build_data_quality_report

_PROFILE_CSV = (
    b"value,category,half_null,empty_col,text_id\n"
    b"10,A,X,,p1\n"
    b"11,A,X,,p2\n"
    b"9,A,,,p3\n"
    b"10,A,,,p4\n"
    b"1000,A,X,,p5\n"
    b"10,A,X,,p1\n"
)


def _upload_profile_csv(api_client) -> str:
    response = api_client.post(
        "/api/v1/data-sources/upload",
        files={"uploaded_file": ("profile_sample.csv", io.BytesIO(_PROFILE_CSV), "text/csv")},
    )
    return response.json()["id"]


def test_profile_overview_and_data_quality(api_client) -> None:
    data_source_id = _upload_profile_csv(api_client)

    response = api_client.get(f"/api/v1/data-sources/{data_source_id}/profile")
    assert response.status_code == 200
    profile = response.json()

    overview = profile["overview"]
    assert overview["row_count"] == 6
    assert overview["column_count"] == 5
    assert overview["shape"] == [6, 5]
    assert overview["total_duplicate_rows"] == 1
    assert overview["total_missing_values"] == 8
    assert overview["numeric_column_count"] == 1
    assert overview["categorical_column_count"] == 3

    quality = profile["data_quality"]
    assert set(quality["constant_columns"]) == {"category", "empty_col"}
    assert quality["empty_columns"] == ["empty_col"]
    assert set(quality["single_unique_value_columns"]) == {"category", "half_null"}
    high_cardinality_names = {c["column_name"] for c in quality["high_cardinality_columns"]}
    assert "text_id" in high_cardinality_names

    assert len(profile["columns"]) == 5


def test_profile_numeric_statistics_and_outliers(api_client) -> None:
    data_source_id = _upload_profile_csv(api_client)

    response = api_client.get(f"/api/v1/data-sources/{data_source_id}/profile")
    profile = response.json()

    numeric_stats = {s["column_name"]: s for s in profile["numeric_statistics"]}
    value_stats = numeric_stats["value"]
    assert value_stats["count"] == 6
    assert value_stats["mean"] == 175.0
    assert value_stats["minimum"] == 9.0
    assert value_stats["maximum"] == 1000.0

    outliers = {o["column_name"]: o for o in profile["outliers"]}
    value_outliers = outliers["value"]
    assert value_outliers["detection_method"] == "iqr"
    assert value_outliers["outlier_count"] == 1
    assert 4 in value_outliers["sample_outlier_row_indices"]


def test_outlier_rows_endpoint_returns_flagged_rows(api_client) -> None:
    data_source_id = _upload_profile_csv(api_client)

    response = api_client.get(
        f"/api/v1/data-sources/{data_source_id}/profile/outliers",
        params={"column_name": "value"},
    )
    assert response.status_code == 200
    outlier_rows = response.json()
    assert outlier_rows["row_count"] == 1
    assert outlier_rows["rows"][0]["value"] == 1000


def test_profile_sql_server_without_table_name_is_rejected(api_client) -> None:
    create_response = api_client.post(
        "/api/v1/data-sources/sql-server",
        json={
            "connection_name": "warehouse",
            "server_host": "sql.example.internal",
            "database_name": "warehouse",
            "authentication_type": "windows",
        },
    )
    data_source_id = create_response.json()["id"]

    response = api_client.get(f"/api/v1/data-sources/{data_source_id}/profile")
    assert response.status_code == 400


def test_profile_sql_server_unreachable_host_returns_422(api_client) -> None:
    create_response = api_client.post(
        "/api/v1/data-sources/sql-server",
        json={
            "connection_name": "unreachable",
            "server_host": "host-that-does-not-exist.invalid",
            "database_name": "warehouse",
            "authentication_type": "windows",
        },
    )
    data_source_id = create_response.json()["id"]

    response = api_client.get(
        f"/api/v1/data-sources/{data_source_id}/profile", params={"table_name": "sales"}
    )
    assert response.status_code == 422


def test_profile_and_tables_unknown_data_source_returns_404(api_client) -> None:
    assert api_client.get("/api/v1/data-sources/does-not-exist/profile").status_code == 404
    assert api_client.get("/api/v1/data-sources/does-not-exist/tables").status_code == 404
    assert (
        api_client.get(
            "/api/v1/data-sources/does-not-exist/profile/outliers",
            params={"column_name": "value"},
        ).status_code
        == 404
    )


def test_quality_report_detects_mixed_types() -> None:
    # A genuinely mixed-type column can't come from a CSV (pandas coerces a CSV
    # column to one dtype), but it can from an in-memory frame or an Excel sheet
    # with mixed cell types, so this checks the pure function directly.
    dataframe = pd.DataFrame({"mixed": [1, "two", 3.5, "four"], "constant": ["A"] * 4})

    report = build_data_quality_report(dataframe)

    mixed_type_names = {column.column_name for column in report.mixed_type_columns}
    assert "mixed" in mixed_type_names
    assert "constant" in report.constant_columns


def test_detect_outliers_iqr_flags_extreme_value() -> None:
    series = pd.Series([10, 11, 9, 10, 1000, 10])

    result = detect_outliers_iqr(series)

    assert result.outlier_row_indices == [4]


def test_profile_boolean_column_is_treated_as_categorical_not_numeric(api_client) -> None:
    # pandas.api.types.is_numeric_dtype(bool_series) is True, so without an
    # explicit bool exclusion this column gets routed into numeric statistics
    # and numpy's quantile() raises on a boolean array ("boolean subtract").
    csv_content = b"flag,amount\nTrue,10\nFalse,20\nTrue,30\nTrue,40\n"
    upload_response = api_client.post(
        "/api/v1/data-sources/upload",
        files={"uploaded_file": ("bool_column.csv", io.BytesIO(csv_content), "text/csv")},
    )
    data_source_id = upload_response.json()["id"]

    response = api_client.get(f"/api/v1/data-sources/{data_source_id}/profile")
    assert response.status_code == 200
    profile = response.json()

    numeric_column_names = {s["column_name"] for s in profile["numeric_statistics"]}
    categorical_column_names = {s["column_name"] for s in profile["categorical_statistics"]}
    assert "flag" not in numeric_column_names
    assert "flag" in categorical_column_names
    assert "amount" in numeric_column_names
