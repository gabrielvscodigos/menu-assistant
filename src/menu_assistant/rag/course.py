"""Deterministic detection of the course a guest asks for ("a vegan dessert").

Like restriction detection, this is pattern matching in code, not the LLM: the course
becomes an exact retrieval filter, so it must be predictable and testable. Only explicit
course words count ("dessert", "sobremesa", "postre"); vague words such as "sweet" are
left to semantic search. If the question names several courses, or negates one ("no
dessert"), no course filter is applied.
"""

import re

from menu_assistant.models import Course
from menu_assistant.rag.restrictions import normalize

# Accent-free, lowercase phrases (English, Portuguese, Spanish) naming each course.
# "entree" is left out on purpose: it means a main in the US and a starter elsewhere.
COURSE_WORDS: dict[Course, tuple[str, ...]] = {
    Course.STARTER: (
        "starter",
        "appetizer",
        "appetiser",
        "entrada",
        "aperitivo",
        "petisco",
        "tira-gosto",
        "tira gosto",
    ),
    Course.MAIN: (
        "mains",  # bare "main" would match "the main ingredient"
        "main course",
        "main dish",
        "prato principal",
        "pratos principais",
        "plato principal",
        "plato fuerte",
    ),
    Course.SIDE: (
        "side dish",
        "side",
        "acompanhamento",
        "guarnicao",
        "acompanamiento",
        "guarnicion",
    ),
    Course.DESSERT: ("dessert", "sobremesa", "postre"),
}

_COURSE_BY_WORD = {word: course for course, words in COURSE_WORDS.items() for word in words}
_COURSE_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, _COURSE_BY_WORD), key=len, reverse=True)) + r")s?\b"
)
# "no dessert", "not a starter", "sem sobremesa", "sin postre" right before the word.
_NEGATION = re.compile(r"\b(?:no|not|without|skip|sem|sin|nao)\s+(?:(?:a|an|um|uma|un|una)\s+)?$")
# "on the side" / "do lado" describe a garnish, not a request for a side dish.
_NOT_A_COURSE = re.compile(r"\b(?:on the|to the|do|al) side$")


def detect_course(question: str) -> Course | None:
    """Return the single course the question asks for, or None if unclear."""
    text = normalize(question)
    found: set[Course] = set()
    for match in _COURSE_PATTERN.finditer(text):
        before = text[: match.start()]
        if _NEGATION.search(before) or _NOT_A_COURSE.search(text[: match.end()]):
            continue
        found.add(_COURSE_BY_WORD[match.group(1)])
    return found.pop() if len(found) == 1 else None
