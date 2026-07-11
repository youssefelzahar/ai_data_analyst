from string import Template


DEFAULT_PROMPTS: dict[str, str] = {
    "system.default": (
        "You are an AI data analyst assistant. "
        "Be concise, practical, and safe."
    ),
    "user.dataset_summary": (
        "Summarize this dataset for a business user:\n\n"
        "${dataset_context}"
    ),
    "system.agent": (
        "You are the response layer for an AI data analyst agent. "
        "Use the selected tool result as the source of truth. "
        "Do not invent analysis results or claim unavailable tool capabilities."
    ),
    "agent.response": (
        "User request:\n${user_request}\n\n"
        "Detected intent: ${intent}\n"
        "Selected tool: ${tool_name}\n"
        "Selected data source: ${selected_data_source}\n\n"
        "Tool result:\n${tool_result}\n\n"
        "Recent conversation:\n${conversation_context}\n\n"
        "Write the assistant response."
    ),
}


class UnknownPromptError(KeyError):
    """Raised when a prompt key is missing in the prompt registry."""


class PromptRenderError(ValueError):
    """Raised when a prompt template cannot be rendered with given variables."""


class PromptManager:
    """Stores and renders named prompt templates."""

    def __init__(self, templates: dict[str, str] | None = None) -> None:
        self._templates: dict[str, str] = dict(DEFAULT_PROMPTS)
        if templates:
            self._templates.update(templates)

    def get(self, key: str) -> str:
        template = self._templates.get(key)
        if template is None:
            raise UnknownPromptError(f"Unknown prompt key: '{key}'")
        return template

    def render(self, key: str, **variables: str) -> str:
        template = self.get(key)
        try:
            return Template(template).substitute(**variables)
        except KeyError as missing_variable_error:
            missing_variable = missing_variable_error.args[0]
            raise PromptRenderError(
                f"Prompt '{key}' missing template variable '{missing_variable}'"
            ) from missing_variable_error

    def add_or_replace(self, key: str, template: str) -> None:
        self._templates[key] = template

