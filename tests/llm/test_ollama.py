"""Tests for the Ollama client, using an in-memory HTTP transport (no network)."""

import json
from collections.abc import Callable

import httpx
import pytest

from menu_assistant.config import Settings
from menu_assistant.llm import ChatMessage, LLMError
from menu_assistant.llm.factory import llm_client_from_settings
from menu_assistant.llm.ollama import OllamaClient

Handler = Callable[[httpx.Request], httpx.Response]

USER_MESSAGE = [ChatMessage(role="user", content="Hi")]


def make_client(handler: Handler) -> OllamaClient:
    return OllamaClient(
        base_url="http://ollama.test",
        model="test-model",
        timeout_seconds=5,
        temperature=0.3,
        transport=httpx.MockTransport(handler),
    )


def reply(content: str) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    return handler


def test_sends_system_prompt_messages_and_options() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return reply("Hello!")(request)

    answer = make_client(handler).generate("Be brief.", USER_MESSAGE)

    assert answer == "Hello!"
    request = captured[0]
    assert request.method == "POST"
    assert request.url == "http://ollama.test/api/chat"
    assert json.loads(request.content) == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": "Hi"},
        ],
        "stream": False,
        "options": {"temperature": 0.3},
    }


def test_strips_whitespace_from_answer() -> None:
    assert make_client(reply("  spaced out \n")).generate("s", USER_MESSAGE) == "spaced out"


def test_empty_answer_is_an_error() -> None:
    with pytest.raises(LLMError, match="empty answer"):
        make_client(reply("   ")).generate("s", USER_MESSAGE)


def test_unreachable_server_is_explained() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(LLMError, match=r"cannot reach Ollama at http://ollama\.test; is it"):
        make_client(handler).generate("s", USER_MESSAGE)


def test_timeout_is_explained() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(LLMError, match="did not answer within 5s"):
        make_client(handler).generate("s", USER_MESSAGE)


def test_missing_model_suggests_pulling_it() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'test-model' not found"})

    with pytest.raises(LLMError, match="run `ollama pull test-model`"):
        make_client(handler).generate("s", USER_MESSAGE)


def test_other_http_errors_include_status_and_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "out of memory"})

    with pytest.raises(LLMError, match="HTTP 500: out of memory"):
        make_client(handler).generate("s", USER_MESSAGE)


def test_malformed_response_is_an_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with pytest.raises(LLMError, match="unexpected response"):
        make_client(handler).generate("s", USER_MESSAGE)


def test_factory_builds_ollama_client_from_settings() -> None:
    client = llm_client_from_settings(Settings(llm_model="llama3.2"))

    assert isinstance(client, OllamaClient)
