"""Rule-based checks of a generated answer. All functions are pure.

The checks are deterministic on purpose (no LLM judge): they are cheap, reproducible,
and test exactly the rules the product promises. They cannot judge tone or catch every
invented detail; see docs/evaluation.md for what they miss.
"""

import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from menu_assistant.eval.answer_dataset import AnswerCase
from menu_assistant.models import Dish
from menu_assistant.rag.answer import NO_MATCH_TEXTS, Answer
from menu_assistant.rag.restrictions import normalize

MAX_RECOMMENDED = 3

_CITED_ID = re.compile(r"\[([a-z0-9]+(?:-[a-z0-9]+)*)\]")

# Normalized (lowercase, accent-free) phrases that say "we don't have that", EN/PT/ES.
UNAVAILABLE_MARKERS = (
    "not on the menu",
    "not on our menu",
    "isn't on",
    "is not on",
    "don't have",
    "do not have",
    "don't serve",
    "do not serve",
    "doesn't say",
    "does not say",
    "doesn't list",
    "does not list",
    "not listed",
    "doesn't include",
    "does not include",
    "doesn't mention",
    "does not mention",
    "not mentioned",
    "unfortunately",
    "nao temos",
    "nao esta no",
    "nao consta",
    "nao ha",
    "nao servimos",
    "nao tem",
    "nao informa",
    "nao diz",
    "nao inclui",
    "nao menciona",
    "infelizmente",
    "no tenemos",
    "no esta en",
    "no hay",
    "no servimos",
    "no indica",
    "no incluye",
    "no menciona",
    "lamentablemente",
)


class AnswerChecks(BaseModel):
    """Outcome of every check for one case. `None` means the check does not apply."""

    model_config = ConfigDict(frozen=True)

    invalid_citations: list[str]
    leaked_dishes: list[str]
    uncited_items: list[str]
    cites_dish: bool | None
    relevant_cited: bool | None
    within_limit: bool
    notice_correct: bool
    unavailable_acknowledged: bool | None

    @property
    def passed(self) -> bool:
        return (
            not self.invalid_citations
            and not self.leaked_dishes
            and not self.uncited_items
            and self.cites_dish is not False
            and self.relevant_cited is not False
            and self.within_limit
            and self.notice_correct
            and self.unavailable_acknowledged is not False
        )


def invalid_citations(raw_text: str, retrieved_ids: set[str]) -> list[str]:
    """Ids the model cited in its raw output that it was never given."""
    return sorted({cited for cited in _CITED_ID.findall(raw_text) if cited not in retrieved_ids})


def leaked_dishes(
    text: str, question: str, menu: Sequence[Dish], allowed_ids: set[str]
) -> list[str]:
    """Menu dishes named in the answer although retrieval did not give them to the model.

    Dishes the guest named in the question are ignored: echoing them is fine.
    """
    answer = normalize(text)
    asked = normalize(question)
    return sorted(
        dish.id
        for dish in menu
        if dish.id not in allowed_ids
        and normalize(dish.name) in answer
        and normalize(dish.name) not in asked
    )


def acknowledges_unavailable(text: str) -> bool:
    if text in NO_MATCH_TEXTS.values():
        return True
    normalized = normalize(text)
    return any(marker in normalized for marker in UNAVAILABLE_MARKERS)


def check_answer(
    case: AnswerCase, answer: Answer, raw_text: str | None, menu: Sequence[Dish]
) -> AnswerChecks:
    """Run every check. `raw_text` is the LLM output before citation clean-up, if called."""
    retrieved_ids = {item.dish.id for item in answer.retrieved}
    cited = set(answer.cited_dish_ids)
    should_cite = bool(case.relevant) and bool(answer.retrieved)
    return AnswerChecks(
        invalid_citations=invalid_citations(raw_text or "", retrieved_ids),
        leaked_dishes=leaked_dishes(answer.text, case.question, menu, retrieved_ids),
        uncited_items=answer.removed_items,
        cites_dish=bool(cited) if should_cite else None,
        relevant_cited=bool(cited & case.relevant) if should_cite else None,
        within_limit=len(cited) <= MAX_RECOMMENDED,
        notice_correct=(answer.notice is not None) == case.expect_notice,
        unavailable_acknowledged=(
            acknowledges_unavailable(answer.text) if case.expect_unavailable else None
        ),
    )
