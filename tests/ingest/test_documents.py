"""Tests for turning dishes into indexable text and filterable metadata."""

from menu_assistant.ingest.documents import (
    DISH_JSON_KEY,
    allergen_key,
    diet_key,
    dish_to_document,
    dish_to_metadata,
)
from menu_assistant.models import Allergen, DietaryFlag, Dish, Menu


def get_dish(menu: Menu, dish_id: str) -> Dish:
    return next(dish for dish in menu.dishes if dish.id == dish_id)


def test_document_contains_searchable_fields(sample_menu: Menu) -> None:
    dish = get_dish(sample_menu, "tofu-green-curry")

    document = dish_to_document(dish)

    assert "Green Curry with Tofu (main)" in document
    assert "coconut milk" in document
    assert "spicy" in document
    assert "Dietary: dairy_free, gluten_free, vegan, vegetarian" in document


def test_document_excludes_allergens(sample_menu: Menu) -> None:
    dish = get_dish(sample_menu, "dan-dan-noodles")

    assert "Allergens" not in dish_to_document(dish)


def test_metadata_has_explicit_boolean_for_every_allergen_and_flag(sample_menu: Menu) -> None:
    dish = get_dish(sample_menu, "dan-dan-noodles")

    metadata = dish_to_metadata(dish)

    for allergen in Allergen:
        assert metadata[allergen_key(allergen)] is (allergen in dish.allergens)
    for flag in DietaryFlag:
        assert metadata[diet_key(flag)] is (flag in dish.dietary_flags)
    assert metadata["allergen_peanuts"] is True
    assert metadata["allergen_milk"] is False


def test_metadata_round_trips_the_full_dish(sample_menu: Menu) -> None:
    dish = get_dish(sample_menu, "spicy-miso-ramen")

    stored = dish_to_metadata(dish)[DISH_JSON_KEY]

    assert isinstance(stored, str)
    assert Dish.model_validate_json(stored) == dish
