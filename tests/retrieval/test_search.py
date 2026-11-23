"""Tests for filtered semantic search, using a fake embedder and a temporary index."""

from typing import Any

import pytest
from chromadb.api.models.Collection import Collection
from pydantic import ValidationError

from menu_assistant.ingest.documents import dish_to_document, dish_to_metadata
from menu_assistant.ingest.indexer import index_menu
from menu_assistant.models import Allergen, Course, DietaryFlag, Dish, Menu
from menu_assistant.retrieval.embeddings import Embedder
from menu_assistant.retrieval.ingredients import disliked_ingredients
from menu_assistant.retrieval.metadata import allergen_key
from menu_assistant.retrieval.search import (
    MenuRetriever,
    SearchRequest,
    build_where,
    satisfies,
)


def get_dish(menu: Menu, dish_id: str) -> Dish:
    return next(dish for dish in menu.dishes if dish.id == dish_id)


@pytest.fixture
def retriever(sample_menu: Menu, collection: Collection, fake_embedder: Embedder) -> MenuRetriever:
    index_menu(sample_menu, collection, fake_embedder)
    return MenuRetriever(collection, fake_embedder)


def query_for(menu: Menu, dish_id: str, **restrictions: Any) -> SearchRequest:
    """A request whose text exactly matches one dish, so that dish is the nearest match."""
    return SearchRequest(query=dish_to_document(get_dish(menu, dish_id)), **restrictions)


# --- build_where -------------------------------------------------------------


def test_build_where_without_restrictions_is_none() -> None:
    assert build_where(SearchRequest(query="anything")) is None


def test_build_where_with_one_restriction_is_a_plain_condition() -> None:
    request = SearchRequest(query="x", exclude_allergens=frozenset({Allergen.PEANUTS}))

    assert build_where(request) == {"allergen_peanuts": False}


def test_build_where_combines_restrictions_in_a_stable_order() -> None:
    request = SearchRequest(
        query="x",
        exclude_allergens=frozenset({Allergen.SESAME, Allergen.GLUTEN}),
        require_flags=frozenset({DietaryFlag.VEGAN}),
        course=Course.DESSERT,
    )

    assert build_where(request) == {
        "$and": [
            {"allergen_gluten": False},
            {"allergen_sesame": False},
            {"diet_vegan": True},
            {"course": "dessert"},
        ]
    }


# --- SearchRequest -----------------------------------------------------------


@pytest.mark.parametrize("k", [0, 26])
def test_request_rejects_out_of_range_k(k: int) -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="x", k=k)


def test_request_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="   ")


# --- satisfies ---------------------------------------------------------------


def test_satisfies_checks_allergens_flags_and_course(sample_menu: Menu) -> None:
    curry = get_dish(sample_menu, "tofu-green-curry")

    assert satisfies(curry, SearchRequest(query="x", require_flags=frozenset({DietaryFlag.VEGAN})))
    assert not satisfies(
        curry, SearchRequest(query="x", exclude_allergens=frozenset({Allergen.SOY}))
    )
    assert not satisfies(curry, SearchRequest(query="x", course=Course.DESSERT))


# --- MenuRetriever.search ----------------------------------------------------


def test_nearest_dish_ranks_first_with_top_score(
    retriever: MenuRetriever, sample_menu: Menu
) -> None:
    results = retriever.search(query_for(sample_menu, "dan-dan-noodles"))

    assert results[0].dish.id == "dan-dan-noodles"
    assert results[0].score == pytest.approx(1.0)
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)


def test_excluded_allergen_removes_even_the_nearest_dish(
    retriever: MenuRetriever, sample_menu: Menu
) -> None:
    request = query_for(
        sample_menu, "dan-dan-noodles", exclude_allergens=frozenset({Allergen.PEANUTS}), k=25
    )

    results = retriever.search(request)

    assert "dan-dan-noodles" not in {r.dish.id for r in results}
    assert all(Allergen.PEANUTS not in r.dish.allergens for r in results)
    assert len(results) == sum(Allergen.PEANUTS not in d.allergens for d in sample_menu.dishes)


def test_required_flags_and_course_are_respected(retriever: MenuRetriever) -> None:
    request = SearchRequest(
        query="something sweet",
        require_flags=frozenset({DietaryFlag.VEGETARIAN}),
        course=Course.DESSERT,
        k=25,
    )

    results = retriever.search(request)

    assert {r.dish.id for r in results} == {
        "tiramisu",
        "mango-sticky-rice",
        "flourless-chocolate-cake",
    }


def test_impossible_restrictions_return_no_results(retriever: MenuRetriever) -> None:
    request = SearchRequest(
        query="dessert",
        require_flags=frozenset({DietaryFlag.VEGAN}),
        exclude_allergens=frozenset({Allergen.SESAME}),
        course=Course.DESSERT,
    )

    assert retriever.search(request) == []


def test_k_limits_the_number_of_results(retriever: MenuRetriever) -> None:
    assert len(retriever.search(SearchRequest(query="anything", k=3))) == 3


def test_dish_with_wrong_index_metadata_is_still_dropped(
    sample_menu: Menu, collection: Collection, fake_embedder: Embedder
) -> None:
    # Simulate a corrupted index entry: metadata says "no peanuts", dish data says otherwise.
    dish = get_dish(sample_menu, "dan-dan-noodles")
    metadata = dish_to_metadata(dish) | {allergen_key(Allergen.PEANUTS): False}
    document = dish_to_document(dish)
    collection.upsert(
        ids=[dish.id],
        embeddings=fake_embedder.embed_documents([document]),
        documents=[document],
        metadatas=[metadata],
    )
    retriever = MenuRetriever(collection, fake_embedder)

    request = query_for(sample_menu, dish.id, exclude_allergens=frozenset({Allergen.PEANUTS}))

    assert retriever.search(request) == []


# --- tag boosting --------------------------------------------------------------


def boosted(collection: Collection, embedder: Embedder, tag_boost: float) -> MenuRetriever:
    return MenuRetriever(collection, embedder, tag_boost=tag_boost)


def test_tag_boost_promotes_dishes_with_tags_named_in_the_query(
    retriever: MenuRetriever, collection: Collection, fake_embedder: Embedder, sample_menu: Menu
) -> None:
    # The fake embedder gives arbitrary similarities, so a large boost must dominate.
    request = SearchRequest(query="spicy", k=5)
    spicy_dishes = {d.id for d in sample_menu.dishes if "spicy" in d.tags}

    results = boosted(collection, fake_embedder, tag_boost=10.0).search(request)

    assert {r.dish.id for r in results} <= spicy_dishes
    assert all(r.matched_tags == {"spicy"} for r in results)
    assert all(r.score == pytest.approx(r.similarity + 10.0) for r in results)


def test_tag_boost_never_overrides_filters(
    retriever: MenuRetriever, collection: Collection, fake_embedder: Embedder
) -> None:
    request = SearchRequest(
        query="spicy sichuan noodles", exclude_allergens=frozenset({Allergen.PEANUTS}), k=25
    )

    results = boosted(collection, fake_embedder, tag_boost=10.0).search(request)

    assert "dan-dan-noodles" not in {r.dish.id for r in results}
    assert all(Allergen.PEANUTS not in r.dish.allergens for r in results)


def test_without_boost_score_equals_similarity(retriever: MenuRetriever) -> None:
    results = retriever.search(SearchRequest(query="spicy noodles"))

    assert all(r.score == r.similarity and not r.matched_tags for r in results)


def test_negative_tag_boost_is_rejected(collection: Collection, fake_embedder: Embedder) -> None:
    with pytest.raises(ValueError):
        MenuRetriever(collection, fake_embedder, tag_boost=-0.1)


# --- disliked ingredients ------------------------------------------------------


def test_disliked_ingredient_removes_even_the_nearest_dish(
    sample_menu: Menu, retriever: MenuRetriever
) -> None:
    request = query_for(sample_menu, "chana-masala", exclude_ingredients=frozenset({"onion"}))

    results = retriever.search(request)

    assert "chana-masala" not in {r.dish.id for r in results}
    assert all(not disliked_ingredients(r.dish, {"onion"}) for r in results)


def test_disliked_ingredients_still_fill_k_results(
    sample_menu: Menu, retriever: MenuRetriever
) -> None:
    # These remove most of the menu, so the nearest k dishes alone would not be enough.
    disliked = frozenset({"wheat", "egg", "garlic"})
    remaining = [d for d in sample_menu.dishes if not disliked_ingredients(d, disliked)]

    results = retriever.search(SearchRequest(query="noodles", exclude_ingredients=disliked, k=5))

    assert len(results) == min(5, len(remaining))
    assert all(not disliked_ingredients(r.dish, disliked) for r in results)


def test_satisfies_checks_disliked_ingredients(sample_menu: Menu) -> None:
    dish = get_dish(sample_menu, "chana-masala")

    assert not satisfies(dish, SearchRequest(query="x", exclude_ingredients=frozenset({"onion"})))
    assert satisfies(dish, SearchRequest(query="x", exclude_ingredients=frozenset({"pork"})))


def test_ingredient_terms_are_normalized_and_validated() -> None:
    request = SearchRequest(query="x", exclude_ingredients=frozenset({"  Onion "}))

    assert request.exclude_ingredients == {"onion"}
    with pytest.raises(ValidationError):
        SearchRequest(query="x", exclude_ingredients=frozenset({"x"}))


# --- excluded dishes -------------------------------------------------------------


def test_excluded_dishes_are_skipped_and_k_is_still_filled(
    sample_menu: Menu, retriever: MenuRetriever
) -> None:
    shown = frozenset({"chana-masala", "falafel-plate", "tofu-green-curry", "edamame"})
    request = query_for(sample_menu, "chana-masala", exclude_dishes=shown, k=5)

    results = retriever.search(request)

    assert len(results) == 5
    assert shown.isdisjoint(r.dish.id for r in results)


def test_satisfies_checks_excluded_dishes(sample_menu: Menu) -> None:
    dish = get_dish(sample_menu, "edamame")

    assert not satisfies(dish, SearchRequest(query="x", exclude_dishes=frozenset({"edamame"})))
    assert satisfies(dish, SearchRequest(query="x", exclude_dishes=frozenset({"elote"})))
