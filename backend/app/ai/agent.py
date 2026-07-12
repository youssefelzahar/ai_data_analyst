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


class AgentResponseError(Exception):
    """Raised when the agent cannot produce a response from the LLM."""


@dataclass(frozen=True)
class AgentTurn:
    session_id: str
    user_request: str
    intent: IntentDetectionResult
    tool_result: ToolResult
    selected_data_source_id: str | None
    visualizations: VisualizationBundle


@dataclass(frozen=True)
class AnalystAgentResponse:
    session_id: str
    content: str
    intent: str
    selected_tool: str
    selected_data_source_id: str | None
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
    ) -> AnalystAgentResponse:
        turn = self._prepare_turn(user_request, session_id, selected_data_source_id)
        try:
            llm_response = self._model_service.generate(
                "agent.response",
                system_prompt_key="system.agent",
                **self._build_prompt_variables(turn),
            )
        except OllamaClientError as error:
            raise AgentResponseError(str(error)) from error
        assistant_metadata = {
            "intent": turn.intent.intent,
            "tool": turn.tool_result.tool_name,
        }
        assistant_message_id = self._conversation_service.save_assistant_message(
            turn.session_id,
            llm_response.content,
            assistant_metadata,
            turn.visualizations,
        )
        self._conversation_memory.add_message(
            turn.session_id,
            "assistant",
            llm_response.content,
            assistant_metadata,
            message_id=assistant_message_id,
        )
        return AnalystAgentResponse(
            session_id=turn.session_id,
            content=llm_response.content,
            intent=turn.intent.intent,
            selected_tool=turn.tool_result.tool_name,
            selected_data_source_id=turn.selected_data_source_id,
            visualizations=turn.visualizations,
        )

    def stream_request(
        self,
        user_request: str,
        session_id: str | None = None,
        selected_data_source_id: str | None = None,
    ) -> Iterator[LLMStreamChunk]:
        turn = self._prepare_turn(user_request, session_id, selected_data_source_id)
        response_parts: list[str] = []
        for chunk in self._model_service.stream_generate(
            "agent.response",
            system_prompt_key="system.agent",
            **self._build_prompt_variables(turn),
        ):
            response_parts.append(chunk.content)
            yield chunk
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
    ) -> AgentTurn:
        if session_id:
            self._conversation_service.hydrate_session(
                session_id,
                selected_data_source_id,
            )
        session = self._conversation_memory.get_or_create_session(session_id)
        if selected_data_source_id != session.selected_data_source_id:
            self._conversation_memory.set_selected_data_source(
                session.session_id,
                selected_data_source_id,
            )
            session.selected_data_source_id = selected_data_source_id
            self._conversation_service.sync_selected_data_source(
                session.session_id,
                selected_data_source_id,
            )

        user_message_id = self._conversation_service.save_user_message(
            session.session_id,
            user_request,
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
        return AgentTurn(
            session_id=session.session_id,
            user_request=user_request,
            intent=intent,
            tool_result=tool_result,
            selected_data_source_id=session.selected_data_source_id,
            visualizations=visualizations,
        )

    def _build_prompt_variables(self, turn: AgentTurn) -> dict[str, str]:
        return {
            "user_request": turn.user_request,
            "intent": turn.intent.intent,
            "tool_name": turn.tool_result.tool_name,
            "selected_data_source": turn.selected_data_source_id or "none",
            "tool_result": turn.tool_result.content,
            "conversation_context": self._format_history(
                self._conversation_memory.get_recent_messages(turn.session_id)
            ),
        }

    @staticmethod
    def _format_history(messages: list[ConversationMessage]) -> str:
        if not messages:
            return "No prior conversation."
        return "\n".join(f"{message.role}: {message.content}" for message in messages)
