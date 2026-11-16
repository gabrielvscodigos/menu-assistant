"""Answer-quality evaluation: `python -m menu_assistant.eval.answers`.

Runs every labeled question through the real `AnswerService` (index + LLM) and checks
each answer with the rules in `answer_checks`. Needs an index and a running Ollama.
Exits with status 1 on labeling errors, setup errors, or a wrong safety notice (the
notice is enforced in code, so any miss is a bug, not model noise).
"""

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import get_args

from pydantic import BaseModel, ConfigDict

from menu_assistant.config import Settings
from menu_assistant.eval.answer_checks import MAX_RECOMMENDED, AnswerChecks, check_answer
from menu_assistant.eval.answer_dataset import (
    AnswerCase,
    AnswerCategory,
    AnswerDataset,
    find_answer_labeling_errors,
    load_answer_dataset,
)
from menu_assistant.eval.metrics import mean
from menu_assistant.ingest.loader import load_menu
from menu_assistant.llm import ChatMessage, LLMClient, LLMError
from menu_assistant.llm.factory import llm_client_from_settings
from menu_assistant.models import Dish
from menu_assistant.rag.answer import AnswerService
from menu_assistant.retrieval.factory import retriever_from_settings
from menu_assistant.retrieval.vector_store import IndexNotReadyError

DEFAULT_DATASET = Path("data/eval/answer_questions.json")
DEFAULT_MENU = Path("data/menu.json")


class RecordingLLM:
    """Wraps an LLM client and keeps its last raw reply, before any clean-up."""

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner
        self.last_reply: str | None = None

    def generate(self, system: str, messages: Sequence[ChatMessage]) -> str:
        self.last_reply = self._inner.generate(system, messages)
        return self.last_reply


class AnswerCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case: AnswerCase
    text: str
    cited_ids: list[str]
    llm_called: bool
    seconds: float
    checks: AnswerChecks


class AnswerSummary(BaseModel):
    """Share of applicable cases passing each check (None if no case applies)."""

    model_config = ConfigDict(frozen=True)

    cases: int
    passed: float
    grounded_citations: float | None
    no_leaked_dishes: float | None
    cites_dish: float | None
    relevant_cited: float | None
    within_limit: float | None
    notice_correct: float | None
    unavailable_acknowledged: float | None
    mean_seconds: float


def _rate(values: Sequence[bool | None]) -> float | None:
    applicable = [value for value in values if value is not None]
    return mean([float(value) for value in applicable]) if applicable else None


class AnswerReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    results: list[AnswerCaseResult]

    def summary(self, category: AnswerCategory | None = None) -> AnswerSummary:
        selected = [r for r in self.results if category is None or r.case.category == category]
        checks = [r.checks for r in selected]
        return AnswerSummary(
            cases=len(selected),
            passed=mean([float(c.passed) for c in checks]),
            grounded_citations=_rate([not c.invalid_citations for c in checks]),
            no_leaked_dishes=_rate([not c.leaked_dishes for c in checks]),
            cites_dish=_rate([c.cites_dish for c in checks]),
            relevant_cited=_rate([c.relevant_cited for c in checks]),
            within_limit=_rate([c.within_limit for c in checks]),
            notice_correct=_rate([c.notice_correct for c in checks]),
            unavailable_acknowledged=_rate([c.unavailable_acknowledged for c in checks]),
            mean_seconds=mean([r.seconds for r in selected]),
        )


def evaluate_answers(
    service_for: Callable[[LLMClient], AnswerService],
    llm: LLMClient,
    dataset: AnswerDataset,
    menu: Sequence[Dish],
) -> list[AnswerCaseResult]:
    """Answer every case and check it. `service_for` builds a service around an LLM."""
    recorder = RecordingLLM(llm)
    service = service_for(recorder)
    results = []
    for case in dataset.cases:
        recorder.last_reply = None
        start = time.perf_counter()
        answer = service.answer(case.question, case.explicit_restrictions, case.course)
        seconds = time.perf_counter() - start
        results.append(
            AnswerCaseResult(
                case=case,
                text=answer.text,
                cited_ids=answer.cited_dish_ids,
                llm_called=recorder.last_reply is not None,
                seconds=seconds,
                checks=check_answer(case, answer, recorder.last_reply, menu),
            )
        )
    return results


class ServiceFactory:
    """Builds the production `AnswerService` around a given LLM client."""

    def __init__(self, settings: Settings) -> None:
        self._retriever = retriever_from_settings(settings)

    def __call__(self, llm: LLMClient) -> AnswerService:
        return AnswerService(self._retriever, llm)


def _percent(value: float | None) -> str:
    return "   n/a" if value is None else f"{value:>6.0%}"


_COLUMNS = (
    ("passed", "pass"),
    ("grounded_citations", "cites"),
    ("no_leaked_dishes", "noleak"),
    ("relevant_cited", "relev"),
    ("within_limit", "<=3"),
    ("notice_correct", "notice"),
    ("unavailable_acknowledged", "unavail"),
)


def format_answer_report(report: AnswerReport, show_cases: bool = False) -> str:
    """Render per-category and overall check rates, optionally every case."""
    header = f"{'group':<13} {'cases':>5} " + " ".join(f"{name:>7}" for _, name in _COLUMNS)
    header += f" {'sec':>6}"
    lines = [f"LLM model: {report.model}", header, "-" * len(header)]

    def row(label: str, summary: AnswerSummary) -> str:
        values = " ".join(f"{_percent(getattr(summary, field)):>7}" for field, _ in _COLUMNS)
        return f"{label:<13} {summary.cases:>5} {values} {summary.mean_seconds:>6.1f}"

    for category in get_args(AnswerCategory):
        lines.append(row(category, report.summary(category)))
    lines += ["-" * len(header), row("overall", report.summary())]
    lines += [
        "",
        "pass: all checks | cites: no invalid citations | noleak: no unretrieved dish named",
        "relev: cites a relevant dish | notice: staff notice iff expected | "
        "unavail: says it is not on the menu",
    ]

    for result in report.results:
        if not show_cases and result.checks.passed:
            continue
        status = "PASS" if result.checks.passed else "FAIL"
        lines += ["", f"[{status}] {result.case.id}: {result.case.question!r}"]
        lines.append(f"    cited: {', '.join(result.cited_ids) or '(none)'}")
        failed = _failed_checks(result.checks)
        if failed:
            lines.append(f"    failed: {'; '.join(failed)}")
        lines.append("    answer: " + result.text.replace("\n", " ")[:300])
    return "\n".join(lines)


def _failed_checks(checks: AnswerChecks) -> list[str]:
    failed = []
    if checks.invalid_citations:
        failed.append(f"invalid citations {checks.invalid_citations}")
    if checks.leaked_dishes:
        failed.append(f"named unretrieved dishes {checks.leaked_dishes}")
    if checks.cites_dish is False:
        failed.append("cites no dish")
    elif checks.relevant_cited is False:
        failed.append("cites no relevant dish")
    if not checks.within_limit:
        failed.append(f"more than {MAX_RECOMMENDED} dishes cited")
    if not checks.notice_correct:
        failed.append("wrong safety notice")
    if checks.unavailable_acknowledged is False:
        failed.append("does not say it is unavailable")
    return failed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m menu_assistant.eval.answers",
        description="Measure answer quality with rule-based checks (needs Ollama running).",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--menu", type=Path, default=DEFAULT_MENU, help="menu the labels refer to")
    parser.add_argument("--cases", action="store_true", help="print every case, not only failures")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()

    dataset = load_answer_dataset(args.dataset)
    menu = load_menu(args.menu)
    errors = find_answer_labeling_errors(dataset, menu)
    if errors:
        print("error: invalid labels:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1

    try:
        results = evaluate_answers(
            ServiceFactory(settings), llm_client_from_settings(settings), dataset, menu.dishes
        )
    except (IndexNotReadyError, LLMError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    report = AnswerReport(model=settings.llm_model, results=results)
    print(format_answer_report(report, show_cases=args.cases))
    return 0 if report.summary().notice_correct == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
