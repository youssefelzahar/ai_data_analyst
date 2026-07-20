from collections.abc import Iterator
from dataclasses import dataclass

from app.ai.intent import IntentDetectionResult, IntentDetector
from app.ai.llm.base import LLMStreamChunk
from app.ai.llm.ollama_client import OllamaClientError
from app.ai.memory import ConversationMemory, ConversationMessage
from app.ai.model_service import ModelService
from app.ai.tools import ToolContext, ToolExecutor, ToolResult
from app.schemas.visualization_schema import VisualizationBundle
from app.services.conversation_service import ConversationService


MAX_TOOL_RESULT_PROMPT_CHARS = 12000
MAX_CONVERSATION_PROMPT_CHARS = 6000


class AgentResponseError(Exception):
    """Raised when the agent cannot produce a response from the LLM."""


@dataclass(frozen=True)
class AgentTurn:
    session_id: str
    user_request: str
    intent: IntentDetectionResult
    tool_result: ToolResult
    selected_data_source_id: str | None
    selected_version_id: str | None
    visualizations: VisualizationBundle


@dataclass(frozen=True)
class AnalystAgentResponse:
    session_id: str
    content: str
    intent: str
    selected_tool: str
    selected_data_source_id: str | None
    selected_version_id: str | None
    visualizations: VisualizationBundle


class AnalystAgent:
    """Coordinates request handling across intent detection, tools, memory, and LLM output."""

    def __init__(
        self,
        intent_detector: IntentDetector,
        tool_executor: ToolExecutor,
        conversation_memory: ConversationMemory,
        model_service: ModelService,
        conversation_service: ConversationService,
    ) -> None:
        self._intent_detector = intent_detector
        self._tool_executor = tool_executor
        self._conversation_memory = conversation_memory
        self._model_service = model_service
        self._conversation_service = conversation_service

    def process_request(
        self,
        user_request: str,
        session_id: str | None = None,
        selected_data_source_id: str | None = None,
        selected_version_id: str | None = None,
        company_id: str | None = None,
        user_id: str | None = None,
    ) -> AnalystAgentResponse:
        turn = self._prepare_turn(
            user_request,
            session_id,
            selected_data_source_id,
            selected_version_id,
            company_id,
            user_id,
        )
        used_llm_fallback = False
        try:
            llm_response = self._model_service.generate(
                "agent.response",
                system_prompt_key="system.agent",
                **self._build_prompt_variables(turn),
            )
            assistant_content = llm_response.content
        except OllamaClientError as error:
            if not self._can_return_tool_fallback(turn):
                raise AgentResponseError(str(error)) from error
            assistant_content = self._build_tool_fallback_response(turn)
            used_llm_fallback = True
        if self._should_replace_misleading_visualization_response(turn, assistant_content):
            assistant_content = self._build_tool_fallback_response(turn)
            used_llm_fallback = True
        assistant_metadata = {
            "intent": turn.intent.intent,
            "tool": turn.tool_result.tool_name,
            "llm_fallback": used_llm_fallback,
        }
        assistant_message_id = self._conversation_service.save_assistant_message(
            turn.session_id,
            assistant_content,
            assistant_metadata,
            turn.visualizations,
        )
        self._conversation_memory.add_message(
            turn.session_id,
            "assistant",
            assistant_content,
            assistant_metadata,
            message_id=assistant_message_id,
        )
        return AnalystAgentResponse(
            session_id=turn.session_id,
            content=assistant_content,
            intent=turn.intent.intent,
            selected_tool=turn.tool_result.tool_name,
            selected_data_source_id=turn.selected_data_source_id,
            selected_version_id=turn.selected_version_id,
            visualizations=turn.visualizations,
        )

    def stream_request(
        self,
        user_request: str,
        session_id: str | None = None,
        selected_data_source_id: str | None = None,
        selected_version_id: str | None = None,
        company_id: str | None = None,
        user_id: str | None = None,
    ) -> Iterator[LLMStreamChunk]:
        turn = self._prepare_turn(
            user_request,
            session_id,
            selected_data_source_id,
            selected_version_id,
            company_id,
            user_id,
        )
        response_parts: list[str] = []
        try:
            for chunk in self._model_service.stream_generate(
                "agent.response",
                system_prompt_key="system.agent",
                **self._build_prompt_variables(turn),
            ):
                response_parts.append(chunk.content)
                yield chunk
        except OllamaClientError as error:
            raise AgentResponseError(str(error)) from error
        assistant_content = "".join(response_parts)
        assistant_metadata = {
            "intent": turn.intent.intent,
            "tool": turn.tool_result.tool_name,
        }
        assistant_message_id = self._conversation_service.save_assistant_message(
            turn.session_id,
            assistant_content,
            assistant_metadata,
            turn.visualizations,
        )
        self._conversation_memory.add_message(
            turn.session_id,
            "assistant",
            assistant_content,
            assistant_metadata,
            message_id=assistant_message_id,
        )

    def _prepare_turn(
        self,
        user_request: str,
        session_id: str | None,
        selected_data_source_id: str | None,
        selected_version_id: str | None = None,
        company_id: str | None = None,
        user_id: str | None = None,
    ) -> AgentTurn:
        if session_id:
            self._conversation_service.hydrate_session(
                session_id,
                selected_data_source_id,
                selected_version_id,
                company_id,
                user_id,
            )
        session = self._conversation_memory.get_or_create_session(session_id)
        if (
            selected_data_source_id != session.selected_data_source_id
            or selected_version_id != session.selected_version_id
        ):
            self._conversation_memory.set_selected_data_source(
                session.session_id,
                selected_data_source_id,
            )
            self._conversation_memory.set_selected_version(
                session.session_id,
                selected_version_id,
            )
            session.selected_data_source_id = selected_data_source_id
            session.selected_version_id = selected_version_id
            self._conversation_service.sync_selected_data_source(
                session.session_id,
                selected_data_source_id,
                selected_version_id,
                company_id,
                user_id,
            )

        user_message_id = self._conversation_service.save_user_message(
            session.session_id,
            user_request,
            company_id,
            user_id,
        )
        self._conversation_memory.add_message(
            session.session_id,
            "user",
            user_request,
            message_id=user_message_id,
        )
        intent = self._intent_detector.detect(user_request)
        tool_context = ToolContext(
            session_id=session.session_id,
            user_request=user_request,
            intent=intent.intent,
            conversation_history=self._conversation_memory.get_recent_messages(
                session.session_id
            ),
            session_context=dict(session.context),
            selected_data_source_id=session.selected_data_source_id,
            selected_version_id=session.selected_version_id,
        )
        tool_result = self._tool_executor.execute(intent.tool_name, tool_context)
        context_updates = tool_result.metadata.get("session_context_updates", {})
        if isinstance(context_updates, dict) and context_updates:
            self._conversation_memory.update_context(session.session_id, **context_updates)
            self._conversation_service.sync_context(
                session.session_id,
                dict(session.context),
            )
        visualizations = VisualizationBundle.model_validate(
            tool_result.metadata.get("visualizations", {})
        )
        # Capture the analysis artifacts alongside the assistant text so future
        # Report/Export features can reuse them without re-running the AI.
        generated_sql = tool_result.metadata.get("generated_sql")
        if generated_sql and not visualizations.generated_sql:
            visualizations.generated_sql = generated_sql
        if session.selected_data_source_id and visualizations.dataset_reference is None:
            visualizations.dataset_reference = {
                "data_source_id": session.selected_data_source_id,
                "version_id": session.selected_version_id,
            }
        return AgentTurn(
            session_id=session.session_id,
            user_request=user_request,
            intent=intent,
            tool_result=tool_result,
            selected_data_source_id=session.selected_data_source_id,
            selected_version_id=session.selected_version_id,
            visualizations=visualizations,
        )

    def _build_prompt_variables(self, turn: AgentTurn) -> dict[str, str]:
        return {
            "user_request": turn.user_request,
            "intent": turn.intent.intent,
            "tool_name": turn.tool_result.tool_name,
            "selected_data_source": turn.selected_data_source_id or "none",
            "tool_result": self._truncate_for_prompt(
                turn.tool_result.content,
                MAX_TOOL_RESULT_PROMPT_CHARS,
            ),
            "conversation_context": self._format_history(
                self._conversation_memory.get_recent_messages(turn.session_id),
                MAX_CONVERSATION_PROMPT_CHARS,
            ),
        }

    @staticmethod
    def _format_history(
        messages: list[ConversationMessage],
        max_chars: int = MAX_CONVERSATION_PROMPT_CHARS,
    ) -> str:
        if not messages:
            return "No prior conversation."
        formatted_history = "\n".join(
            f"{message.role}: {message.content}" for message in messages
        )
        return AnalystAgent._truncate_for_prompt(formatted_history, max_chars)

    @staticmethod
    def _truncate_for_prompt(value: str, max_chars: int) -> str:
        if len(value) <= max_chars:
            return value
        omitted_chars = len(value) - max_chars
        return (
            f"{value[:max_chars]}\n\n"
            f"[Truncated {omitted_chars} characters to keep the model request within limits.]"
        )

    @staticmethod
    def _can_return_tool_fallback(turn: AgentTurn) -> bool:
        return (
            turn.tool_result.metadata.get("status") == "ok"
            and (
                bool(turn.visualizations.kpi_cards)
                or bool(turn.visualizations.tables)
                or bool(turn.visualizations.charts)
            )
        )

    @staticmethod
    def _build_tool_fallback_response(turn: AgentTurn) -> str:
        artifact_counts: list[str] = []
        if turn.visualizations.kpi_cards:
            artifact_counts.append(f"{len(turn.visualizations.kpi_cards)} KPI cards")
        if turn.visualizations.charts:
            artifact_counts.append(f"{len(turn.visualizations.charts)} charts")
        if turn.visualizations.tables:
            artifact_counts.append(f"{len(turn.visualizations.tables)} tables")
        artifact_summary = ", ".join(artifact_counts)
        details: list[str] = []
        if turn.visualizations.kpi_cards:
            kpis = ", ".join(
                f"{card.title}: {card.value}" for card in turn.visualizations.kpi_cards[:4]
            )
            details.append(f"KPI cards include {kpis}")
        if turn.visualizations.charts:
            charts = ", ".join(chart.title for chart in turn.visualizations.charts[:3])
            details.append(f"Charts include {charts}")
        detail_text = f" {'; '.join(details)}." if details else ""
        return f"I created the dashboard with {artifact_summary}.{detail_text}"

    @staticmethod
    def _should_replace_misleading_visualization_response(
        turn: AgentTurn,
        assistant_content: str,
    ) -> bool:
        if not AnalystAgent._can_return_tool_fallback(turn):
            return False
        normalized_content = assistant_content.lower()
        misleading_markers = (
            "visualization capabilities aren't available",
            "visualization capabilities are not available",
            "don't have visualization capabilities",
            "do not have visualization capabilities",
            "tool capabilities will be added later",
            "current tool result doesn't include",
            "current tool result does not include",
            "need to run a separate aggregation",
        )
        return any(marker in normalized_content for marker in misleading_markers)
