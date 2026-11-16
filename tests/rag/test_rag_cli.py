"""Tests for the `ask` command-line entry point."""

from pathlib import Path

import pytest

from menu_assistant.ingest import load_menu
from menu_assistant.models import Allergen, DietaryFlag, Dish
from menu_assistant.rag.__main__ import format_answer, main
from menu_assistant.rag.answer import SAFETY_NOTICE, Answer
from menu_assistant.rag.restrictions import Restrictions
from menu_assistant.retrieval.search import RetrievedDish


def test_missing_index_exits_with_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MENU_ASSISTANT_CHROMA_PATH", str(tmp_path / "empty-index"))

    assert main(["what is good?"]) == 1
    assert "is empty" in capsys.readouterr().err


def test_unknown_allergen_option_is_rejected() -> None:
    with pytest.raises(SystemExit):
        main(["q", "--exclude", "glutten"])


def test_format_answer_shows_sources_restrictions_and_notice(sample_menu_dish: Dish) -> None:
    item = RetrievedDish(dish=sample_menu_dish, similarity=0.8, score=0.8)
    answer = Answer(
        question="q",
        text="Try Edamame [edamame].",
        cited_dish_ids=["edamame"],
        retrieved=[item],
        restrictions=Restrictions(
            exclude_allergens=frozenset({Allergen.MILK}),
            require_flags=frozenset({DietaryFlag.VEGAN}),
        ),
        notice=SAFETY_NOTICE,
    )

    output = format_answer(answer)

    assert "Sources:\n  - Salted Edamame [edamame]" in output
    assert "Restrictions applied: excludes milk; must be vegan" in output
    assert output.endswith(f"Note: {SAFETY_NOTICE}")


@pytest.fixture
def sample_menu_dish(sample_menu_path: Path) -> Dish:
    return next(d for d in load_menu(sample_menu_path).dishes if d.id == "edamame")
