"""Tests for deterministic course detection in English, Portuguese, and Spanish."""

import pytest

from menu_assistant.models import Course
from menu_assistant.rag.course import detect_course


@pytest.mark.parametrize(
    ("question", "course"),
    [
        ("a vegan dessert?", Course.DESSERT),
        ("any desserts without nuts?", Course.DESSERT),
        ("quero uma sobremesa sem glúten", Course.DESSERT),
        ("¿qué postre me recomiendas?", Course.DESSERT),
        ("a light starter to share", Course.STARTER),
        ("what appetizers do you have?", Course.STARTER),
        ("uma entrada leve", Course.STARTER),
        ("algo para petiscar? um petisco", Course.STARTER),
        ("a filling main course", Course.MAIN),
        ("which mains are spicy?", Course.MAIN),
        ("um prato principal vegano", Course.MAIN),
        ("un plato principal picante", Course.MAIN),
        ("a side dish for my curry", Course.SIDE),
        ("um acompanhamento", Course.SIDE),
        ("una guarnición", Course.SIDE),
    ],
)
def test_detects_the_requested_course(question: str, course: Course) -> None:
    assert detect_course(question) == course


@pytest.mark.parametrize(
    "question",
    [
        "spicy ramen",
        "something sweet",  # vague: left to semantic search
        "what's the main ingredient of the curry?",
        "sauce on the side please",
        "no dessert, just something spicy",
        "not a starter, something filling",
        "sem sobremesa, algo picante",
        "a starter and a dessert",  # several courses: no single filter
        "",
    ],
)
def test_returns_none_when_no_single_course_is_requested(question: str) -> None:
    assert detect_course(question) is None


def test_course_word_inside_another_word_is_ignored() -> None:
    assert detect_course("I like sideways glances and remains") is None
