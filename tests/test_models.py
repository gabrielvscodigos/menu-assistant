"""Tests for the menu domain models and their consistency rules."""

from decimal import Decimal
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
        "price": {"amount": "12.50", "currency": "USD"},
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


def test_price_keeps_exact_decimal_amounts() -> None:
    dish = Dish.model_validate(make_dish_data(price={"amount": "14.50", "currency": "BRL"}))

    assert dish.price.amount == Decimal("14.50")
    assert dish.price.currency == "BRL"


@pytest.mark.parametrize(
    "price",
    [
        {"amount": "0", "currency": "USD"},
        {"amount": "-3.00", "currency": "USD"},
        {"amount": "9.999", "currency": "USD"},
        {"amount": "9.00", "currency": "usd"},
        {"amount": "9.00", "currency": "DOLLAR"},
        {"amount": "9.00"},
    ],
)
def test_invalid_prices_are_rejected(price: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        Dish.model_validate(make_dish_data(price=price))


def test_menu_rejects_mixed_currencies() -> None:
    dishes = [
        make_dish_data(id="a", price={"amount": "5.00", "currency": "USD"}),
        make_dish_data(id="b", price={"amount": "5.00", "currency": "EUR"}),
    ]

    with pytest.raises(ValidationError, match="mixes currencies: EUR, USD"):
        Menu.model_validate({"restaurant": "R", "dishes": dishes})


PT = {
    "name": "Prato de Teste",
    "description": "Um prato para testes.",
    "ingredients": ["arroz"],
    "preparation": "Cozido.",
    "price": {"amount": "39.90", "currency": "BRL"},
}


def test_localized_dish_uses_the_translation_but_keeps_safety_data() -> None:
    dish = Dish.model_validate(
        make_dish_data(allergens=["milk"], dietary_flags=["vegetarian"], translations={"pt": PT})
    )

    localized = dish.localized("pt")

    assert localized.name == "Prato de Teste"
    assert localized.ingredients == ["arroz"]
    assert localized.price.amount == Decimal("39.90")
    assert localized.price.currency == "BRL"
    assert localized.allergens == dish.allergens
    assert localized.dietary_flags == dish.dietary_flags
    assert localized.id == dish.id
    assert localized.translations == {}


def test_dish_without_that_translation_stays_as_is() -> None:
    dish = Dish.model_validate(make_dish_data(translations={"pt": PT}))

    assert dish.localized("es") is dish
    assert dish.localized("en") is dish


@pytest.mark.parametrize("code", ["pt-BR", "PT", "portuguese"])
def test_translation_language_codes_are_two_lowercase_letters(code: str) -> None:
    with pytest.raises(ValidationError):
        Dish.model_validate(make_dish_data(translations={code: PT}))


def test_menu_rejects_mixed_currencies_within_a_translation() -> None:
    usd_pt = {**PT, "price": {"amount": "9.00", "currency": "USD"}}
    dishes = [
        make_dish_data(id="a", translations={"pt": PT}),
        make_dish_data(id="b", translations={"pt": usd_pt}),
    ]

    with pytest.raises(ValidationError, match="in 'pt' translations: BRL, USD"):
        Menu.model_validate({"restaurant": "R", "dishes": dishes})


def test_sample_menu_is_translated_to_portuguese_in_reais(sample_menu: Menu) -> None:
    for dish in sample_menu.dishes:
        translation = dish.translations.get("pt")
        assert translation is not None, f"{dish.id} has no Portuguese translation"
        assert translation.price.currency == "BRL"
