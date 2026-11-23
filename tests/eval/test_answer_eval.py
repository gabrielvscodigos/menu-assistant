"""Tests for the answer-quality runner, report, and CLI, with a scripted LLM."""

from collections.abc import Sequence
from pathlib import Path

import pytest
from chromadb.api.models.Collection import Collection

from menu_assistant.eval.answer_dataset import AnswerCase, AnswerDataset
from menu_assistant.eval.answers import (
    AnswerReport,
    evaluate_answers,
    format_answer_report,
    main,
)
from menu_assistant.ingest.indexer import index_menu
from menu_assistant.llm import ChatMessage, LLMClient
from menu_assistant.models import Menu
from menu_assistant.rag.answer import AnswerService
from menu_assistant.retrieval.embeddings import Embedder
from menu_assistant.retrieval.search import MenuRetriever


class ScriptedLLM:
    """Replies with a fixed text and counts calls."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def generate(self, system: str, messages: Sequence[ChatMessage]) -> str:
        self.calls += 1
        return self.reply

    def check(self) -> None:
        pass


DATASET = AnswerDataset(
    cases=[
        AnswerCase(
            id="vegan-dessert",
            category="restricted",
            question="a vegan dessert?",
            relevant=frozenset({"mango-sticky-rice"}),
            expect_notice=True,
        ),
        AnswerCase(
            id="vegan-halal",
            category="off_menu",
            question="a vegan halal dish",
            expect_notice=True,
            expect_unavailable=True,
        ),
        AnswerCase(
            id="tacos",
            category="preference",
            question="what tacos do you have?",
            relevant=frozenset({"fish-tacos", "beef-birria-tacos"}),
            expect_notice=False,
        ),
    ]
)


@pytest.fixture
def report(
    sample_menu: Menu, collection: Collection, fake_embedder: Embedder
) -> tuple[AnswerReport, ScriptedLLM]:
    index_menu(sample_menu, collection, fake_embedder)
    retriever = MenuRetriever(collection, fake_embedder)

    def service_for(llm: LLMClient) -> AnswerService:
        return AnswerService(retriever, llm)

    llm = ScriptedLLM("Try Mango Sticky Rice [mango-sticky-rice] or [ghost-dish].")
    results = evaluate_answers(service_for, llm, DATASET, sample_menu.dishes)
    return AnswerReport(model="scripted", results=results), llm


def test_runner_checks_raw_output_and_skips_llm_on_no_match(
    report: tuple[AnswerReport, ScriptedLLM],
) -> None:
    answer_report, llm = report
    by_id = {r.case.id: r for r in answer_report.results}

    assert llm.calls == 2  # the vegan+halal case is answered without the LLM
    assert by_id["vegan-halal"].llm_called is False
    assert by_id["vegan-halal"].checks.passed
    dessert = by_id["vegan-dessert"]
    assert dessert.cited_ids == ["mango-sticky-rice"]
    assert dessert.checks.invalid_citations == ["ghost-dish"]
    assert not dessert.checks.passed


def test_summary_rates_only_count_applicable_cases(
    report: tuple[AnswerReport, ScriptedLLM],
) -> None:
    summary = report[0].summary()

    assert summary.cases == 3
    assert summary.notice_correct == 1.0
    assert summary.unavailable_acknowledged == 1.0  # one applicable case
    assert summary.grounded_citations == pytest.approx(1 / 3)
    assert report[0].summary("off_menu").relevant_cited is None


def test_report_lists_failures_with_reasons(report: tuple[AnswerReport, ScriptedLLM]) -> None:
    text = format_answer_report(report[0])

    assert "LLM model: scripted" in text
    assert "[FAIL] vegan-dessert" in text
    assert "invalid citations ['ghost-dish']" in text
    assert "[PASS]" not in text
    assert "[PASS] vegan-halal" in format_answer_report(report[0], show_cases=True)


def test_cli_exits_with_error_on_empty_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MENU_ASSISTANT_CHROMA_PATH", str(tmp_path / "empty-index"))

    assert main([]) == 1
    assert "is empty" in capsys.readouterr().err
