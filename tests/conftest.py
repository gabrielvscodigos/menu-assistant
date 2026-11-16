"""Shared test fixtures: sample menu, a fake embedder, and a throwaway vector store."""

import hashlib
from collections.abc import Sequence
from pathlib import Path

import pytest
from chromadb.api.models.Collection import Collection

from menu_assistant.ingest import load_menu
from menu_assistant.models import Menu
from menu_assistant.retrieval.vector_store import open_collection

SAMPLE_MENU_PATH = Path(__file__).parents[1] / "data" / "menu.json"


class FakeEmbedder:
    """Deterministic, model-free embedder: identical texts map to identical vectors."""

    def __init__(self, dimensions: int = 16) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: Sequence[str]) -> list[Sequence[float]]:
        return [self._vector(text) for text in texts]

    def embed_queries(self, texts: Sequence[str]) -> list[Sequence[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [byte / 255 for byte in digest[: self.dimensions]]


@pytest.fixture
def sample_menu_path() -> Path:
    return SAMPLE_MENU_PATH


@pytest.fixture
def sample_menu() -> Menu:
    return load_menu(SAMPLE_MENU_PATH)


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def collection(tmp_path: Path) -> Collection:
    return open_collection(tmp_path / "chroma", "test-menu", index_signature="fake")
