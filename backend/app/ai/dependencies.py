from functools import lru_cache

from app.ai.llm.factory import get_llm_client
from app.ai.model_service import ModelService
from app.ai.prompts import PromptManager


@lru_cache
def get_prompt_manager() -> PromptManager:
    return PromptManager()


@lru_cache
def get_model_service() -> ModelService:
    return ModelService(
        llm_client=get_llm_client(),
        prompt_manager=get_prompt_manager(),
    )

