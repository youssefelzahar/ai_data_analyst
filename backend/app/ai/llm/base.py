from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    default_model: str
    temperature: float
    request_timeout_seconds: int


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    model: str | None = None
    system_prompt: str | None = None
    temperature: float | None = None


@dataclass(frozen=True)
class LLMResponse:
    model: str
    content: str
    raw_response: dict[str, Any]


@dataclass(frozen=True)
class LLMStreamChunk:
    model: str
    content: str
    done: bool
    raw_response: dict[str, Any]


class LLMClient(ABC):
    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Run a non-streaming completion request."""

    @abstractmethod
    def stream_generate(self, request: LLMRequest) -> Iterator[LLMStreamChunk]:
        """Run a streaming completion request."""
