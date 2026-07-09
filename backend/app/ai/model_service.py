from collections.abc import Iterator

from app.ai.llm.base import LLMClient, LLMRequest, LLMResponse, LLMStreamChunk
from app.ai.prompts import PromptManager


class ModelService:
    """Prompt-aware wrapper around an LLM client.

    Business logic should depend on this abstraction instead of a concrete model client.
    """

    def __init__(self, llm_client: LLMClient, prompt_manager: PromptManager) -> None:
        self._llm_client = llm_client
        self._prompt_manager = prompt_manager

    def generate(
        self,
        prompt_key: str,
        *,
        system_prompt_key: str = "system.default",
        model: str | None = None,
        temperature: float | None = None,
        **prompt_variables: str,
    ) -> LLMResponse:
        user_prompt = self._prompt_manager.render(prompt_key, **prompt_variables)
        system_prompt = self._prompt_manager.get(system_prompt_key)
        return self._llm_client.generate(
            LLMRequest(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
            )
        )

    def stream_generate(
        self,
        prompt_key: str,
        *,
        system_prompt_key: str = "system.default",
        model: str | None = None,
        temperature: float | None = None,
        **prompt_variables: str,
    ) -> Iterator[LLMStreamChunk]:
        user_prompt = self._prompt_manager.render(prompt_key, **prompt_variables)
        system_prompt = self._prompt_manager.get(system_prompt_key)
        return self._llm_client.stream_generate(
            LLMRequest(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
            )
        )

