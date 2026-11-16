"""LLM client for a local Ollama server, using its `/api/chat` endpoint."""

from collections.abc import Sequence

import httpx
from pydantic import BaseModel, ValidationError

from menu_assistant.llm.base import ChatMessage, LLMError


class _ResponseMessage(BaseModel):
    content: str


class _ChatResponse(BaseModel):
    message: _ResponseMessage


class OllamaClient:
    """Sends non-streaming chat requests to Ollama and returns the reply text."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        temperature: float = 0.2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._temperature = temperature
        # `transport` lets tests replace the network with an in-memory handler.
        self._http = httpx.Client(base_url=base_url, timeout=timeout_seconds, transport=transport)

    def generate(self, system: str, messages: Sequence[ChatMessage]) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                *({"role": m.role, "content": m.content} for m in messages),
            ],
            "stream": False,
            "options": {"temperature": self._temperature},
        }
        response = self._post(payload)
        self._raise_for_status(response)
        return self._parse(response)

    def close(self) -> None:
        self._http.close()

    def _post(self, payload: dict[str, object]) -> httpx.Response:
        try:
            return self._http.post("/api/chat", json=payload)
        except httpx.TimeoutException as error:
            raise LLMError(
                f"Ollama did not answer within {self._timeout_seconds:g}s; "
                "try a smaller model or a longer timeout"
            ) from error
        except httpx.TransportError as error:
            raise LLMError(
                f"cannot reach Ollama at {self._base_url}; is it running? ({error})"
            ) from error

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        detail = _error_detail(response)
        if response.status_code == httpx.codes.NOT_FOUND and "not found" in detail:
            raise LLMError(
                f"model '{self._model}' is not available in Ollama; run `ollama pull {self._model}`"
            )
        raise LLMError(f"Ollama returned HTTP {response.status_code}: {detail}")

    def _parse(self, response: httpx.Response) -> str:
        try:
            content = _ChatResponse.model_validate_json(response.content).message.content
        except ValidationError as error:
            raise LLMError(f"unexpected response from Ollama: {error}") from error
        if not content.strip():
            raise LLMError("Ollama returned an empty answer")
        return content.strip()


def _error_detail(response: httpx.Response) -> str:
    """Ollama reports errors as {"error": "..."}; fall back to the raw body."""
    try:
        body = response.json()
    except ValueError:
        return response.text
    error = body.get("error") if isinstance(body, dict) else None
    return error if isinstance(error, str) else response.text
