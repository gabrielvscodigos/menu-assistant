"""Plain-text rendering of an evaluation report."""

from typing import get_args

from menu_assistant.eval.dataset import Category
from menu_assistant.eval.runner import EvalReport, Summary


def _summary_row(label: str, summary: Summary) -> str:
    return (
        f"{label:<14} {summary.cases:>5} {summary.recall:>10.3f} "
        f"{summary.mrr:>7.3f} {summary.violations:>11}"
    )


def format_report(report: EvalReport, show_cases: bool = False) -> str:
    """Render overall and per-category scores, optionally followed by every case."""
    header = f"{'group':<14} {'cases':>5} {f'recall@{report.k}':>10} {'MRR':>7} {'violations':>11}"
    lines = [header, "-" * len(header)]
    for category in get_args(Category):
        lines.append(_summary_row(category, report.summary(category)))
    lines.append("-" * len(header))
    lines.append(_summary_row("overall", report.summary()))

    if show_cases:
        lines.append("")
        for result in report.results:
            marks = [
                f"{dish_id}*" if dish_id in result.case.relevant else dish_id
                for dish_id in result.retrieved_ids
            ]
            lines.append(
                f"[{result.recall:.2f} | RR {result.reciprocal_rank:.2f}] "
                f"{result.case.id}: {result.case.query!r}"
            )
            lines.append(f"    got:      {', '.join(marks) or '(nothing)'}")
            lines.append(f"    expected: {', '.join(sorted(result.case.relevant))}")
        lines.append("")
        lines.append("* = relevant")

    return "\n".join(lines)
