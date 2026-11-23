"""Tests for matching disliked ingredients against a dish's ingredient list."""

from decimal import Decimal

import pytest

from menu_assistant.models import Course, Dish, Price
from menu_assistant.retrieval.ingredients import disliked_ingredients


def dish_with(*ingredients: str) -> Dish:
    return Dish(
        id="test-dish",
        name="Test Dish",
        course=Course.MAIN,
        description="A dish for tests.",
        ingredients=list(ingredients),
        preparation="Cooked.",
        price=Price(amount=Decimal("10.00"), currency="USD"),
    )


@pytest.mark.parametrize(
    ("term", "ingredient"),
    [
        ("onion", "onion"),
        ("onion", "white onion"),
        ("onion", "sumac onions"),  # plural in the menu
        ("onions", "white onion"),  # plural in the request
        ("chili", "ancho chilies"),
        ("tomato", "cherry tomatoes"),
        ("pork", "guanciale (cured pork cheek)"),  # inside parentheses
        ("fish sauce", "kimchi (with fish sauce)"),  # multi-word term
        ("jalapeno", "Jalapeño"),  # accents and case
        ("cherry", "cherries"),
    ],
)
def test_term_matches_ingredient(term: str, ingredient: str) -> None:
    assert disliked_ingredients(dish_with(ingredient), [term]) == {term}


@pytest.mark.parametrize(
    ("term", "ingredient"),
    [
        ("pea", "chickpeas"),  # not a whole word
        ("onion", "scallions"),
        ("fish sauce", "fish"),
        ("rice", "licorice"),
    ],
)
def test_term_does_not_match_other_words(term: str, ingredient: str) -> None:
    assert disliked_ingredients(dish_with(ingredient), [term]) == set()


def test_returns_only_the_matching_terms() -> None:
    dish = dish_with("garlic", "olive oil", "basil")

    assert disliked_ingredients(dish, ["garlic", "onion", "basil"]) == {"garlic", "basil"}
