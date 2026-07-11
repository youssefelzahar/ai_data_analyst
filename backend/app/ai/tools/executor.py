from app.ai.tools.registry import ToolContext, ToolRegistry, ToolResult


class ToolExecutor:
    """Executes tools selected by the intent detector."""

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry

    def execute(self, tool_name: str, context: ToolContext) -> ToolResult:
        tool = self._tool_registry.get(tool_name)
        return tool.execute(context)
