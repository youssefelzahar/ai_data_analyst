import json

from app.ai.agent import AnalystAgent
from app.ai.intent import IntentDetector
from app.ai.llm.base import LLMRequest, LLMResponse, LLMStreamChunk
from app.ai.llm.factory import build_model_config, create_llm_client
from app.ai.llm.ollama_client import OllamaClient
from app.ai.memory import ConversationMemory
from app.ai.model_service import ModelService
from app.ai.prompts import PromptManager
from app.ai.tools import NoAvailableTool, ToolExecutor, ToolRegistry
from app.core.config import Settings
from app.schemas.visualization_schema import VisualizationBundle


class _FakeHTTPResponse:
    def __init__(self, body: bytes, stream_lines: list[bytes] | None = None) -> None:
        self._body = body
        self._stream_lines = stream_lines or []

    def read(self) -> bytes:
        return self._body

    def __iter__(self):
        return iter(self._stream_lines)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_build_model_config_reads_ai_settings() -> None:
    settings = Settings(
        ai_provider="ollama",
        ai_default_model="phi4-mini",
        ai_temperature=0.25,
        ai_request_timeout_seconds=42,
    )
    model_config = build_model_config(settings)

    assert model_config.provider == "ollama"
    assert model_config.default_model == "phi4-mini"
    assert model_config.temperature == 0.25
    assert model_config.request_timeout_seconds == 42


def test_create_llm_client_returns_ollama_client() -> None:
    settings = Settings(ai_provider="ollama")
    client = create_llm_client(settings)
    assert isinstance(client, OllamaClient)


def test_ollama_generate_uses_default_model_from_configuration(monkeypatch) -> None:
    captured_request_payload: dict[str, object] = {}

    def _fake_urlopen(request_object, timeout):
        del timeout
        captured_request_payload.update(json.loads(request_object.data.decode("utf-8")))
        return _FakeHTTPResponse(body=json.dumps({"model": "phi4-mini", "response": "ok"}).encode("utf-8"))

    monkeypatch.setattr("app.ai.llm.ollama_client.request.urlopen", _fake_urlopen)

    client = OllamaClient(
        base_url="http://localhost:11434",
        model_config=build_model_config(Settings(ai_default_model="phi4-mini")),
    )

    response = client.generate(LLMRequest(prompt="hello"))

    assert captured_request_payload["model"] == "phi4-mini"
    assert captured_request_payload["stream"] is False
    assert response.content == "ok"


def test_ollama_stream_generate_yields_chunks(monkeypatch) -> None:
    stream_lines = [
        json.dumps({"model": "phi4-mini", "response": "hello ", "done": False}).encode("utf-8"),
        b"\n",
        json.dumps({"model": "phi4-mini", "response": "world", "done": True}).encode("utf-8"),
    ]

    def _fake_urlopen(request_object, timeout):
        del request_object, timeout
        return _FakeHTTPResponse(body=b"", stream_lines=stream_lines)

    monkeypatch.setattr("app.ai.llm.ollama_client.request.urlopen", _fake_urlopen)

    client = OllamaClient(
        base_url="http://localhost:11434",
        model_config=build_model_config(Settings(ai_default_model="phi4-mini")),
    )

    chunks = list(client.stream_generate(LLMRequest(prompt="hi")))

    assert len(chunks) == 2
    assert chunks[0].content == "hello "
    assert chunks[0].done is False
    assert chunks[1].content == "world"
    assert chunks[1].done is True


def test_prompt_manager_renders_template() -> None:
    prompt_manager = PromptManager({"user.greet": "Hello ${name}"})
    rendered_prompt = prompt_manager.render("user.greet", name="team")
    assert rendered_prompt == "Hello team"


class _FakeLLMClient:
    def __init__(self) -> None:
        self.last_request: LLMRequest | None = None

    def generate(self, request_payload: LLMRequest) -> LLMResponse:
        self.last_request = request_payload
        return LLMResponse(model="phi4-mini", content="done", raw_response={})

    def stream_generate(self, request_payload: LLMRequest):
        self.last_request = request_payload
        yield LLMStreamChunk(model="phi4-mini", content="piece", done=True, raw_response={})


class _FakeConversationService:
    def __init__(self) -> None:
        self.saved_user_messages: list[tuple[str, str]] = []
        self.saved_assistant_messages: list[tuple[str, str, dict, VisualizationBundle]] = []

    def hydrate_session(self, session_id: str, selected_data_source_id: str | None = None) -> None:
        del session_id, selected_data_source_id

    def sync_selected_data_source(self, session_id: str, selected_data_source_id: str | None) -> None:
        del session_id, selected_data_source_id

    def sync_context(self, session_id: str, context: dict) -> None:
        del session_id, context

    def save_user_message(self, session_id: str, content: str) -> str:
        self.saved_user_messages.append((session_id, content))
        return "user-message-id"

    def save_assistant_message(
        self,
        session_id: str,
        content: str,
        metadata: dict,
        visualizations: VisualizationBundle,
    ) -> str:
        self.saved_assistant_messages.append((session_id, content, metadata, visualizations))
        return "assistant-message-id"


def test_model_service_uses_prompt_manager_and_llm_client() -> None:
    fake_llm_client = _FakeLLMClient()
    prompt_manager = PromptManager({"user.greet": "Hello ${name}"})
    model_service = ModelService(fake_llm_client, prompt_manager)

    response = model_service.generate("user.greet", name="analyst")

    assert response.content == "done"
    assert fake_llm_client.last_request is not None
    assert fake_llm_client.last_request.prompt == "Hello analyst"
    assert fake_llm_client.last_request.system_prompt == prompt_manager.get("system.default")


def test_tool_registry_registers_and_finds_tools_by_intent() -> None:
    registry = ToolRegistry()
    tool = NoAvailableTool()

    registry.register(tool)

    assert registry.get("no_available_tool") is tool
    assert registry.find_by_intent("general_chat") is tool


def test_intent_detector_falls_back_to_registered_general_tool() -> None:
    registry = ToolRegistry()
    registry.register(NoAvailableTool())
    detector = IntentDetector(registry)

    detected_intent = detector.detect("hello there")

    assert detected_intent.intent == "general_chat"
    assert detected_intent.tool_name == "no_available_tool"


def test_conversation_memory_tracks_session_messages_and_context() -> None:
    memory = ConversationMemory()
    session = memory.get_or_create_session("session-1")

    memory.set_selected_data_source("session-1", "data-source-1")
    memory.update_context("session-1", active_table="sales")
    memory.add_message("session-1", "user", "hello")

    assert session.selected_data_source_id == "data-source-1"
    assert session.context["active_table"] == "sales"
    assert memory.get_recent_messages("session-1")[0].content == "hello"


def test_analyst_agent_runs_intent_tool_llm_workflow() -> None:
    fake_llm_client = _FakeLLMClient()
    prompt_manager = PromptManager()
    model_service = ModelService(fake_llm_client, prompt_manager)
    registry = ToolRegistry()
    registry.register(NoAvailableTool())
    memory = ConversationMemory()
    conversation_service = _FakeConversationService()
    agent = AnalystAgent(
        intent_detector=IntentDetector(registry),
        tool_executor=ToolExecutor(registry),
        conversation_memory=memory,
        model_service=model_service,
        conversation_service=conversation_service,
    )

    response = agent.process_request(
        "Can you summarize this?",
        session_id="session-1",
        selected_data_source_id="data-source-1",
    )

    assert response.session_id == "session-1"
    assert response.content == "done"
    assert response.selected_tool == "no_available_tool"
    assert response.selected_data_source_id == "data-source-1"
    assert response.visualizations.charts == []
    assert fake_llm_client.last_request is not None
    assert "Selected tool: no_available_tool" in fake_llm_client.last_request.prompt
    assert len(memory.get_recent_messages("session-1")) == 2
    assert len(conversation_service.saved_user_messages) == 1
    assert len(conversation_service.saved_assistant_messages) == 1
