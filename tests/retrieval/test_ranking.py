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
