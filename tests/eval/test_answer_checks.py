"""Tests for the rule-based answer checks and the answer dataset."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from menu_assistant.eval.answer_checks import (
    acknowledges_unavailable,
    check_answer,
    invalid_citations,
    leaked_dishes,
)
from menu_assistant.eval.answer_dataset import (
    AnswerCase,
    AnswerDataset,
    find_answer_labeling_errors,
    load_answer_dataset,
)
from menu_assistant.models import Course, Dish, Menu
from menu_assistant.rag.answer import NO_MATCH_TEXT, SAFETY_NOTICE, Answer
from menu_assistant.rag.restrictions import Restrictions
from menu_assistant.retrieval.search import RetrievedDish

DATASET_PATH = Path(__file__).parents[2] / "data" / "eval" / "answer_questions.json"


def dish(menu: Menu, dish_id: str) -> Dish:
    return next(d for d in menu.dishes if d.id == dish_id)


def make_answer(menu: Menu, text: str, retrieved: list[str], cited: list[str]) -> Answer:
    return Answer(
        question="q",
        text=text,
        cited_dish_ids=cited,
        retrieved=[
            RetrievedDish(dish=dish(menu, dish_id), similarity=0.5, score=0.5)
            for dish_id in retrieved
        ],
        restrictions=Restrictions(),
        notice=None,
    )


def case(**overrides: object) -> AnswerCase:
    fields: dict[str, object] = {
        "id": "c",
        "category": "preference",
        "question": "spicy noodles?",
        "relevant": ["dan-dan-noodles"],
        "expect_notice": False,
    }
    return AnswerCase.model_validate(fields | overrides)


# --- individual checks -----------------------------------------------------------


def test_invalid_citations_lists_ids_the_model_was_not_given() -> None:
    raw = "Try [edamame], [made-up-dish] or [tiramisu]. [edamame] again."

    assert invalid_citations(raw, {"edamame"}) == ["made-up-dish", "tiramisu"]


def test_leaked_dishes_finds_unretrieved_menu_dishes_by_name(sample_menu: Menu) -> None:
    text = "We have Edamame, and the Tiramisu is great too."

    leaked = leaked_dishes(text, "light starter?", sample_menu.dishes, {"edamame"})

    assert leaked == ["tiramisu"]


def test_leaked_dishes_ignores_dishes_the_guest_named(sample_menu: Menu) -> None:
    text = "The Tiramisu is not vegan."

    assert leaked_dishes(text, "is the tiramisu vegan?", sample_menu.dishes, set()) == []


@pytest.mark.parametrize(
    "text",
    [
        "Sorry, lasagna is not on the menu.",
        "Infelizmente não temos feijoada.",
        "Lo siento, no tenemos sushi.",
        "The menu doesn't include prices.",
        NO_MATCH_TEXT,
    ],
)
def test_acknowledges_unavailable(text: str) -> None:
    assert acknowledges_unavailable(text)


def test_recommending_without_saying_unavailable_is_not_an_acknowledgement() -> None:
    assert not acknowledges_unavailable("Try our Spaghetti Carbonara [spaghetti-carbonara]!")


# --- check_answer ----------------------------------------------------------------


def test_good_answer_passes_every_check(sample_menu: Menu) -> None:
    answer = make_answer(
        sample_menu, "Try [dan-dan-noodles].", ["dan-dan-noodles"], ["dan-dan-noodles"]
    )

    checks = check_answer(case(), answer, "Try [dan-dan-noodles].", sample_menu.dishes)

    assert checks.passed
    assert checks.unavailable_acknowledged is None


def test_answer_citing_no_relevant_dish_fails(sample_menu: Menu) -> None:
    answer = make_answer(sample_menu, "Try [edamame].", ["edamame"], ["edamame"])

    checks = check_answer(case(), answer, "Try [edamame].", sample_menu.dishes)

    assert checks.cites_dish is True
    assert checks.relevant_cited is False
    assert not checks.passed


def test_removed_list_items_fail_the_answer(sample_menu: Menu) -> None:
    answer = make_answer(
        sample_menu, "1. [dan-dan-noodles]", ["dan-dan-noodles"], ["dan-dan-noodles"]
    ).model_copy(update={"removed_items": ["2. Coconut Ice Cream"]})

    checks = check_answer(case(), answer, "1. [dan-dan-noodles]", sample_menu.dishes)

    assert checks.uncited_items == ["2. Coconut Ice Cream"]
    assert not checks.passed


def test_wrong_notice_and_too_many_citations_fail(sample_menu: Menu) -> None:
    ids = ["edamame", "pork-gyoza", "caesar-salad", "dan-dan-noodles"]
    answer = make_answer(sample_menu, "Many.", ids, ids)

    checks = check_answer(case(expect_notice=True), answer, "Many.", sample_menu.dishes)

    assert not checks.within_limit
    assert not checks.notice_correct


def test_off_menu_case_checks_acknowledgement_not_citations(sample_menu: Menu) -> None:
    answer = make_answer(sample_menu, "We have pizza instead!", ["margherita-pizza"], [])
    off_menu = case(category="off_menu", relevant=[], expect_unavailable=True)

    checks = check_answer(off_menu, answer, "We have pizza instead!", sample_menu.dishes)

    assert checks.cites_dish is None
    assert checks.relevant_cited is None
    assert checks.unavailable_acknowledged is False


def test_deterministic_no_match_reply_passes_off_menu_case(sample_menu: Menu) -> None:
    answer = make_answer(sample_menu, NO_MATCH_TEXT, [], []).model_copy(
        update={"notice": SAFETY_NOTICE}
    )
    off_menu = case(category="off_menu", relevant=[], expect_notice=True, expect_unavailable=True)

    assert check_answer(off_menu, answer, None, sample_menu.dishes).passed


# --- dataset ---------------------------------------------------------------------


def test_bundled_answer_dataset_is_consistent_with_the_menu(sample_menu: Menu) -> None:
    dataset = load_answer_dataset(DATASET_PATH)

    assert find_answer_labeling_errors(dataset, sample_menu) == []
    assert {c.category for c in dataset.cases} == {
        "preference",
        "restricted",
        "multilingual",
        "off_menu",
    }


def test_labeling_errors_use_detected_filters(sample_menu: Menu) -> None:
    # Tiramisu contains gluten, and "sem glúten" is detected from the question.
    dataset = AnswerDataset(
        cases=[case(question="sobremesa sem glúten", relevant=["tiramisu", "nope"])]
    )

    assert find_answer_labeling_errors(dataset, sample_menu) == [
        "c: relevant dish 'nope' is not on the menu",
        "c: relevant dish 'tiramisu' breaks the case filters",
    ]


def test_effective_request_prefers_the_explicit_course() -> None:
    request = case(question="a dessert", course="starter").effective_request()

    assert request.course == Course.STARTER


def test_duplicate_answer_case_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate case ids: c"):
        AnswerDataset(cases=[case(), case()])
