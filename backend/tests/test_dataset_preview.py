import io

import pandas as pd


def _upload_csv(api_client, filename: str = "sales_report.csv") -> str:
    file_content = io.BytesIO(
        b"region,revenue,notes\nnorth,100,\nsouth,200,ok\neast,,pending\n"
    )
    response = api_client.post(
        "/api/v1/data-sources/upload",
        files={"uploaded_file": (filename, file_content, "text/csv")},
    )
    return response.json()["id"]


def _upload_excel(api_client, filename: str = "report.xlsx") -> str:
    dataframe = pd.DataFrame({"city": ["paris", "cairo"], "population": [2148000, 9500000]})
    excel_buffer = io.BytesIO()
    dataframe.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)
    response = api_client.post(
        "/api/v1/data-sources/upload",
        files={"uploaded_file": (filename, excel_buffer, "application/octet-stream")},
    )
    return response.json()["id"]


def test_preview_csv_returns_shape_columns_dtypes_and_rows(api_client) -> None:
    data_source_id = _upload_csv(api_client)

    response = api_client.get(f"/api/v1/data-sources/{data_source_id}/preview")
    assert response.status_code == 200

    preview = response.json()
    assert preview["row_count"] == 3
    assert preview["column_count"] == 3
    assert preview["column_names"] == ["region", "revenue", "notes"]
    assert set(preview["dtypes"]) == {"region", "revenue", "notes"}
    assert preview["missing_value_counts"]["revenue"] == 1
    assert len(preview["preview_rows"]) == 3
    assert preview["preview_rows"][0]["region"] == "north"


def test_preview_row_count_is_configurable(api_client) -> None:
    data_source_id = _upload_csv(api_client)

    response = api_client.get(
        f"/api/v1/data-sources/{data_source_id}/preview", params={"preview_row_count": 1}
    )
    assert response.status_code == 200
    assert len(response.json()["preview_rows"]) == 1


def test_preview_excel_file(api_client) -> None:
    data_source_id = _upload_excel(api_client)

    response = api_client.get(f"/api/v1/data-sources/{data_source_id}/preview")
    assert response.status_code == 200

    preview = response.json()
    assert preview["row_count"] == 2
    assert preview["column_names"] == ["city", "population"]


def test_preview_rejects_sql_server_data_source(api_client) -> None:
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

    response = api_client.get(f"/api/v1/data-sources/{data_source_id}/preview")
    assert response.status_code == 400


def test_preview_unknown_data_source_returns_404(api_client) -> None:
    response = api_client.get("/api/v1/data-sources/does-not-exist/preview")
    assert response.status_code == 404
