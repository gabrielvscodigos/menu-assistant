"""Tests for lexical tag matching."""

import pytest

from menu_assistant.retrieval.ranking import matched_tags

TAGS = ["spicy", "noodles", "middle-eastern", "japanese", "glass"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Spicy noodle soup", {"spicy", "noodles"}),
        ("any middle eastern food?", {"middle-eastern"}),
        ("something from the east", set()),
        ("JAPANESE please", {"japanese"}),
        ("a glass of wine", {"glass"}),
        ("spiciness", set()),
        ("", set()),
    ],
)
def test_matched_tags(query: str, expected: set[str]) -> None:
    assert matched_tags(query, TAGS) == expected


@pytest.mark.parametrize(
    ("query", "tags", "expected"),
    [
        (
            "algo apimentado com macarrão",
            ["spicy", "noodles", "pasta", "soup"],
            {"spicy", "noodles", "pasta"},
        ),
        ("pratos com frango", ["chicken", "beef"], {"chicken"}),
        ("algo frito e crocante", ["fried", "crispy"], {"fried", "crispy"}),
        ("cogumelos", ["mushroom"], {"mushroom"}),
        ("comida chinesa", ["chinese"], {"chinese"}),
        ("Comida Chinês", ["chinese"], {"chinese"}),
        ("comida árabe", ["middle-eastern"], {"middle-eastern"}),
    ],
)
def test_portuguese_aliases_match_english_tags(
    query: str, tags: list[str], expected: set[str]
) -> None:
    assert matched_tags(query, tags) == expected


def test_alias_does_not_match_tags_it_does_not_stand_for() -> None:
    assert matched_tags("pratos com frango", ["pork", "spicy"]) == set()
