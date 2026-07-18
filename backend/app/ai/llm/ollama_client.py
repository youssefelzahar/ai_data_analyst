import json
from collections.abc import Iterator
from typing import Any
from urllib import error, request

from app.ai.llm.base import LLMClient, LLMRequest, LLMResponse, LLMStreamChunk, ModelConfig


class OllamaClientError(Exception):
    """Raised when communication with Ollama fails."""


class OllamaClient(LLMClient):
    """Thin Ollama wrapper with sync and streaming generation support."""

    def __init__(
        self,
        base_url: str,
        model_config: ModelConfig,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_config = model_config

    def generate(self, request_payload: LLMRequest) -> LLMResponse:
        payload = self._build_payload(request_payload, stream=False)
        raw_response = self._post_json("/api/generate", payload)
        return LLMResponse(
            model=raw_response.get("model", payload["model"]),
            content=str(raw_response.get("response", "")),
            raw_response=raw_response,
        )

    def stream_generate(self, request_payload: LLMRequest) -> Iterator[LLMStreamChunk]:
        payload = self._build_payload(request_payload, stream=True)
        for event in self._stream_json_lines("/api/generate", payload):
            yield LLMStreamChunk(
                model=event.get("model", payload["model"]),
                content=str(event.get("response", "")),
                done=bool(event.get("done", False)),
                raw_response=event,
            )

    def _build_payload(self, request_payload: LLMRequest, stream: bool) -> dict[str, Any]:
        model_name = request_payload.model or self._model_config.default_model
        temperature = (
            request_payload.temperature
            if request_payload.temperature is not None
            else self._model_config.temperature
        )
        payload: dict[str, Any] = {
            "model": model_name,
            "prompt": request_payload.prompt,
            "stream": stream,
            "options": {"temperature": temperature},
        }
        if request_payload.system_prompt:
            payload["system"] = request_payload.system_prompt
        return payload
    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        target_url = f"{self._base_url}{path}"

        req = request.Request(
            target_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(
                req,
                timeout=self._model_config.request_timeout_seconds,
            ) as response:
                return json.loads(response.read().decode())

        except error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")

            raise OllamaClientError(
                f"""
    HTTP {e.code}
    Reason: {e.reason}

    Response:
    {body}
    """
            ) from e

        except TimeoutError as e:
            raise OllamaClientError(
                f"Ollama timed out after {self._model_config.request_timeout_seconds} seconds. "
                "The model may still be loading or the request is too large."
            ) from e

        except error.URLError as e:
            raise OllamaClientError(
                f"Cannot connect to Ollama ({target_url}). {e.reason}"
            ) from e

        except json.JSONDecodeError as e:
            raise OllamaClientError(
                f"Ollama returned invalid JSON: {e}"
            ) from e
    def _stream_json_lines(self, path: str, payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
        target_url = f"{self._base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        request_object = request.Request(
            target_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(
                request_object,
                timeout=self._model_config.request_timeout_seconds,
            ) as response:
                for raw_line in response:
                    decoded_line = raw_line.decode("utf-8").strip()
                    if not decoded_line:
                        continue
                    yield json.loads(decoded_line)
        except TimeoutError as request_error:
            raise OllamaClientError(
                f"Ollama streaming request timed out after {self._model_config.request_timeout_seconds} seconds."
            ) from request_error
        except (error.URLError, error.HTTPError, json.JSONDecodeError) as request_error:
            raise OllamaClientError(f"Ollama streaming request failed: {request_error}") from request_error

