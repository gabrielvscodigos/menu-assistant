"""Tests for the menu domain models and their consistency rules."""

from typing import Any

import pytest
from pydantic import ValidationError

from menu_assistant.models import Allergen, DietaryFlag, Dish, Menu


def make_dish_data(**overrides: Any) -> dict[str, Any]:
    """Return valid raw dish data, with any field overridden."""
    data: dict[str, Any] = {
        "id": "test-dish",
        "name": "Test Dish",
        "course": "main",
        "description": "A dish used in tests.",
        "ingredients": ["rice"],
        "preparation": "Boiled.",
    }
    data.update(overrides)
    return data


def test_valid_dish_is_parsed_into_enums() -> None:
    dish = Dish.model_validate(
        make_dish_data(dietary_flags=["vegetarian"], allergens=["milk", "eggs"])
    )

    assert dish.dietary_flags == {DietaryFlag.VEGETARIAN}
    assert dish.allergens == {Allergen.MILK, Allergen.EGGS}


def test_tags_are_normalized_to_lowercase() -> None:
    dish = Dish.model_validate(make_dish_data(tags=["  Spicy ", "JAPANESE"]))

    assert dish.tags == ["spicy", "japanese"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("allergens", ["glutten"]),
        ("dietary_flags", ["keto"]),
        ("course", "brunch"),
    ],
)
def test_unknown_vocabulary_values_are_rejected(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        Dish.model_validate(make_dish_data(**{field: value}))


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="extra"):
        Dish.model_validate(make_dish_data(alergens=["milk"]))


@pytest.mark.parametrize("bad_id", ["Has Spaces", "UPPER", "trailing-", "", "under_score"])
def test_invalid_dish_ids_are_rejected(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        Dish.model_validate(make_dish_data(id=bad_id))


def test_empty_ingredients_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Dish.model_validate(make_dish_data(ingredients=[]))


@pytest.mark.parametrize(
    ("flags", "allergens"),
    [
        (["vegan", "vegetarian", "dairy_free"], ["eggs"]),
        (["vegetarian"], ["fish"]),
        (["vegetarian"], ["crustaceans"]),
        (["gluten_free"], ["gluten"]),
        (["dairy_free"], ["milk"]),
    ],
)
def test_flags_contradicting_allergens_are_rejected(flags: list[str], allergens: list[str]) -> None:
    with pytest.raises(ValidationError, match="lists allergens"):
        Dish.model_validate(make_dish_data(dietary_flags=flags, allergens=allergens))


def test_vegan_without_implied_flags_is_rejected() -> None:
    with pytest.raises(ValidationError, match="missing flags: dairy_free, vegetarian"):
        Dish.model_validate(make_dish_data(dietary_flags=["vegan"]))


def test_menu_rejects_duplicate_dish_ids() -> None:
    dish = make_dish_data(id="same-id")

    with pytest.raises(ValidationError, match="duplicate dish ids: same-id"):
        Menu.model_validate({"restaurant": "Test", "dishes": [dish, dish]})


def test_menu_requires_at_least_one_dish() -> None:
    with pytest.raises(ValidationError):
        Menu.model_validate({"restaurant": "Test", "dishes": []})


def test_dish_is_immutable() -> None:
    dish = Dish.model_validate(make_dish_data())

    with pytest.raises(ValidationError):
        dish.name = "Changed"  # type: ignore[misc]
