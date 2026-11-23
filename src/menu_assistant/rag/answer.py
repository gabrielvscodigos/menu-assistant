"""Grounded answer generation: retrieve, prompt, then verify the LLM's output in code."""

import logging
import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from menu_assistant.llm import ChatMessage, LLMClient
from menu_assistant.models import Course, Dish
from menu_assistant.rag.conversation import (
    recent_turns,
    restrictions_from_history,
    retrieval_query,
    user_turns,
)
from menu_assistant.rag.course import detect_course
from menu_assistant.rag.language import Language, detect_language
from menu_assistant.rag.prompt import SYSTEM_PROMPT, build_user_message
from menu_assistant.rag.restrictions import (
    Restrictions,
    detect_restrictions,
    mentions_dietary_topic,
)
from menu_assistant.retrieval.search import MenuRetriever, RetrievedDish, SearchRequest

logger = logging.getLogger(__name__)

# Texts written in code, not by the LLM, in every language `detect_language` returns.
SAFETY_NOTICES: dict[Language, str] = {
    Language.EN: (
        "Allergen and dietary information comes from the menu and may be incomplete. "
        "Please confirm with the restaurant staff before ordering."
    ),
    Language.PT: (
        "As informações sobre alérgenos e restrições alimentares vêm do cardápio e podem "
        "estar incompletas. Confirme com a equipe do restaurante antes de pedir."
    ),
    Language.ES: (
        "La información sobre alérgenos y dietas proviene de la carta y puede estar "
        "incompleta. Confirma con el personal del restaurante antes de pedir."
    ),
}
NO_MATCH_TEXTS: dict[Language, str] = {
    Language.EN: (
        "Sorry, no dish on this menu matches your request and restrictions. "
        "You may want to ask the staff about possible adjustments."
    ),
    Language.PT: (
        "Desculpe, nenhum prato deste cardápio atende ao seu pedido e às suas restrições. "
        "Vale perguntar à equipe sobre possíveis adaptações."
    ),
    Language.ES: (
        "Lo siento, ningún plato de esta carta coincide con tu pedido y tus restricciones. "
        "Puedes preguntar al personal por posibles adaptaciones."
    ),
}

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
    course: Course | None = None
    language: Language = Language.EN
    notice: str | None
    removed_items: list[str] = []

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


# A top-level list item: "- x", "* x", "• x", "1. x", "2) x" (indented sub-items excluded).
_LIST_ITEM = re.compile(r"^(?:[-*•]|(\d+)([.)]))\s+")


def enforce_list_citations(text: str, retrieved: Sequence[Dish]) -> tuple[str, list[str]]:
    """Make every top-level list item point at a retrieved dish, or drop it.

    Small models list extra suggestions without a citation ("3. Coconut Ice Cream"),
    which is how invented dishes slip past citation checks. For each list item:
    - with a `[id]` of a retrieved dish: kept;
    - naming a retrieved dish without a citation: kept, and the citation is added;
    - anything else: removed (logged), and numbered items are renumbered.

    Returns the new text and the removed items.
    """
    removed: list[str] = []
    kept: list[str] = []
    for line in text.split("\n"):
        if _LIST_ITEM.match(line) is None or _cites_retrieved(line, retrieved):
            kept.append(line)
            continue
        dish = next((d for d in retrieved if d.name.casefold() in line.casefold()), None)
        if dish is not None:
            kept.append(_add_citation(line, dish))
        else:
            logger.warning("removed list item without a retrieved dish: %s", line.strip())
            removed.append(line.strip())
    return "\n".join(_renumber(kept) if removed else kept), removed


def _cites_retrieved(line: str, retrieved: Sequence[Dish]) -> bool:
    return any(f"[{dish.id}]" in line for dish in retrieved)


def _add_citation(line: str, dish: Dish) -> str:
    start = line.casefold().index(dish.name.casefold())
    end = start + len(dish.name)
    # Keep closing markdown emphasis attached to the name: "**Mango Sticky Rice**".
    while end < len(line) and line[end] == "*":
        end += 1
    return f"{line[:end]} [{dish.id}]{line[end:]}"


def _renumber(lines: list[str]) -> list[str]:
    number = 0
    result = []
    for line in lines:
        match = _LIST_ITEM.match(line)
        if match is not None and match.group(1) is not None:
            number += 1
            line = f"{number}{match.group(2)} {line[match.end() :]}"
        result.append(line)
    return result


def clean_reply(raw: str, retrieved: Sequence[Dish]) -> tuple[str, list[str], list[str]]:
    """Verify citations, then enforce them on list items.

    Returns the cleaned text, the cited ids, and the list items that were removed.
    """
    text, _ = verify_citations(raw, retrieved)
    text, removed = enforce_list_citations(text, retrieved)
    text, cited = verify_citations(text, retrieved)
    return text, cited, removed


class AnswerService:
    """Answers menu questions using only retrieved dishes, with code-enforced safety."""

    def __init__(self, retriever: MenuRetriever, llm: LLMClient, k: int = 5) -> None:
        self._retriever = retriever
        self._llm = llm
        self._k = k

    def check_llm(self) -> None:
        """Raise `LLMError` if the LLM cannot answer right now (see `LLMClient.check`)."""
        self._llm.check()

    def answer(
        self,
        question: str,
        explicit: Restrictions | None = None,
        course: Course | None = None,
        history: Sequence[ChatMessage] = (),
        language: Language | None = None,
        exclude_dishes: frozenset[str] = frozenset(),
    ) -> Answer:
        """Answer `question`, a follow-up to the earlier turns in `history` if any.

        Restrictions from earlier user turns keep applying (see `rag.conversation`). The
        course comes from this question only; an explicit `course` overrides it. An
        explicit `language` (chosen by the guest) overrides the detected one, for the fixed
        texts and for the LLM's reply. `exclude_dishes` are never retrieved (e.g. dishes
        already suggested when the guest asks for other options).
        """
        restrictions = (
            (explicit or Restrictions())
            .merge(restrictions_from_history(history))
            .merge(detect_restrictions(question))
        )
        course = course or detect_course(question)
        retrieved = self._retriever.search(
            SearchRequest(
                query=retrieval_query(question, history),
                exclude_allergens=restrictions.exclude_allergens,
                require_flags=restrictions.require_flags,
                exclude_ingredients=restrictions.exclude_ingredients,
                exclude_dishes=exclude_dishes,
                course=course,
                k=self._k,
            )
        )
        reply_language = language or detect_language(
            question, default=detect_language(" ".join(user_turns(history)))
        )
        # Filters ran on the canonical dish data; from here on, the guest sees the dish in
        # their language (name, ingredients, local price) when the menu has a translation.
        retrieved = [
            item.model_copy(update={"dish": item.dish.localized(reply_language)})
            for item in retrieved
        ]
        needs_notice = bool(restrictions) or mentions_dietary_topic(question)
        notice = SAFETY_NOTICES[reply_language] if needs_notice else None

        if not retrieved:
            # Nothing passed the filters: answer deterministically, without the LLM.
            return Answer(
                question=question,
                text=NO_MATCH_TEXTS[reply_language],
                cited_dish_ids=[],
                retrieved=[],
                restrictions=restrictions,
                course=course,
                language=reply_language,
                notice=notice,
            )

        raw = self._llm.generate(
            SYSTEM_PROMPT,
            [
                *recent_turns(history),
                ChatMessage(
                    role="user",
                    content=build_user_message(question, retrieved, restrictions, course, language),
                ),
            ],
        )
        text, cited, removed = clean_reply(raw, [item.dish for item in retrieved])
        return Answer(
            question=question,
            text=text,
            cited_dish_ids=cited,
            retrieved=retrieved,
            restrictions=restrictions,
            course=course,
            language=reply_language,
            notice=notice,
            removed_items=removed,
        )
