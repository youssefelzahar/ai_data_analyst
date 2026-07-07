import io


def _build_csv_upload(filename: str = "sales_report.csv"):
    file_content = io.BytesIO(b"region,revenue\nnorth,100\nsouth,200\n")
    return {"uploaded_file": (filename, file_content, "text/csv")}


def test_upload_csv_returns_metadata(api_client) -> None:
    response = api_client.post("/api/v1/data-sources/upload", files=_build_csv_upload())
    assert response.status_code == 201
    uploaded_data_source = response.json()
    assert uploaded_data_source["source_type"] == "file"
    assert uploaded_data_source["original_filename"] == "sales_report.csv"
    assert uploaded_data_source["file_format"] == "csv"
    assert uploaded_data_source["file_size_bytes"] > 0
    assert uploaded_data_source["id"]
    assert uploaded_data_source["created_at"]


def test_upload_excel_extension_is_accepted(api_client) -> None:
    response = api_client.post(
        "/api/v1/data-sources/upload",
        files={"uploaded_file": ("report.xlsx", io.BytesIO(b"fake-bytes"), "application/octet-stream")},
    )
    assert response.status_code == 201
    assert response.json()["file_format"] == "excel"


def test_upload_unsupported_file_type_is_rejected(api_client) -> None:
    response = api_client.post(
        "/api/v1/data-sources/upload",
        files={"uploaded_file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_exceeding_size_limit_is_rejected(api_client) -> None:
    oversized_content = io.BytesIO(b"x" * (2 * 1024 * 1024))  # limit is 1 MB in tests
    response = api_client.post(
        "/api/v1/data-sources/upload",
        files={"uploaded_file": ("big.csv", oversized_content, "text/csv")},
    )
    assert response.status_code == 413


def test_uploaded_dataset_appears_in_listing_and_can_be_deleted(api_client) -> None:
    upload_response = api_client.post("/api/v1/data-sources/upload", files=_build_csv_upload())
    uploaded_data_source_id = upload_response.json()["id"]

    listing_response = api_client.get("/api/v1/data-sources", params={"source_type": "file"})
    assert listing_response.status_code == 200
    listed_ids = [data_source["id"] for data_source in listing_response.json()]
    assert uploaded_data_source_id in listed_ids

    delete_response = api_client.delete(f"/api/v1/data-sources/{uploaded_data_source_id}")
    assert delete_response.status_code == 204

    get_response = api_client.get(f"/api/v1/data-sources/{uploaded_data_source_id}")
    assert get_response.status_code == 404