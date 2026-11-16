"""Command-line entry point: `python -m menu_assistant.rag "your question"`."""

import argparse
import sys
from collections.abc import Sequence

from menu_assistant.config import Settings
from menu_assistant.llm import LLMError
from menu_assistant.llm.factory import llm_client_from_settings
from menu_assistant.models import Allergen, Course, DietaryFlag
from menu_assistant.rag.answer import Answer, AnswerService
from menu_assistant.rag.prompt import format_restrictions
from menu_assistant.rag.restrictions import Restrictions
from menu_assistant.retrieval.factory import retriever_from_settings
from menu_assistant.retrieval.vector_store import IndexNotReadyError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m menu_assistant.rag",
        description="Ask for dish suggestions grounded in the indexed menu.",
    )
    parser.add_argument("question", help="what you feel like eating, in any language")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        choices=[a.value for a in Allergen],
        metavar="ALLERGEN",
        help="allergen to avoid; repeatable (e.g. --exclude peanuts --exclude sesame)",
    )
    parser.add_argument(
        "--diet",
        action="append",
        default=[],
        choices=[f.value for f in DietaryFlag],
        metavar="FLAG",
        help="required dietary flag; repeatable (e.g. --diet vegan)",
    )
    parser.add_argument(
        "--course",
        choices=[c.value for c in Course],
        help="only suggest dishes of this course (otherwise detected from the question)",
    )
    return parser


def format_answer(answer: Answer) -> str:
    lines = [answer.text, ""]
    if answer.cited_dishes:
        lines.append("Sources:")
        lines += [f"  - {item.dish.name} [{item.dish.id}]" for item in answer.cited_dishes]
    elif answer.retrieved:
        lines.append("Sources: the model cited no dish. Dishes it was given:")
        lines += [f"  - {item.dish.name} [{item.dish.id}]" for item in answer.retrieved]
    lines.append(f"Restrictions applied: {format_restrictions(answer.restrictions)}")
    if answer.course:
        lines.append(f"Course: {answer.course}")
    if answer.notice:
        lines += ["", f"Note: {answer.notice}"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    explicit = Restrictions(
        exclude_allergens=frozenset(Allergen(a) for a in args.exclude),
        require_flags=frozenset(DietaryFlag(f) for f in args.diet),
    )

    try:
        service = AnswerService(
            retriever_from_settings(settings), llm_client_from_settings(settings)
        )
        course = Course(args.course) if args.course else None
        answer = service.answer(args.question, explicit, course)
    except (IndexNotReadyError, LLMError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(format_answer(answer))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
