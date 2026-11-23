"""Tests for loading menu files, including the bundled sample menu."""

import json
from pathlib import Path

import pytest

from menu_assistant.ingest import MenuLoadError, load_menu
from menu_assistant.models import Allergen, Course, DietaryFlag


def write_menu(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "menu.json"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_valid_menu(tmp_path: Path) -> None:
    content = json.dumps(
        {
            "restaurant": "Test Kitchen",
            "dishes": [
                {
                    "id": "plain-rice",
                    "name": "Plain Rice",
                    "course": "side",
                    "description": "Steamed rice.",
                    "ingredients": ["rice"],
                    "preparation": "Steamed.",
                    "price": {"amount": "3.00", "currency": "USD"},
                }
            ],
        }
    )

    menu = load_menu(write_menu(tmp_path, content))

    assert menu.restaurant == "Test Kitchen"
    assert [dish.id for dish in menu.dishes] == ["plain-rice"]


def test_missing_file_raises_menu_load_error(tmp_path: Path) -> None:
    with pytest.raises(MenuLoadError, match="cannot read menu file"):
        load_menu(tmp_path / "missing.json")


def test_malformed_json_raises_menu_load_error(tmp_path: Path) -> None:
    with pytest.raises(MenuLoadError, match="invalid menu file"):
        load_menu(write_menu(tmp_path, "{not json"))


def test_schema_violation_names_the_bad_field(tmp_path: Path) -> None:
    content = json.dumps({"restaurant": "Test", "dishes": [{"id": "x"}]})

    with pytest.raises(MenuLoadError, match="ingredients"):
        load_menu(write_menu(tmp_path, content))


def test_sample_menu_is_valid_and_varied(sample_menu_path: Path) -> None:
    menu = load_menu(sample_menu_path)
    dishes = menu.dishes

    assert len(dishes) >= 20
    assert {dish.course for dish in dishes} == set(Course)
    assert any(DietaryFlag.VEGAN in dish.dietary_flags for dish in dishes)
    assert any(DietaryFlag.HALAL in dish.dietary_flags for dish in dishes)
    assert any(not dish.allergens for dish in dishes)
    assert sum("spicy" in dish.tags for dish in dishes) >= 5
    covered_allergens = set().union(*(dish.allergens for dish in dishes))
    assert covered_allergens >= {Allergen.GLUTEN, Allergen.PEANUTS, Allergen.CRUSTACEANS}
