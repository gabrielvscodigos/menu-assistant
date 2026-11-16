"""Text embedding interface and the sentence-transformers implementation."""

from collections.abc import Sequence
from typing import Protocol

from menu_assistant.config import Settings


class Embedder(Protocol):
    """Turns texts into fixed-size vectors. Implementations must be deterministic.

    Documents and queries have separate methods because some models (e.g. E5) expect
    different instruction prefixes for each.
    """

    def embed_documents(self, texts: Sequence[str]) -> list[Sequence[float]]:
        """Return one embedding per document, in the same order."""
        ...

    def embed_queries(self, texts: Sequence[str]) -> list[Sequence[float]]:
        """Return one embedding per search query, in the same order."""
        ...


class SentenceTransformerEmbedder:
    """Embedder backed by a local sentence-transformers model.

    The model is downloaded on first use and cached by Hugging Face. Embeddings are
    L2-normalized so cosine similarity and dot product agree.
    """

    def __init__(self, model_name: str, query_prefix: str = "", document_prefix: str = "") -> None:
        # Imported lazily: loading torch is slow and unnecessary for code paths
        # (and tests) that use a different embedder.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self._query_prefix = query_prefix
        self._document_prefix = document_prefix

    def embed_documents(self, texts: Sequence[str]) -> list[Sequence[float]]:
        return self._encode([self._document_prefix + text for text in texts])

    def embed_queries(self, texts: Sequence[str]) -> list[Sequence[float]]:
        return self._encode([self._query_prefix + text for text in texts])

    def _encode(self, texts: list[str]) -> list[Sequence[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [[float(value) for value in vector] for vector in vectors]


def embedder_from_settings(settings: Settings) -> SentenceTransformerEmbedder:
    """Build the configured embedder, including any model-specific prefixes."""
    return SentenceTransformerEmbedder(
        settings.embedding_model,
        query_prefix=settings.embedding_query_prefix,
        document_prefix=settings.embedding_document_prefix,
    )
