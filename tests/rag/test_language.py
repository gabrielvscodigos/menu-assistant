"""Tests for deterministic language detection."""

import pytest

from menu_assistant.rag.language import Language, detect_language


@pytest.mark.parametrize(
    "question",
    [
        "I like spicy ramen, what else here would I enjoy?",
        "I'm allergic to peanuts. Any spicy noodles?",
        "Do you have lasagna?",
    ],
)
def test_detects_english(question: str) -> None:
    assert detect_language(question) == Language.EN


@pytest.mark.parametrize(
    "question",
    [
        "gosto de cuscuz, tem algo parecido pra mim?",
        "Tenho alergia a amendoim e gergelim, qual sobremesa posso pedir?",
        "Quero uma sobremesa vegana",
        "Tem sushi?",
        "alguma sugestão apimentada?",  # "ã" alone is enough
    ],
)
def test_detects_portuguese(question: str) -> None:
    assert detect_language(question) == Language.PT


@pytest.mark.parametrize(
    "question",
    [
        "Me gustan los tacos picantes",
        "¿Tienen algo sin gluten?",
        "Quiero un postre de chocolate",
        "unos fideos con piña",
    ],
)
def test_detects_spanish(question: str) -> None:
    assert detect_language(question) == Language.ES


@pytest.mark.parametrize("question", ["", "tacos", "sushi", "fideos picantes"])
def test_unclear_questions_fall_back_to_english(question: str) -> None:
    assert detect_language(question) == Language.EN


def test_accents_and_case_do_not_matter() -> None:
    assert detect_language("VOCÊS TÊM ALGO SEM LACTOSE?") == Language.PT
    assert detect_language("voces tem algo sem lactose?") == Language.PT
