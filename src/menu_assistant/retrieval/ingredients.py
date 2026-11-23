"""Deterministic matching of disliked ingredients against a dish's ingredient list.

A term matches an ingredient when it appears as whole words, in singular or plural:
"onion" matches "white onion" and "sumac onions", "chili" matches "ancho chilies", but
"pea" does not match "chickpeas". Matching is deliberately broad within those words
("rice" also matches "rice vinegar"): excluding one dish too many is better than serving
a guest the ingredient they asked to avoid.
"""

import re
import unicodedata
from collections.abc import Iterable
from functools import cache
from typing import Annotated

from pydantic import StringConstraints

from menu_assistant.models import Dish

# A user-supplied ingredient term, e.g. "onion" or "fish sauce".
IngredientTerm = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=2, max_length=40)
]


def fold(text: str) -> str:
    """Lowercase and strip accents, so "Jalapeño" and "jalapeno" compare equal."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _word_forms(word: str) -> set[str]:
    """Singular and plural spellings of an English word ("chili" <-> "chilies")."""
    bases = {word}
    if word.endswith("ies"):
        bases.add(word[:-3] + "y")
    if word.endswith("es"):
        bases.add(word[:-2])
    if word.endswith("s") and not word.endswith("ss"):
        bases.add(word[:-1])
    forms = set(bases)
    for base in bases:
        forms |= {base + "s", base + "es"}
        if base.endswith("y"):
            forms.add(base[:-1] + "ies")
    return forms


@cache
def _term_pattern(term: str) -> re.Pattern[str]:
    *head, last = fold(term).split()
    prefix = "".join(re.escape(word) + r"\s+" for word in head)
    forms = "|".join(sorted(map(re.escape, _word_forms(last)), key=len, reverse=True))
    return re.compile(rf"\b{prefix}(?:{forms})\b")


def disliked_ingredients(dish: Dish, terms: Iterable[str]) -> set[str]:
    """Return the terms that appear in any of the dish's ingredients."""
    ingredients = [fold(ingredient) for ingredient in dish.ingredients]
    return {
        term
        for term in terms
        if any(_term_pattern(term).search(ingredient) for ingredient in ingredients)
    }
