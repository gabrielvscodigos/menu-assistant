"""Command-line entry point: `python -m menu_assistant.eval`.

Evaluates retrieval against the index built by `python -m menu_assistant.ingest`.
Exits with status 1 on labeling errors, a missing index, or any filter violation.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from menu_assistant.config import Settings
from menu_assistant.eval.dataset import find_labeling_errors, load_dataset
from menu_assistant.eval.report import format_report
from menu_assistant.eval.runner import evaluate
from menu_assistant.ingest.loader import load_menu
from menu_assistant.retrieval.factory import retriever_from_settings
from menu_assistant.retrieval.search import MAX_RESULTS
from menu_assistant.retrieval.vector_store import IndexNotReadyError

DEFAULT_DATASET = Path("data/eval/retrieval_queries.json")
DEFAULT_MENU = Path("data/menu.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m menu_assistant.eval",
        description="Measure retrieval quality (recall@k, MRR, filter violations).",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--menu", type=Path, default=DEFAULT_MENU, help="menu the labels refer to")
    parser.add_argument("--k", type=int, default=5, choices=range(1, MAX_RESULTS + 1), metavar="K")
    parser.add_argument("--cases", action="store_true", help="also print every case")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()

    dataset = load_dataset(args.dataset)
    errors = find_labeling_errors(dataset, load_menu(args.menu))
    if errors:
        print("error: invalid labels:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1

    try:
        retriever = retriever_from_settings(settings)
    except IndexNotReadyError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    report = evaluate(retriever, dataset, args.k)

    print(f"Embedding model: {settings.embedding_model} | tag boost: {settings.tag_boost}")
    print(format_report(report, show_cases=args.cases))
    return 1 if report.summary().violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
