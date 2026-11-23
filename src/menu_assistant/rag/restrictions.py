"""Deterministic detection of allergen, dietary, and ingredient restrictions in a question.

This is plain pattern matching, never the LLM: restrictions decide which dishes may be
recommended, so they must be predictable and testable. Detection is deliberately
conservative (it prefers excluding a dish over missing an allergy), works in English,
Portuguese, and Spanish, and is combined with restrictions the user selects explicitly.
"""

import re
import unicodedata
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from menu_assistant.models import Allergen, DietaryFlag
from menu_assistant.retrieval.ingredients import IngredientTerm


class Restrictions(BaseModel):
    """Hard constraints every recommended dish must satisfy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exclude_allergens: frozenset[Allergen] = frozenset()
    require_flags: frozenset[DietaryFlag] = frozenset()
    exclude_ingredients: frozenset[IngredientTerm] = frozenset()

    def __bool__(self) -> bool:
        return bool(self.exclude_allergens or self.require_flags or self.exclude_ingredients)

    def merge(self, other: "Restrictions") -> "Restrictions":
        return Restrictions(
            exclude_allergens=self.exclude_allergens | other.exclude_allergens,
            require_flags=self.require_flags | other.require_flags,
            exclude_ingredients=self.exclude_ingredients | other.exclude_ingredients,
        )


# Words (accent-free, lowercase) that name an allergen. A word may map to several
# allergens: "nuts" usually means both tree nuts and peanuts, "seafood" all three
# seafood allergens. Plurals are covered by the optional "s"/"es" in the pattern.
ALLERGEN_WORDS: dict[str, frozenset[Allergen]] = {
    **dict.fromkeys(
        ["peanut", "amendoim", "amendoin", "cacahuete", "mani"], frozenset({Allergen.PEANUTS})
    ),
    **dict.fromkeys(["nut"], frozenset({Allergen.TREE_NUTS, Allergen.PEANUTS})),
    **dict.fromkeys(
        [
            "tree nut",
            "walnut",
            "almond",
            "pistachio",
            "cashew",
            "hazelnut",
            "noz",
            "noze",
            "castanha",
            "nuez",
            "nuece",
            "almendra",
            "frutos secos",
            "oleaginosa",
        ],
        frozenset({Allergen.TREE_NUTS}),
    ),
    **dict.fromkeys(["gluten", "wheat", "trigo"], frozenset({Allergen.GLUTEN})),
    **dict.fromkeys(
        [
            "milk",
            "dairy",
            "lactose",
            "cheese",
            "leite",
            "laticinio",
            "queijo",
            "leche",
            "lactosa",
            "lacteo",
            "queso",
        ],
        frozenset({Allergen.MILK}),
    ),
    **dict.fromkeys(["egg", "ovo", "huevo"], frozenset({Allergen.EGGS})),
    **dict.fromkeys(["fish", "peixe", "pescado"], frozenset({Allergen.FISH})),
    **dict.fromkeys(
        ["shellfish", "marisco", "frutos do mar", "mariscos"],
        frozenset({Allergen.CRUSTACEANS, Allergen.MOLLUSCS}),
    ),
    **dict.fromkeys(
        ["seafood"], frozenset({Allergen.FISH, Allergen.CRUSTACEANS, Allergen.MOLLUSCS})
    ),
    **dict.fromkeys(
        [
            "shrimp",
            "prawn",
            "crab",
            "lobster",
            "crustacean",
            "camarao",
            "camaroe",
            "camaron",
            "gamba",
            "crustaceo",
        ],
        frozenset({Allergen.CRUSTACEANS}),
    ),
    **dict.fromkeys(
        ["mussel", "clam", "oyster", "squid", "octopus", "mollusc", "mollusk", "molusco"],
        frozenset({Allergen.MOLLUSCS}),
    ),
    **dict.fromkeys(["soy", "soya", "soja"], frozenset({Allergen.SOY})),
    **dict.fromkeys(["sesame", "gergelim", "sesamo", "tahini"], frozenset({Allergen.SESAME})),
    **dict.fromkeys(["mustard", "mostarda", "mostaza"], frozenset({Allergen.MUSTARD})),
    **dict.fromkeys(["celery", "aipo", "salsao", "apio"], frozenset({Allergen.CELERY})),
    **dict.fromkeys(["sulphite", "sulfite", "sulfito"], frozenset({Allergen.SULPHITES})),
    **dict.fromkeys(["lupin", "tremoco", "altramuz"], frozenset({Allergen.LUPIN})),
}

# Words (accent-free, lowercase; English, Portuguese, Spanish) for ingredients guests
# commonly avoid, mapped to the English terms matched against the menu's ingredient lists.
# Allergens are not repeated here ("sem queijo" already excludes milk), and neither are
# words too broad to filter on ("carne", "salsa") or that would over-match ("olive" would
# also exclude every dish cooked in olive oil).
INGREDIENT_WORDS: dict[str, frozenset[str]] = {
    **dict.fromkeys(["onion", "cebola", "cebolla"], frozenset({"onion"})),
    **dict.fromkeys(
        ["scallion", "spring onion", "cebolinha", "cebolleta"], frozenset({"scallion"})
    ),
    **dict.fromkeys(["garlic", "alho", "ajo"], frozenset({"garlic"})),
    "cilantro": frozenset({"cilantro"}),  # same word in English and Spanish
    "coriander": frozenset({"coriander"}),
    "coentro": frozenset({"cilantro", "coriander"}),  # leaves and seeds in Portuguese
    **dict.fromkeys(["pork", "porco", "cerdo", "puerco"], frozenset({"pork"})),
    **dict.fromkeys(["bacon", "toucinho", "tocino"], frozenset({"bacon"})),
    **dict.fromkeys(["beef", "boi", "ternera"], frozenset({"beef"})),
    **dict.fromkeys(["chicken", "frango", "pollo"], frozenset({"chicken"})),
    **dict.fromkeys(["lamb", "cordeiro", "cordero"], frozenset({"lamb"})),
    **dict.fromkeys(
        ["mushroom", "cogumelo", "champignon", "hongo", "champinon", "seta"],
        frozenset({"mushroom", "shiitake"}),
    ),
    **dict.fromkeys(["tomato", "tomate"], frozenset({"tomato"})),
    **dict.fromkeys(["chili", "chilli", "chile"], frozenset({"chili", "chilli"})),
    "pimenta": frozenset({"chili", "chilli", "pepper", "peppercorn"}),
    **dict.fromkeys(["pepper", "pimienta"], frozenset({"pepper", "peppercorn"})),
    **dict.fromkeys(["ginger", "gengibre", "jengibre"], frozenset({"ginger"})),
    **dict.fromkeys(["cumin", "cominho", "comino"], frozenset({"cumin"})),
    **dict.fromkeys(["cream", "creme de leite", "nata"], frozenset({"cream"})),
    **dict.fromkeys(["eggplant", "aubergine", "berinjela", "berenjena"], frozenset({"eggplant"})),
    **dict.fromkeys(["parsley", "salsinha", "perejil"], frozenset({"parsley"})),
    **dict.fromkeys(["basil", "manjericao", "albahaca"], frozenset({"basil"})),
    **dict.fromkeys(["mayonnaise", "mayo", "maionese", "mayonesa"], frozenset({"mayonnaise"})),
    "tofu": frozenset({"tofu"}),
    **dict.fromkeys(["corn", "milho", "maiz"], frozenset({"corn"})),
    **dict.fromkeys(["cabbage", "repolho", "repollo"], frozenset({"cabbage"})),
    **dict.fromkeys(["lettuce", "alface", "lechuga"], frozenset({"lettuce"})),
    **dict.fromkeys(["chickpea", "grao de bico", "garbanzo"], frozenset({"chickpea"})),
    **dict.fromkeys(["dill", "endro", "eneldo"], frozenset({"dill"})),
    **dict.fromkeys(["mint", "hortela", "menta"], frozenset({"mint"})),
    "kimchi": frozenset({"kimchi"}),
}

# Diet requests that need no extra cue: saying "vegan" is the request itself.
DIET_PATTERNS: dict[DietaryFlag, re.Pattern[str]] = {
    DietaryFlag.VEGAN: re.compile(r"\bvegan[oa]?s?\b"),
    DietaryFlag.VEGETARIAN: re.compile(r"\bvegetarian[oa]?s?\b"),
    DietaryFlag.GLUTEN_FREE: re.compile(
        r"\bgluten[- ]?free\b|\b(?:celiac|coeliac|celiac[oa]s?)\b|"
        r"\b(?:no|without|sem|sin)\s+gluten\b"
    ),
    DietaryFlag.DAIRY_FREE: re.compile(
        r"\bdairy[- ]?free\b|\blactose[- ]intolerant\b|"
        r"\bintoleran(?:te|cia) a (?:la )?lactos[ae]\b|\b(?:sem|sin)\s+lactos[ae]\b"
    ),
    DietaryFlag.HALAL: re.compile(r"\bhalal\b"),
}

_ALLERGEN_PATTERN = re.compile(
    r"\b("
    + "|".join(sorted(map(re.escape, ALLERGEN_WORDS), key=len, reverse=True))
    + r")(?:e?s)?\b"
)
_INGREDIENT_PATTERN = re.compile(
    r"\b("
    + "|".join(sorted(map(re.escape, INGREDIENT_WORDS), key=len, reverse=True))
    + r")(?:e?s)?\b"
)
# A cue shortly before the allergen or ingredient word in the same clause ("allergic to",
# "no", "sem", "não gosto de").
_PRE_CUE = re.compile(
    r"\b(?:allerg\w*|alerg\w*|intoleran\w*|no|not|without|avoid\w*|free of|"
    r"can'?t (?:eat|have)|cannot (?:eat|have)|don'?t (?:eat|want|like)|"
    r"hate|dislike|hold the|"
    r"sem|sin|nada de|nao (?:como|posso|gosto|quero)|odeio|odio|evit\w*)\b"
)
# A cue right after it ("peanut allergy", "nut-free"). English only: Portuguese and
# Spanish put the cue first, and "soy alérgica" means "I am allergic" in Spanish.
_POST_CUE = re.compile(r"^\s*-?\s*(?:allerg\w*|free\b)")
_CLAUSE_BREAK = re.compile(r"[.!?;]|\b(?:but|mas|pero|however|though)\b")
_PRE_WINDOW_CHARS = 40


def normalize(text: str) -> str:
    """Lowercase, strip accents, and unify apostrophes so patterns stay simple."""
    right_single_quote = chr(0x2019)  # typographic apostrophe often typed on phones
    decomposed = unicodedata.normalize("NFKD", text.replace(right_single_quote, "'"))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def detect_restrictions(question: str) -> Restrictions:
    """Find allergens and ingredients the user wants to avoid, and diets they require."""
    text = normalize(question)
    allergens: set[Allergen] = set()
    for match in _ALLERGEN_PATTERN.finditer(text):
        if _has_cue(text, match.start(), match.end()):
            allergens |= ALLERGEN_WORDS[match.group(1)]
    ingredients: set[str] = set()
    for match in _INGREDIENT_PATTERN.finditer(text):
        if _has_cue(text, match.start(), match.end()):
            ingredients |= INGREDIENT_WORDS[match.group(1)]
    flags = {flag for flag, pattern in DIET_PATTERNS.items() if pattern.search(text)}
    return Restrictions(
        exclude_allergens=frozenset(allergens),
        require_flags=frozenset(flags),
        exclude_ingredients=frozenset(ingredients),
    )


def ingredient_terms(words: Iterable[str]) -> frozenset[str]:
    """Map ingredient words given explicitly to the English terms matched on the menu.

    "cebola" and "cebolas" become `onion`, like in a question; unknown words are kept as
    given, so any ingredient on the menu can still be excluded by its English name.
    """
    terms: set[str] = set()
    for word in words:
        key = normalize(word).strip()
        singular = re.sub(r"e?s$", "", key)
        terms |= INGREDIENT_WORDS.get(key) or INGREDIENT_WORDS.get(singular) or {word}
    return frozenset(terms)


def mentions_dietary_topic(question: str) -> bool:
    """True if the question talks about allergens or diets at all, with or without a cue."""
    text = normalize(question)
    return bool(
        _ALLERGEN_PATTERN.search(text)
        or re.search(r"\b(?:allerg|alerg|intoleran|diet|dieta)\w*", text)
        or any(pattern.search(text) for pattern in DIET_PATTERNS.values())
    )


def _has_cue(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - _PRE_WINDOW_CHARS) : start]
    clause_breaks = list(_CLAUSE_BREAK.finditer(before))
    if clause_breaks:
        before = before[clause_breaks[-1].end() :]
    return bool(_PRE_CUE.search(before) or _POST_CUE.match(text[end:]))
