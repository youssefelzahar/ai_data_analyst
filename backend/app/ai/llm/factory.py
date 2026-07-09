from functools import lru_cache

from app.ai.llm.base import LLMClient, ModelConfig
from app.ai.llm.ollama_client import OllamaClient
from app.core.config import Settings, get_settings


def build_model_config(settings: Settings) -> ModelConfig:
    return ModelConfig(
        provider=settings.ai_provider,
        default_model=settings.ai_default_model,
        temperature=settings.ai_temperature,
        request_timeout_seconds=settings.ai_request_timeout_seconds,
    )


def create_llm_client(settings: Settings) -> LLMClient:
    model_config = build_model_config(settings)
    if model_config.provider == "ollama":
        return OllamaClient(
            base_url=settings.ollama_base_url,
            model_config=model_config,
        )
    raise ValueError(f"Unsupported AI provider '{model_config.provider}'")


@lru_cache
def get_llm_client() -> LLMClient:
    return create_llm_client(get_settings())

