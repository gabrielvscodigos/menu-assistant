"""Grounded answer generation: retrieve, prompt, then verify the LLM's output in code."""

import logging
import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from menu_assistant.llm import ChatMessage, LLMClient
from menu_assistant.models import Dish
from menu_assistant.rag.prompt import SYSTEM_PROMPT, build_user_message
from menu_assistant.rag.restrictions import (
    Restrictions,
    detect_restrictions,
    mentions_dietary_topic,
)
from menu_assistant.retrieval.search import MenuRetriever, RetrievedDish, SearchRequest

logger = logging.getLogger(__name__)

SAFETY_NOTICE = (
    "Allergen and dietary information comes from the menu and may be incomplete. "
    "Please confirm with the restaurant staff before ordering."
)
NO_MATCH_TEXT = (
    "Sorry, no dish on this menu matches your request and restrictions. "
    "You may want to ask the staff about possible adjustments."
)

# Anything in square brackets on one line: a dish id, or a dish name small models
# sometimes write instead ("[Mango Sticky Rice]").
_BRACKETED = re.compile(r"\s?\[([^\[\]\n]{1,80})\]")
_ID_LIKE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class Answer(BaseModel):
    """A reply plus everything needed to show and audit where it came from."""

    model_config = ConfigDict(frozen=True)

    question: str
    text: str
    cited_dish_ids: list[str]
    retrieved: list[RetrievedDish]
    restrictions: Restrictions
    notice: str | None

    @property
    def cited_dishes(self) -> list[RetrievedDish]:
        by_id = {item.dish.id: item for item in self.retrieved}
        return [by_id[dish_id] for dish_id in self.cited_dish_ids]


def verify_citations(text: str, retrieved: Sequence[Dish]) -> tuple[str, list[str]]:
    """Check every bracketed citation against the dishes that were actually retrieved.

    - `[id]` of a retrieved dish is kept.
    - `[Dish Name]` of a retrieved dish is rewritten to its `[id]`.
    - An id-like `[something]` that was not retrieved is removed, so the answer never
      cites a dish the filters excluded or that does not exist.
    - Any other bracketed text is left as is.

    Returns the cleaned text and the cited ids in order of first appearance.
    """
    ids = {dish.id for dish in retrieved}
    ids_by_name = {dish.name.casefold(): dish.id for dish in retrieved}
    cited: list[str] = []

    def check(match: re.Match[str]) -> str:
        content = match.group(1).strip()
        dish_id = content if content in ids else ids_by_name.get(content.casefold())
        if dish_id is None:
            if _ID_LIKE.match(content):
                logger.warning("removed citation of a dish that was not retrieved: %s", content)
                return ""
            return match.group(0)
        if dish_id not in cited:
            cited.append(dish_id)
        return f"{match.group(0)[: -len(match.group(0).lstrip())]}[{dish_id}]"

    return _BRACKETED.sub(check, text), cited


class AnswerService:
    """Answers menu questions using only retrieved dishes, with code-enforced safety."""

    def __init__(self, retriever: MenuRetriever, llm: LLMClient, k: int = 5) -> None:
        self._retriever = retriever
        self._llm = llm
        self._k = k

    def answer(self, question: str, explicit: Restrictions | None = None) -> Answer:
        restrictions = (explicit or Restrictions()).merge(detect_restrictions(question))
        retrieved = self._retriever.search(
            SearchRequest(
                query=question,
                exclude_allergens=restrictions.exclude_allergens,
                require_flags=restrictions.require_flags,
                k=self._k,
            )
        )
        needs_notice = bool(restrictions) or mentions_dietary_topic(question)
        notice = SAFETY_NOTICE if needs_notice else None

        if not retrieved:
            # Nothing passed the filters: answer deterministically, without the LLM.
            return Answer(
                question=question,
                text=NO_MATCH_TEXT,
                cited_dish_ids=[],
                retrieved=[],
                restrictions=restrictions,
                notice=notice,
            )

        raw = self._llm.generate(
            SYSTEM_PROMPT,
            [
                ChatMessage(
                    role="user", content=build_user_message(question, retrieved, restrictions)
                )
            ],
        )
        text, cited = verify_citations(raw, [item.dish for item in retrieved])
        return Answer(
            question=question,
            text=text,
            cited_dish_ids=cited,
            retrieved=retrieved,
            restrictions=restrictions,
            notice=notice,
        )
