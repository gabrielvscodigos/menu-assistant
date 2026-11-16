"""Text embedding interface and the sentence-transformers implementation."""

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    """Turns texts into fixed-size vectors. Implementations must be deterministic."""

    def embed(self, texts: Sequence[str]) -> list[Sequence[float]]:
        """Return one embedding per input text, in the same order."""
        ...


class SentenceTransformerEmbedder:
    """Embedder backed by a local sentence-transformers model.

    The model is downloaded on first use and cached by Hugging Face. Embeddings are
    L2-normalized so cosine similarity and dot product agree.
    """

    def __init__(self, model_name: str) -> None:
        # Imported lazily: loading torch is slow and unnecessary for code paths
        # (and tests) that use a different embedder.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: Sequence[str]) -> list[Sequence[float]]:
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return [[float(value) for value in vector] for vector in vectors]
