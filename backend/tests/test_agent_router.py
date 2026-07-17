from collections.abc import Iterator

from fastapi.testclient import TestClient

from app.ai.agent import AnalystAgent, AgentResponseError, AnalystAgentResponse
from app.ai.dependencies import get_analyst_agent
from app.ai.llm.base import LLMStreamChunk
from app.ai.memory import ConversationMessage
from app.main import app


class _FailingAgent:
    def process_request(
        self,
        user_request: str,
        session_id: str | None = None,
        selected_data_source_id: str | None = None,
    ) -> AnalystAgentResponse:
        del user_request, session_id, selected_data_source_id
        raise AgentResponseError("Ollama request failed")

    def stream_request(
        self,
        user_request: str,
        session_id: str | None = None,
        selected_data_source_id: str | None = None,
    ) -> Iterator[LLMStreamChunk]:
        del user_request, session_id, selected_data_source_id
        raise AgentResponseError("Ollama streaming request failed")
        yield


def test_agent_chat_returns_bad_gateway_when_model_fails(api_client: TestClient) -> None:
    app.dependency_overrides[get_analyst_agent] = lambda: _FailingAgent()
    try:
        response = api_client.post(
            "/api/v1/agent/chat",
            json={"message": "Summarize this data", "session_id": "session-1"},
        )
    finally:
        app.dependency_overrides.pop(get_analyst_agent, None)

    assert response.status_code == 502
    assert response.json() == {
        "detail": (
            "The AI model service failed while generating a response. "
            "Check that Ollama is running and the selected model can handle this request."
        )
    }


def test_agent_chat_stream_returns_error_text_when_model_fails(
    api_client: TestClient,
) -> None:
    app.dependency_overrides[get_analyst_agent] = lambda: _FailingAgent()
    try:
        response = api_client.post(
            "/api/v1/agent/chat/stream",
            json={"message": "Summarize this data", "session_id": "session-1"},
        )
    finally:
        app.dependency_overrides.pop(get_analyst_agent, None)

    assert response.status_code == 200
    assert response.text == (
        "The AI model service failed while generating a response. "
        "Check that Ollama is running and the selected model can handle this request."
    )


def test_agent_prompt_variables_truncate_large_context() -> None:
    history = AnalystAgent._format_history(
        [ConversationMessage(role="user", content="x" * 20)],
        max_chars=10,
    )

    assert history.startswith("user: xxxx")
    assert "[Truncated" in history
