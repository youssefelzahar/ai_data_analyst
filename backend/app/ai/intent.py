import json
import re
from dataclasses import dataclass

from app.ai.llm.ollama_client import OllamaClientError
from app.ai.model_service import ModelService
from app.ai.tools import ToolNotFoundError, ToolRegistry

_FALLBACK_INTENTS = ("general_chat", "unknown")
_THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class IntentDetectionResult:
    intent: str
    tool_name: str
    confidence: float
    rationale: str


class IntentDetector:
    """Maps user requests to registered tools."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        model_service: ModelService | None = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._model_service = model_service

    def detect(self, user_request: str) -> IntentDetectionResult:
        best_match = self._tool_registry.find_best_match(user_request)
        if best_match is not None:
            tool, matched_keywords = best_match
            return IntentDetectionResult(
                intent=tool.intents[0],
                tool_name=tool.name,
                confidence=min(0.95, 0.45 + 0.1 * len(matched_keywords)),
                rationale=(
                    f"Matched tool keywords for '{tool.name}': "
                    f"{', '.join(matched_keywords)}."
                ),
            )

        if self._model_service is not None:
            llm_result = self._classify_with_llm(user_request)
            if llm_result is not None:
                return llm_result

        return self._fallback_result()

    def _fallback_result(self) -> IntentDetectionResult:
        fallback_tool = (
            self._tool_registry.find_by_intent("general_chat")
            or self._tool_registry.find_by_intent("unknown")
        )
        if fallback_tool is None:
            available_tools = self._tool_registry.list_tools()
            if not available_tools:
                raise RuntimeError("No tools registered for the analyst agent.")
            fallback_tool = available_tools[0]

        return IntentDetectionResult(
            intent="general_chat",
            tool_name=fallback_tool.name,
            confidence=0.4,
            rationale="No specialized registered tool matched the request.",
        )

    def _classify_with_llm(self, user_request: str) -> IntentDetectionResult | None:
        """Ask the LLM to route the request when keyword matching finds nothing.

        Must never raise: any failure degrades to the safe keyword fallback.
        """
        assert self._model_service is not None
        catalog = self._build_tool_catalog()
        if not catalog:
            return None
        try:
            response = self._model_service.generate(
                "intent.classify",
                system_prompt_key="system.intent_classifier",
                temperature=0.0,
                user_request=user_request,
                tool_catalog=catalog,
            )
        except OllamaClientError:
            return None

        classification = _parse_classification(response.content)
        if classification is None:
            return None

        tool_name = classification.get("tool_name")
        if not isinstance(tool_name, str) or tool_name.strip().lower() == "none":
            return None
        try:
            tool = self._tool_registry.get(tool_name)
        except ToolNotFoundError:
            return None
        if not tool.intents:
            return None

        confidence = classification.get("confidence")
        if not isinstance(confidence, (int, float)):
            confidence = 0.6
        rationale = classification.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            rationale = f"LLM classifier selected '{tool.name}'."

        return IntentDetectionResult(
            intent=tool.intents[0],
            tool_name=tool.name,
            confidence=max(0.0, min(1.0, float(confidence))),
            rationale=rationale,
        )

    def _build_tool_catalog(self) -> str:
        lines: list[str] = []
        for tool in self._tool_registry.list_tools():
            if any(intent in _FALLBACK_INTENTS for intent in tool.intents):
                continue
            intents = ", ".join(tool.intents)
            lines.append(f"- {tool.name}: {tool.description} (intents: {intents})")
        return "\n".join(lines)


def _parse_classification(content: str) -> dict | None:
    """Extract a JSON object from the model output, tolerating think blocks/prose."""
    stripped = _THINK_BLOCK_PATTERN.sub("", content).strip()
    match = _JSON_OBJECT_PATTERN.search(stripped)
    if match is None:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed
