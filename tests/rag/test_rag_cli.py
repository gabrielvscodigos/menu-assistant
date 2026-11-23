"""Tests for the `ask` command-line entry point."""

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from chromadb.api.models.Collection import Collection

import menu_assistant.rag.__main__ as cli
from menu_assistant.ingest import load_menu
from menu_assistant.ingest.indexer import index_menu
from menu_assistant.llm import ChatMessage, LLMError
from menu_assistant.models import Allergen, Course, DietaryFlag, Dish, Menu
from menu_assistant.rag.__main__ import format_answer, main
from menu_assistant.rag.answer import SAFETY_NOTICES, Answer, AnswerService
from menu_assistant.rag.language import Language
from menu_assistant.rag.restrictions import Restrictions
from menu_assistant.retrieval.embeddings import Embedder
from menu_assistant.retrieval.search import MenuRetriever, RetrievedDish


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


def test_too_short_ingredient_option_is_rejected() -> None:
    with pytest.raises(SystemExit):
        main(["q", "--without", "x"])


def test_ingredient_option_is_normalized() -> None:
    args = cli.build_parser().parse_args(["q", "--without", " Onion ", "--without", "garlic"])

    assert args.without == ["onion", "garlic"]


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


# --- chat mode -------------------------------------------------------------------


class RecordingLLM(ReadyLLM):
    def __init__(self) -> None:
        super().__init__()
        self.conversations: list[list[ChatMessage]] = []

    def generate(self, system: str, messages: Sequence[ChatMessage]) -> str:
        self.conversations.append(list(messages))
        return "Try Edamame [edamame]."


@pytest.fixture
def chat_service(
    sample_menu: Menu, collection: Collection, fake_embedder: Embedder
) -> tuple[AnswerService, RecordingLLM]:
    index_menu(sample_menu, collection, fake_embedder)
    llm = RecordingLLM()
    return AnswerService(MenuRetriever(collection, fake_embedder), llm), llm


def scripted_input(*lines: str) -> Callable[[str], str]:
    remaining = list(lines)

    def read(prompt: str) -> str:
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    return read


def test_chat_carries_history_and_restrictions_between_questions(
    chat_service: tuple[AnswerService, RecordingLLM], capsys: pytest.CaptureFixture[str]
) -> None:
    service, llm = chat_service

    cli.chat(
        service,
        Restrictions(),
        None,
        "I'm allergic to peanuts",
        read=scripted_input("and a starter?", ""),
    )

    assert len(llm.conversations) == 2
    second = llm.conversations[1]
    assert [turn.role for turn in second] == ["user", "assistant", "user"]
    assert second[0].content == "I'm allergic to peanuts"
    assert "excludes peanuts" in second[-1].content
    assert capsys.readouterr().out.count("Restrictions applied: excludes peanuts") == 2


@pytest.mark.parametrize("ending", ["", "exit", "SAIR"])
def test_chat_ends_on_empty_line_or_exit_word(
    chat_service: tuple[AnswerService, RecordingLLM], ending: str
) -> None:
    service, llm = chat_service

    cli.chat(service, Restrictions(), None, read=scripted_input("hi", ending, "never asked"))

    assert len(llm.conversations) == 1


def test_chat_ends_at_end_of_input(chat_service: tuple[AnswerService, RecordingLLM]) -> None:
    service, llm = chat_service

    cli.chat(service, Restrictions(), None, read=scripted_input())

    assert llm.conversations == []


def test_question_is_required_without_chat() -> None:
    with pytest.raises(SystemExit):
        main([])
