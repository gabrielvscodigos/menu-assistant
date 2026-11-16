"""Access to the persistent ChromaDB collection that stores indexed dishes."""

import logging
from pathlib import Path

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

INDEX_SIGNATURE_KEY = "index_signature"


class IndexNotReadyError(Exception):
    """The index cannot be searched yet; re-running ingestion fixes it."""


class IndexMismatchError(IndexNotReadyError):
    """The stored index was built with a different embedding setup than requested."""


def open_collection(
    path: Path, name: str, index_signature: str, reset_on_mismatch: bool = False
) -> Collection:
    """Open (or create) the dish collection stored at `path`.

    Vectors from different embedding models are not comparable, so each collection
    records the `index_signature` it was built with. Opening it with a different
    signature either raises `IndexMismatchError` or, with `reset_on_mismatch`, drops the
    old collection so it can be rebuilt.

    Embeddings are always computed by our own `Embedder`, so the collection has no
    embedding function. Distances use cosine similarity.
    """
    client = chromadb.PersistentClient(
        path=path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    existing = _get_existing(client, name)
    if existing is not None:
        stored = (existing.metadata or {}).get(INDEX_SIGNATURE_KEY)
        if stored == index_signature:
            return existing
        if not reset_on_mismatch:
            raise IndexMismatchError(
                f"collection '{name}' at {path} was built with {stored!r}, "
                f"not {index_signature!r}; re-run ingestion"
            )
        logger.info("resetting collection '%s': embedding setup changed", name)
        client.delete_collection(name)

    return client.create_collection(
        name=name,
        configuration={"hnsw": {"space": "cosine"}},
        metadata={INDEX_SIGNATURE_KEY: index_signature},
        embedding_function=None,
    )


def _get_existing(client: ClientAPI, name: str) -> Collection | None:
    if name not in {collection.name for collection in client.list_collections()}:
        return None
    return client.get_collection(name=name, embedding_function=None)
