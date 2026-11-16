"""Access to the persistent ChromaDB collection that stores indexed dishes."""

from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings


def open_collection(path: Path, name: str) -> Collection:
    """Open (or create) the dish collection stored at `path`.

    Embeddings are always computed by our own `Embedder`, so the collection has no
    embedding function. Distances use cosine similarity.
    """
    client = chromadb.PersistentClient(
        path=path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name=name,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,
    )
