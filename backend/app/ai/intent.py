from dataclasses import dataclass

from app.ai.tools import ToolRegistry


@dataclass(frozen=True)
class IntentDetectionResult:
    intent: str
    tool_name: str
    confidence: float
    rationale: str


class IntentDetector:
    """Maps user requests to registered tools."""

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry

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
