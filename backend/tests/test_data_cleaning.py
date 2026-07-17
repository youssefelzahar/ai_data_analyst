import io

from app.ai.llm.base import LLMResponse

_CLEANING_CSV = (
    b"value,category,note\n"
    b"10,A,This is a fairly long free text note about something\n"
    b"11,A,Another fairly long free text note about something else\n"
    b",A,Yet another long piece of free text describing an event\n"
    b"10,B,Some more descriptive text goes here for testing\n"
    b"1000,B,Extra long free text sample for the outlier row here\n"
    b"10,A,This is a fairly long free text note about something\n"
)


class _CapturingModelService:
    def __init__(self) -> None:
        self.last_prompt_variables: dict[str, str] | None = None

    def generate(
        self,
        prompt_key: str,
        *,
        system_prompt_key: str = "system.default",
        **prompt_variables: str,
    ) -> LLMResponse:
        del prompt_key, system_prompt_key
        self.last_prompt_variables = prompt_variables
        return LLMResponse(model="test-model", content="answer", raw_response={})


def _upload_cleaning_csv(api_client) -> str:
    response = api_client.post(
        "/api/v1/data-sources/upload",
        files={"uploaded_file": ("cleaning_sample.csv", io.BytesIO(_CLEANING_CSV), "text/csv")},
    )
    return response.json()["id"]


def test_recommendations_shape(api_client) -> None:
    data_source_id = _upload_cleaning_csv(api_client)

    response = api_client.get(f"/api/v1/data-sources/{data_source_id}/cleaning/recommendations")
    assert response.status_code == 200
    recommendations = response.json()

    for category in (
        "missing_values", "duplicates", "type_conversion", "outliers",
        "encoding", "scaling", "skew", "text",
    ):
        assert category in recommendations

    missing_columns = {item["column_name"] for item in recommendations["missing_values"]}
    assert "value" in missing_columns

    assert len(recommendations["duplicates"]) == 1

    text_columns = {item["column_name"] for item in recommendations["text"]}
    assert "note" in text_columns


def test_methods_catalog_lists_every_category(api_client) -> None:
    data_source_id = _upload_cleaning_csv(api_client)

    response = api_client.get(f"/api/v1/data-sources/{data_source_id}/cleaning/methods")
    assert response.status_code == 200
    methods = response.json()["methods"]
    categories = {method["category"] for method in methods}
    assert categories == {
        "missing_values", "duplicates", "type_conversion", "outliers",
        "encoding", "scaling", "skew", "text",
    }
    keys = {method["key"] for method in methods}
    assert "missing_values.median" in keys
    assert "outliers.iqr_capping" in keys
    assert "encoding.one_hot" in keys
    assert "scaling.standard" in keys
    assert "skew.yeojohnson" in keys
    assert "text.lemmatize" in keys


def test_preview_does_not_modify_original_profile(api_client) -> None:
    data_source_id = _upload_cleaning_csv(api_client)

    profile_before = api_client.get(f"/api/v1/data-sources/{data_source_id}/profile").json()

    preview_response = api_client.post(
        f"/api/v1/data-sources/{data_source_id}/cleaning/preview",
        json={"operations": [{"operation_key": "missing_values.median", "column_name": "value"}]},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["before_overview"]["total_missing_values"] == 1
    assert preview["after_overview"]["total_missing_values"] == 0
    assert len(preview["steps"]) == 1
    assert preview["steps"][0]["affected_row_count"] == 1

    profile_after = api_client.get(f"/api/v1/data-sources/{data_source_id}/profile").json()
    assert profile_after == profile_before


def test_apply_creates_version_and_undo_removes_it(api_client) -> None:
    data_source_id = _upload_cleaning_csv(api_client)

    apply_response = api_client.post(
        f"/api/v1/data-sources/{data_source_id}/cleaning/apply",
        json={
            "operations": [
                {"operation_key": "missing_values.median", "column_name": "value"},
                {"operation_key": "duplicates.remove"},
            ]
        },
    )
    assert apply_response.status_code == 201
    version = apply_response.json()
    assert version["version_number"] == 1
    assert version["row_count"] == 5  # one duplicate row removed
    assert len(version["operations_summary"]) == 2

    versions_response = api_client.get(f"/api/v1/data-sources/{data_source_id}/cleaning/versions")
    assert len(versions_response.json()) == 1

    # Applying again builds on top of the current (already-cleaned) version.
    second_apply = api_client.post(
        f"/api/v1/data-sources/{data_source_id}/cleaning/apply",
        json={"operations": [{"operation_key": "encoding.one_hot", "column_name": "category"}]},
    )
    assert second_apply.status_code == 201
    assert second_apply.json()["version_number"] == 2

    undo_response = api_client.delete(f"/api/v1/data-sources/{data_source_id}/cleaning/versions/latest")
    assert undo_response.status_code == 204

    versions_after_undo = api_client.get(f"/api/v1/data-sources/{data_source_id}/cleaning/versions").json()
    assert len(versions_after_undo) == 1
    assert versions_after_undo[0]["version_number"] == 1

    # Original data source file is still untouched throughout.
    original_profile = api_client.get(f"/api/v1/data-sources/{data_source_id}/profile").json()
    assert original_profile["overview"]["row_count"] == 6


def test_agent_answers_use_latest_cleaned_version(api_client, monkeypatch) -> None:
    data_source_id = _upload_cleaning_csv(api_client)
    model_service = _CapturingModelService()
    monkeypatch.setattr(
        "app.ai.dependencies.get_model_service",
        lambda: model_service,
    )

    apply_response = api_client.post(
        f"/api/v1/data-sources/{data_source_id}/cleaning/apply",
        json={"operations": [{"operation_key": "duplicates.remove"}]},
    )
    assert apply_response.status_code == 201
    assert apply_response.json()["row_count"] == 5

    chat_response = api_client.post(
        "/api/v1/agent/chat",
        json={
            "message": "count rows",
            "session_id": "cleaned-version-session",
            "selected_data_source_id": data_source_id,
        },
    )

    assert chat_response.status_code == 200
    assert model_service.last_prompt_variables is not None
    assert '"count_1": 5' in model_service.last_prompt_variables["tool_result"]


def test_undo_without_any_version_returns_400(api_client) -> None:
    data_source_id = _upload_cleaning_csv(api_client)

    response = api_client.delete(f"/api/v1/data-sources/{data_source_id}/cleaning/versions/latest")
    assert response.status_code == 400


def test_representative_strategy_per_category_executes(api_client) -> None:
    data_source_id = _upload_cleaning_csv(api_client)

    operations = [
        {"operation_key": "missing_values.median", "column_name": "value"},
        {"operation_key": "duplicates.remove"},
        {"operation_key": "outliers.iqr_capping", "column_name": "value"},
        {"operation_key": "encoding.frequency", "column_name": "category"},
        {"operation_key": "scaling.standard", "column_name": "value"},
        {"operation_key": "text.lowercase", "column_name": "note"},
    ]
    response = api_client.post(
        f"/api/v1/data-sources/{data_source_id}/cleaning/preview",
        json={"operations": operations},
    )
    assert response.status_code == 200
    steps = response.json()["steps"]
    assert len(steps) == len(operations)
    for step in steps:
        assert step["message"]


def test_skew_transform_reports_before_after_skewness(api_client) -> None:
    csv_content = b"amount\n" + b"\n".join(str(i * i).encode() for i in range(1, 21))
    upload_response = api_client.post(
        "/api/v1/data-sources/upload",
        files={"uploaded_file": ("skewed.csv", io.BytesIO(csv_content), "text/csv")},
    )
    data_source_id = upload_response.json()["id"]

    response = api_client.post(
        f"/api/v1/data-sources/{data_source_id}/cleaning/preview",
        json={"operations": [{"operation_key": "skew.log_transform", "column_name": "amount"}]},
    )
    assert response.status_code == 200
    message = response.json()["steps"][0]["message"]
    assert "skewness" in message.lower()


def test_unknown_data_source_returns_404(api_client) -> None:
    assert api_client.get("/api/v1/data-sources/does-not-exist/cleaning/recommendations").status_code == 404
    assert api_client.get("/api/v1/data-sources/does-not-exist/cleaning/methods").status_code == 404
    assert (
        api_client.post(
            "/api/v1/data-sources/does-not-exist/cleaning/preview", json={"operations": []}
        ).status_code
        == 404
    )
