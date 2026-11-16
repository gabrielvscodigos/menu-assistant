"""Tests for the HTTP API, using a fake LLM and a fake embedder (no network)."""

from collections.abc import Iterator, Sequence

import pytest
from chromadb.api.models.Collection import Collection
from fastapi.testclient import TestClient

from menu_assistant.api.main import create_app
from menu_assistant.ingest.indexer import index_menu
from menu_assistant.llm import ChatMessage, LLMError
from menu_assistant.models import Menu
from menu_assistant.rag.answer import SAFETY_NOTICE, AnswerService
from menu_assistant.retrieval.embeddings import Embedder
from menu_assistant.retrieval.search import MenuRetriever
from menu_assistant.retrieval.vector_store import IndexNotReadyError


class ScriptedLLM:
    def __init__(self, reply: str = "Try Edamame [edamame].", error: str | None = None) -> None:
        self.reply = reply
        self.error = error

    def generate(self, system: str, messages: Sequence[ChatMessage]) -> str:
        if self.error:
            raise LLMError(self.error)
        return self.reply


@pytest.fixture
def llm() -> ScriptedLLM:
    return ScriptedLLM()


@pytest.fixture
def client(
    sample_menu: Menu, collection: Collection, fake_embedder: Embedder, llm: ScriptedLLM
) -> Iterator[TestClient]:
    index_menu(sample_menu, collection, fake_embedder)
    service = AnswerService(MenuRetriever(collection, fake_embedder), llm, k=25)
    with TestClient(create_app(lambda: service)) as test_client:
        yield test_client


def test_health_is_ok_when_service_is_ready(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "detail": None}


def test_ask_returns_answer_with_cited_sources(client: TestClient) -> None:
    response = client.post("/ask", json={"question": "something light"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Try Edamame [edamame]."
    assert [source["id"] for source in body["sources"]] == ["edamame"]
    assert body["sources"][0]["allergens"] == ["soy"]
    assert len(body["candidates"]) == 25
    assert body["notice"] is None


def test_ask_combines_explicit_and_detected_restrictions(client: TestClient) -> None:
    response = client.post(
        "/ask",
        json={"question": "I'm allergic to peanuts, anything vegan?", "exclude_allergens": ["soy"]},
    )

    body = response.json()
    assert body["applied_restrictions"] == {
        "exclude_allergens": ["peanuts", "soy"],
        "require_flags": ["vegan"],
        "course": None,
    }
    candidate_ids = {candidate["id"] for candidate in body["candidates"]}
    assert candidate_ids == {"chana-masala", "falafel-plate", "mango-sticky-rice"}
    assert body["notice"] == SAFETY_NOTICE


@pytest.mark.parametrize(
    "payload",
    [
        {"question": ""},
        {"question": "x" * 501},
        {"question": "ok", "exclude_allergens": ["glutten"]},
        {"question": "ok", "require_flags": ["keto"]},
        {"question": "ok", "unexpected": True},
        {},
    ],
)
def test_invalid_requests_are_rejected(client: TestClient, payload: dict[str, object]) -> None:
    assert client.post("/ask", json=payload).status_code == 422


def test_llm_failure_returns_503(client: TestClient, llm: ScriptedLLM) -> None:
    llm.error = "cannot reach Ollama"

    response = client.post("/ask", json={"question": "spicy noodles"})

    assert response.status_code == 503
    assert response.json()["detail"] == "LLM unavailable: cannot reach Ollama"


def test_missing_index_degrades_instead_of_crashing() -> None:
    def failing_factory() -> AnswerService:
        raise IndexNotReadyError("index at .chroma is empty; run ingestion first")

    with TestClient(create_app(failing_factory)) as client:
        health = client.get("/health").json()
        ask = client.post("/ask", json={"question": "hi"})

    assert health == {
        "status": "degraded",
        "detail": "index at .chroma is empty; run ingestion first",
    }
    assert ask.status_code == 503
    assert "run ingestion" in ask.json()["detail"]


def test_ask_reports_detected_course(client: TestClient) -> None:
    body = client.post("/ask", json={"question": "a vegan dessert?"}).json()

    assert body["applied_restrictions"]["course"] == "dessert"
    assert [candidate["id"] for candidate in body["candidates"]] == ["mango-sticky-rice"]


def test_ask_accepts_explicit_course(client: TestClient) -> None:
    body = client.post("/ask", json={"question": "something light", "course": "starter"}).json()

    assert body["applied_restrictions"]["course"] == "starter"
    assert {candidate["course"] for candidate in body["candidates"]} == {"starter"}


def test_unknown_course_is_rejected(client: TestClient) -> None:
    assert client.post("/ask", json={"question": "ok", "course": "brunch"}).status_code == 422
