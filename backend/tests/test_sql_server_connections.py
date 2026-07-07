def _build_sql_authentication_payload() -> dict:
    return {
        "connection_name": "warehouse-production",
        "server_host": "sql.example.internal",
        "database_name": "warehouse",
        "authentication_type": "sql_server",
        "username": "analyst",
        "password": "s3cret-value",
    }


def test_create_connection_never_exposes_password(api_client) -> None:
    response = api_client.post(
        "/api/v1/data-sources/sql-server", json=_build_sql_authentication_payload()
    )
    assert response.status_code == 201
    saved_connection = response.json()
    assert saved_connection["source_type"] == "sql_server"
    assert saved_connection["name"] == "warehouse-production"
    assert saved_connection["server_host"] == "sql.example.internal"
    assert saved_connection["username"] == "analyst"
    assert "password" not in saved_connection
    assert "encrypted_password" not in saved_connection


def test_windows_authentication_requires_no_credentials(api_client) -> None:
    response = api_client.post(
        "/api/v1/data-sources/sql-server",
        json={
            "connection_name": "local-dev",
            "server_host": "localhost\\SQLEXPRESS",
            "database_name": "AdventureWorks",
            "authentication_type": "windows",
        },
    )
    assert response.status_code == 201
    assert response.json()["authentication_type"] == "windows"


def test_sql_authentication_without_credentials_is_rejected(api_client) -> None:
    incomplete_payload = _build_sql_authentication_payload()
    del incomplete_payload["password"]
    response = api_client.post("/api/v1/data-sources/sql-server", json=incomplete_payload)
    assert response.status_code == 422


def test_saved_connections_appear_in_filtered_listing(api_client) -> None:
    api_client.post("/api/v1/data-sources/sql-server", json=_build_sql_authentication_payload())
    listing_response = api_client.get(
        "/api/v1/data-sources", params={"source_type": "sql_server"}
    )
    assert listing_response.status_code == 200
    assert all(
        data_source["source_type"] == "sql_server" for data_source in listing_response.json()
    )
    assert len(listing_response.json()) >= 1


def test_password_is_encrypted_at_rest() -> None:
    from app.core.encryption import decrypt_secret, encrypt_secret

    encrypted_value = encrypt_secret("s3cret-value")
    assert encrypted_value != "s3cret-value"
    assert decrypt_secret(encrypted_value) == "s3cret-value"


def test_connection_test_against_unreachable_server_reports_failure(api_client) -> None:
    unreachable_payload = _build_sql_authentication_payload()
    unreachable_payload["server_host"] = "host-that-does-not-exist.invalid"
    response = api_client.post(
        "/api/v1/data-sources/sql-server/test", json=unreachable_payload
    )
    assert response.status_code == 200
    connection_test_result = response.json()
    assert connection_test_result["success"] is False
    assert connection_test_result["message"]