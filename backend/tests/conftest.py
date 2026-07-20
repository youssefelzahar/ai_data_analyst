"""Test configuration.

Environment variables are set BEFORE the application is imported so that
the engine and settings bind to an isolated temporary database and upload
directory instead of the developer's local ones.
"""

import os
import tempfile

import pytest

_test_artifacts_directory = tempfile.mkdtemp(prefix="ai_data_analyst_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_artifacts_directory}/test.db"
os.environ["UPLOAD_DIRECTORY"] = f"{_test_artifacts_directory}/uploads"
os.environ["MAX_UPLOAD_SIZE_MB"] = "1"
os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", "admin")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "admin123")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

_ADMIN_USERNAME = os.environ["BOOTSTRAP_ADMIN_USERNAME"]
_ADMIN_PASSWORD = os.environ["BOOTSTRAP_ADMIN_PASSWORD"]


def _login(test_client: TestClient, username: str, password: str) -> str:
    response = test_client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture()
def anonymous_client():
    """An unauthenticated client, for testing auth failures and the login flow."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def api_client():
    """Admin-authenticated client.

    Existing feature tests exercise admin-level operations (uploads, cleaning,
    SQL), so the default client is authenticated as the bootstrap admin.
    """
    with TestClient(app) as test_client:
        token = _login(test_client, _ADMIN_USERNAME, _ADMIN_PASSWORD)
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client


# Alias kept for readability in new tests that specifically need an admin.
@pytest.fixture()
def admin_client(api_client):
    return api_client


@pytest.fixture()
def user_client(api_client):
    """A regular (non-admin) user client in the same company as the admin."""
    create = api_client.post(
        "/api/v1/users",
        json={"username": "regular_user", "password": "userpass1", "role": "user"},
    )
    # The DB is shared across the test session, so the user may already exist.
    assert create.status_code in (201, 400), create.text
    with TestClient(app) as test_client:
        token = _login(test_client, "regular_user", "userpass1")
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client
