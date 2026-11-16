"""Build a ready-to-use retriever from settings."""

from menu_assistant.config import Settings
from menu_assistant.retrieval.embeddings import embedder_from_settings
from menu_assistant.retrieval.search import MenuRetriever
from menu_assistant.retrieval.vector_store import IndexNotReadyError, open_collection

INGEST_HINT = "run `python -m menu_assistant.ingest data/menu.json` first"


def retriever_from_settings(settings: Settings) -> MenuRetriever:
    """Open the configured index and return a retriever over it.

    Raises:
        IndexNotReadyError: if the index is empty or was built with another model.
    """
    collection = open_collection(
        settings.chroma_path, settings.collection_name, settings.index_signature
    )
    if collection.count() == 0:
        raise IndexNotReadyError(f"index at {settings.chroma_path} is empty; {INGEST_HINT}")
    return MenuRetriever(collection, embedder_from_settings(settings), tag_boost=settings.tag_boost)
