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

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def api_client():
    # Context manager form triggers the lifespan (table creation).
    with TestClient(app) as test_client:
        yield test_client