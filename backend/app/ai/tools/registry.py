from collections.abc import Sequence
from dataclasses import dataclass, field
import re
from typing import Any, Protocol

from app.ai.memory import ConversationMessage


@dataclass(frozen=True)
class ToolContext:
    session_id: str
    user_request: str
    intent: str
    conversation_history: Sequence[ConversationMessage]
    session_context: dict[str, Any] = field(default_factory=dict)
    selected_data_source_id: str | None = None
    selected_version_id: str | None = None


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AnalystTool(Protocol):
    name: str
    description: str
    intents: Sequence[str]
    keywords: Sequence[str]

    def execute(self, context: ToolContext) -> ToolResult:
        """Run the tool for the detected intent."""


class ToolNotFoundError(KeyError):
    """Raised when an agent tries to execute an unknown tool."""


class ToolRegistry:
    """Registers analyst tools without coupling them to the agent."""

    def __init__(self) -> None:
        self._tools: dict[str, AnalystTool] = {}

    def register(self, tool: AnalystTool) -> None:
        self._tools[tool.name] = tool

    def get(self, tool_name: str) -> AnalystTool:
        tool = self._tools.get(tool_name)
        if tool is None:
            raise ToolNotFoundError(f"Unknown tool: '{tool_name}'")
        return tool

    def list_tools(self) -> list[AnalystTool]:
        return list(self._tools.values())

    def find_by_intent(self, intent: str) -> AnalystTool | None:
        return next(
            (tool for tool in self._tools.values() if intent in tool.intents),
            None,
        )

    def find_best_match(
        self,
        user_request: str,
    ) -> tuple[AnalystTool, list[str]] | None:
        normalized_request = user_request.lower()
        best_match: tuple[AnalystTool, list[str]] | None = None

        for tool in self._tools.values():
            if not tool.keywords:
                continue
            matched_keywords = [
                keyword
                for keyword in tool.keywords
                if _keyword_in_request(keyword, normalized_request)
            ]
            if not matched_keywords:
                continue
            if best_match is None or len(matched_keywords) > len(best_match[1]):
                best_match = (tool, matched_keywords)

        return best_match


class NoAvailableTool:
    name = "no_available_tool"
    description = "Responds when no specialized tool matched the request."
    intents = ("general_chat", "unknown")
    keywords: tuple[str, ...] = ()

    def execute(self, context: ToolContext) -> ToolResult:
        del context
        return ToolResult(
            tool_name=self.name,
            content=(
                "The request did not map to a specific analysis tool. "
                "Briefly and helpfully respond to the user. Do NOT say that analysis "
                "capabilities are unavailable or coming later - they exist now. "
                "Explain what you can do: summarize and profile a dataset; preview rows; "
                "compute aggregations (sum, average, min, max, count, median); group by "
                "columns; find correlations; filter and sort rows; count value frequencies; "
                "run SQL queries; and build dashboards with KPI cards, tables, and charts. "
                "Ask the user to select a data source (if none is selected) or to rephrase "
                "which of these they would like."
            ),
            metadata={"status": "general_chat"},
        )


def _keyword_in_request(keyword: str, normalized_request: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(keyword.lower()).replace(r"\ ", r"\s+") + r"(?!\w)"
    return re.search(pattern, normalized_request) is not None
