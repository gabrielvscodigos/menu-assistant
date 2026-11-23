"""Tests for the `ask` command-line entry point."""

from collections.abc import Sequence
from pathlib import Path

import pytest

import menu_assistant.rag.__main__ as cli
from menu_assistant.ingest import load_menu
from menu_assistant.llm import ChatMessage, LLMError
from menu_assistant.models import Allergen, Course, DietaryFlag, Dish
from menu_assistant.rag.__main__ import format_answer, main
from menu_assistant.rag.answer import SAFETY_NOTICES, Answer
from menu_assistant.rag.language import Language
from menu_assistant.rag.restrictions import Restrictions
from menu_assistant.retrieval.search import RetrievedDish


class ReadyLLM:
    def __init__(self, check_error: str | None = None) -> None:
        self.check_error = check_error

    def generate(self, system: str, messages: Sequence[ChatMessage]) -> str:
        raise AssertionError("not expected to be called")

    def check(self) -> None:
        if self.check_error:
            raise LLMError(self.check_error)


def use_llm(monkeypatch: pytest.MonkeyPatch, llm: ReadyLLM) -> None:
    monkeypatch.setattr(cli, "llm_client_from_settings", lambda settings: llm)


def test_missing_index_exits_with_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_llm(monkeypatch, ReadyLLM())
    monkeypatch.setenv("MENU_ASSISTANT_CHROMA_PATH", str(tmp_path / "empty-index"))

    assert main(["what is good?"]) == 1
    assert "is empty" in capsys.readouterr().err


def test_unavailable_llm_fails_before_loading_the_index(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def must_not_load(settings: object) -> None:
        raise AssertionError("index and embedding model should not be loaded")

    use_llm(monkeypatch, ReadyLLM(check_error="cannot reach Ollama; is it running?"))
    monkeypatch.setattr(cli, "retriever_from_settings", must_not_load)

    assert main(["what is good?"]) == 1
    assert "cannot reach Ollama" in capsys.readouterr().err


def test_unknown_course_option_is_rejected() -> None:
    with pytest.raises(SystemExit):
        main(["q", "--course", "brunch"])


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
        course=Course.STARTER,
        notice=SAFETY_NOTICES[Language.EN],
    )

    output = format_answer(answer)

    assert "Sources:\n  - Salted Edamame [edamame]" in output
    assert "Restrictions applied: excludes milk; must be vegan\nCourse: starter" in output
    assert output.endswith(f"Note: {SAFETY_NOTICES[Language.EN]}")


@pytest.fixture
def sample_menu_dish(sample_menu_path: Path) -> Dish:
    return next(d for d in load_menu(sample_menu_path).dishes if d.id == "edamame")
