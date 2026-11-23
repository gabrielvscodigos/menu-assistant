"""Command-line entry point: `menu-ask "your question"` (or `python -m menu_assistant.rag`)."""

import argparse
import sys
from collections.abc import Callable, Sequence

from pydantic import TypeAdapter, ValidationError

from menu_assistant.config import Settings
from menu_assistant.console import use_utf8_output
from menu_assistant.llm import ChatMessage, LLMError
from menu_assistant.llm.factory import llm_client_from_settings
from menu_assistant.models import Allergen, Course, DietaryFlag
from menu_assistant.rag.answer import Answer, AnswerService
from menu_assistant.rag.prompt import format_restrictions
from menu_assistant.rag.restrictions import Restrictions, ingredient_terms
from menu_assistant.retrieval.factory import retriever_from_settings
from menu_assistant.retrieval.ingredients import IngredientTerm
from menu_assistant.retrieval.vector_store import IndexNotReadyError

_INGREDIENT_TERM: TypeAdapter[str] = TypeAdapter(IngredientTerm)


def ingredient_term(value: str) -> str:
    """argparse type: a valid `IngredientTerm`, so bad input is a usage error, not a crash."""
    try:
        return _INGREDIENT_TERM.validate_python(value)
    except ValidationError as error:
        raise argparse.ArgumentTypeError("expected 2 to 40 characters") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="menu-ask",
        description="Ask for dish suggestions grounded in the indexed menu.",
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="what you feel like eating, in any language (optional with --chat)",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="keep asking follow-up questions; an empty line or 'exit' ends the chat",
    )
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
        "--without",
        action="append",
        default=[],
        type=ingredient_term,
        metavar="INGREDIENT",
        help="ingredient to avoid; repeatable (e.g. --without onion --without cebola)",
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


EXIT_WORDS = frozenset({"exit", "quit", "sair", "salir"})


def chat(
    service: AnswerService,
    explicit: Restrictions,
    course: Course | None,
    first_question: str | None = None,
    read: Callable[[str], str] = input,
) -> None:
    """Answer questions until an empty line, an exit word, or end of input.

    Each answer sees the earlier turns, so restrictions stated once keep applying.
    """
    history: list[ChatMessage] = []
    question = first_question
    while True:
        if question is None:
            try:
                question = read("> ").strip()
            except EOFError:
                return
            if not question or question.casefold() in EXIT_WORDS:
                return
        answer = service.answer(question, explicit, course, history)
        print(format_answer(answer), end="\n\n")
        history += [
            ChatMessage(role="user", content=question),
            ChatMessage(role="assistant", content=answer.text),
        ]
        question = None


def main(argv: Sequence[str] | None = None) -> int:
    use_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.question and not args.chat:
        parser.error("a question is required unless --chat is given")
    settings = Settings()
    explicit = Restrictions(
        exclude_allergens=frozenset(Allergen(a) for a in args.exclude),
        require_flags=frozenset(DietaryFlag(f) for f in args.diet),
        exclude_ingredients=ingredient_terms(args.without),
    )

    try:
        llm = llm_client_from_settings(settings)
        # Fail fast: checking the LLM takes milliseconds, loading the embedding model
        # takes seconds.
        llm.check()
        service = AnswerService(retriever_from_settings(settings), llm)
        course = Course(args.course) if args.course else None
        if args.chat:
            chat(service, explicit, course, args.question)
        else:
            print(format_answer(service.answer(args.question, explicit, course)))
    except (IndexNotReadyError, LLMError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
