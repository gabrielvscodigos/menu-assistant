"""Tests for deterministic restriction detection in English, Portuguese, and Spanish."""

import pytest

from menu_assistant.models import Allergen, DietaryFlag
from menu_assistant.rag.restrictions import (
    Restrictions,
    detect_restrictions,
    ingredient_terms,
    mentions_dietary_topic,
)

A = Allergen
F = DietaryFlag


@pytest.mark.parametrize(
    ("question", "allergens"),
    [
        ("I'm allergic to peanuts", {A.PEANUTS}),
        ("peanut allergy here, what can I eat?", {A.PEANUTS}),
        ("something nut-free please", {A.PEANUTS, A.TREE_NUTS}),
        ("no shellfish please", {A.CRUSTACEANS, A.MOLLUSCS}),
        ("I can't eat eggs or milk", {A.EGGS, A.MILK}),
        (
            "allergic to peanuts, sesame and shellfish",
            {A.PEANUTS, A.SESAME, A.CRUSTACEANS, A.MOLLUSCS},
        ),
        ("I avoid seafood", {A.FISH, A.CRUSTACEANS, A.MOLLUSCS}),
        ("sou alérgico a amendoim", {A.PEANUTS}),
        ("algo sem camarão e sem gergelim", {A.CRUSTACEANS, A.SESAME}),
        ("tenho alergia a frutos do mar", {A.CRUSTACEANS, A.MOLLUSCS}),
        ("soy alérgica al maní", {A.PEANUTS}),
        ("algo sin huevos ni mariscos", {A.EGGS, A.CRUSTACEANS, A.MOLLUSCS}),
        ("I don't eat fish", {A.FISH}),
    ],
)
def test_detects_allergens_to_avoid(question: str, allergens: set[Allergen]) -> None:
    assert detect_restrictions(question).exclude_allergens == allergens


@pytest.mark.parametrize(
    "question",
    [
        "I love peanuts",
        "something with shrimp",
        "spicy noodles with egg",
        "a coconut dessert",  # 'nut' inside a word
        "eggplant dishes?",  # 'egg' inside a word
        "",
    ],
)
def test_ignores_allergens_mentioned_without_a_cue(question: str) -> None:
    assert detect_restrictions(question).exclude_allergens == frozenset()


def test_cue_does_not_cross_into_the_next_clause() -> None:
    restrictions = detect_restrictions("I'm allergic to peanuts but I love shrimp")

    assert restrictions.exclude_allergens == {A.PEANUTS}


@pytest.mark.parametrize(
    ("question", "flags"),
    [
        ("any vegan options?", {F.VEGAN}),
        ("sou vegetariana", {F.VEGETARIAN}),
        ("I'm celiac", {F.GLUTEN_FREE}),
        ("gluten-free dessert", {F.GLUTEN_FREE}),
        ("sobremesa sem glúten", {F.GLUTEN_FREE}),
        ("I'm lactose intolerant", {F.DAIRY_FREE}),
        ("algo sin lactosa", {F.DAIRY_FREE}),
        ("tenho intolerância à lactose", {F.DAIRY_FREE}),
        ("halal meat please", {F.HALAL}),
        ("quero um prato vegano e sem lactose", {F.VEGAN, F.DAIRY_FREE}),
        ("spicy ramen", set()),
    ],
)
def test_detects_required_diets(question: str, flags: set[DietaryFlag]) -> None:
    assert detect_restrictions(question).require_flags == flags


def test_restrictions_merge_and_truthiness() -> None:
    explicit = Restrictions(exclude_allergens=frozenset({A.SOY}))
    detected = Restrictions(require_flags=frozenset({F.VEGAN}))

    merged = explicit.merge(detected)

    assert merged == Restrictions(
        exclude_allergens=frozenset({A.SOY}), require_flags=frozenset({F.VEGAN})
    )
    assert merged
    assert not Restrictions()


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("does the ramen have peanuts?", True),
        ("is the curry vegan?", True),
        ("tenho alergia", True),
        ("what's good and spicy?", False),
    ],
)
def test_mentions_dietary_topic(question: str, expected: bool) -> None:
    assert mentions_dietary_topic(question) is expected


@pytest.mark.parametrize(
    ("question", "ingredients"),
    [
        ("something spicy, no cilantro please", {"cilantro"}),
        ("I hate onions", {"onion"}),
        ("I don't like mushrooms or garlic", {"mushroom", "shiitake", "garlic"}),
        ("tacos, hold the onion", {"onion"}),
        ("onion-free curry?", {"onion"}),
        ("algo sem cebola e sem alho", {"onion", "garlic"}),
        ("não gosto de coentro", {"cilantro", "coriander"}),
        ("odeio cogumelos, tem massa?", {"mushroom", "shiitake"}),
        ("tem algo sem carne de porco?", {"pork"}),
        ("tacos sin cebolla ni cilantro", {"onion", "cilantro"}),
        ("no me gustan los tomates", {"tomato"}),
    ],
)
def test_detects_ingredients_to_avoid(question: str, ingredients: set[str]) -> None:
    assert detect_restrictions(question).exclude_ingredients == ingredients


@pytest.mark.parametrize(
    "question",
    [
        "I love onions and garlic",
        "Do you have chicken?",
        "tem frango com cogumelos?",
        "quiero algo con tomate",
    ],
)
def test_ignores_ingredients_mentioned_without_a_cue(question: str) -> None:
    assert detect_restrictions(question).exclude_ingredients == set()


def test_ingredient_cue_does_not_cross_into_the_next_clause() -> None:
    restrictions = detect_restrictions("No onions, please. Do you have chicken?")

    assert restrictions.exclude_ingredients == {"onion"}


def test_disliked_ingredients_make_restrictions_truthy_and_merge() -> None:
    explicit = Restrictions(exclude_ingredients=frozenset({"onion"}))
    detected = Restrictions(exclude_ingredients=frozenset({"garlic"}))

    merged = explicit.merge(detected)

    assert merged.exclude_ingredients == {"onion", "garlic"}
    assert explicit


@pytest.mark.parametrize(
    ("words", "terms"),
    [
        (["cebola"], {"onion"}),
        (["Cebolas", "coentro"], {"onion", "cilantro", "coriander"}),
        (["onion"], {"onion"}),
        (["fish sauce"], {"fish sauce"}),  # not in the word list: kept as given
    ],
)
def test_ingredient_terms_maps_known_words(words: list[str], terms: set[str]) -> None:
    assert ingredient_terms(words) == terms


def test_without_keeps_only_restrictions_the_other_lacks() -> None:
    current = Restrictions(
        exclude_allergens=frozenset({Allergen.EGGS, Allergen.MILK}),
        require_flags=frozenset({DietaryFlag.VEGAN}),
    )
    earlier = Restrictions(exclude_allergens=frozenset({Allergen.MILK}))

    assert current.without(earlier) == Restrictions(
        exclude_allergens=frozenset({Allergen.EGGS}),
        require_flags=frozenset({DietaryFlag.VEGAN}),
    )
    assert not earlier.without(current)
