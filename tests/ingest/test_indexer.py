"""Tests for indexing a menu into ChromaDB, using a fake embedder."""

from chromadb.api.models.Collection import Collection

from menu_assistant.ingest.documents import dish_to_document
from menu_assistant.ingest.indexer import IndexResult, index_menu
from menu_assistant.models import Allergen, Menu
from menu_assistant.retrieval.embeddings import Embedder


def test_indexes_every_dish(
    sample_menu: Menu, collection: Collection, fake_embedder: Embedder
) -> None:
    result = index_menu(sample_menu, collection, fake_embedder)

    assert result == IndexResult(indexed=len(sample_menu.dishes), removed=0)
    assert collection.count() == len(sample_menu.dishes)


def test_reindexing_is_idempotent(
    sample_menu: Menu, collection: Collection, fake_embedder: Embedder
) -> None:
    index_menu(sample_menu, collection, fake_embedder)

    result = index_menu(sample_menu, collection, fake_embedder)

    assert result.removed == 0
    assert collection.count() == len(sample_menu.dishes)


def test_dishes_removed_from_menu_are_deleted(
    sample_menu: Menu, collection: Collection, fake_embedder: Embedder
) -> None:
    index_menu(sample_menu, collection, fake_embedder)
    smaller_menu = Menu(restaurant=sample_menu.restaurant, dishes=sample_menu.dishes[:5])

    result = index_menu(smaller_menu, collection, fake_embedder)

    assert result == IndexResult(indexed=5, removed=len(sample_menu.dishes) - 5)
    assert sorted(collection.get(include=[])["ids"]) == sorted(d.id for d in smaller_menu.dishes)


def test_allergen_metadata_supports_exact_filtering(
    sample_menu: Menu, collection: Collection, fake_embedder: Embedder
) -> None:
    index_menu(sample_menu, collection, fake_embedder)
    expected = {dish.id for dish in sample_menu.dishes if Allergen.PEANUTS not in dish.allergens}

    found = collection.get(where={"allergen_peanuts": False}, include=[])["ids"]

    assert set(found) == expected
    assert "dan-dan-noodles" not in found


def test_stored_embedding_matches_dish_document(
    sample_menu: Menu, collection: Collection, fake_embedder: Embedder
) -> None:
    index_menu(sample_menu, collection, fake_embedder)
    edamame = next(dish for dish in sample_menu.dishes if dish.id == "edamame")

    result = collection.query(
        query_embeddings=fake_embedder.embed([dish_to_document(edamame)]),
        n_results=1,
        include=[],
    )

    assert result["ids"] == [["edamame"]]
