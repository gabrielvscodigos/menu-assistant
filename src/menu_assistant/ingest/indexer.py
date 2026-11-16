"""Write a validated menu into the vector store."""

from dataclasses import dataclass

from chromadb.api.models.Collection import Collection
from chromadb.api.types import Metadata

from menu_assistant.ingest.documents import dish_to_document, dish_to_metadata
from menu_assistant.models import Menu
from menu_assistant.retrieval.embeddings import Embedder


@dataclass(frozen=True)
class IndexResult:
    """Summary of an indexing run."""

    indexed: int
    removed: int


def index_menu(menu: Menu, collection: Collection, embedder: Embedder) -> IndexResult:
    """Make `collection` contain exactly the dishes in `menu`.

    Dishes are upserted by id, so re-running is idempotent. Dishes that are in the
    collection but no longer on the menu are deleted, so they can never be recommended.
    """
    ids = [dish.id for dish in menu.dishes]
    documents = [dish_to_document(dish) for dish in menu.dishes]
    metadatas: list[Metadata] = [dish_to_metadata(dish) for dish in menu.dishes]

    collection.upsert(
        ids=ids,
        embeddings=embedder.embed_documents(documents),
        documents=documents,
        metadatas=metadatas,
    )

    stale_ids = sorted(set(collection.get(include=[])["ids"]) - set(ids))
    if stale_ids:
        collection.delete(ids=stale_ids)

    return IndexResult(indexed=len(ids), removed=len(stale_ids))
