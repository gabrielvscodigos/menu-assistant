"""Lexical tag matching used to re-rank semantic search results.

Small embedding models capture *what* a dish is (ramen, tacos) much better than its
*attributes* (spicy, Italian). Dish tags already encode those attributes, so a query that
names a tag gets a small, explicit ranking bonus for dishes carrying it.

Tags are written in English. Brazilian Portuguese words for common tags are mapped to
them (`TAG_ALIASES`), so "algo apimentado com macarrão" boosts `spicy` and `noodles`.
"""

import re
import unicodedata
from collections.abc import Iterable

_WORD = re.compile(r"\w+")

# Portuguese word (accent-free) -> English tags it stands for. Masculine and
# feminine forms are listed; plurals are handled by `_normalize`.
TAG_ALIASES: dict[str, frozenset[str]] = {
    **dict.fromkeys(
        ["apimentado", "apimentada", "picante", "ardido", "ardida"], frozenset({"spicy"})
    ),
    "macarrao": frozenset({"noodles", "pasta"}),  # Brazilian usage covers both
    **dict.fromkeys(["massa", "espaguete"], frozenset({"pasta"})),
    **dict.fromkeys(["lamen", "talharim"], frozenset({"noodles"})),
    **dict.fromkeys(["sopa", "caldo"], frozenset({"soup"})),
    **dict.fromkeys(["porco", "suino", "suina"], frozenset({"pork"})),
    "frango": frozenset({"chicken"}),
    **dict.fromkeys(["bovina", "bovino"], frozenset({"beef"})),
    "cordeiro": frozenset({"lamb"}),
    **dict.fromkeys(["frito", "frita"], frozenset({"fried"})),
    "crocante": frozenset({"crispy"}),
    **dict.fromkeys(["grelhado", "grelhada"], frozenset({"grilled"})),
    **dict.fromkeys(["cremoso", "cremosa"], frozenset({"creamy"})),
    "suave": frozenset({"mild"}),
    "leve": frozenset({"light"}),
    **dict.fromkeys(["fresco", "fresca"], frozenset({"fresh"})),
    "doce": frozenset({"sweet"}),
    **dict.fromkeys(["azedo", "azeda"], frozenset({"sour"})),
    **dict.fromkeys(["defumado", "defumada"], frozenset({"smoky"})),
    "cogumelo": frozenset({"mushroom"}),
    "arroz": frozenset({"rice"}),
    "milho": frozenset({"corn"}),
    "queijo": frozenset({"cheese"}),
    "coco": frozenset({"coconut"}),
    "cafe": frozenset({"coffee"}),
    "salada": frozenset({"salad"}),
    **dict.fromkeys(["fruta", "frutado", "frutada"], frozenset({"fruity"})),
    "alho": frozenset({"garlicky"}),
    "erva": frozenset({"herby"}),
    **dict.fromkeys(["japones", "japonesa"], frozenset({"japanese"})),
    **dict.fromkeys(["chines", "chinesa"], frozenset({"chinese"})),
    **dict.fromkeys(["coreano", "coreana"], frozenset({"korean"})),
    **dict.fromkeys(["tailandes", "tailandesa"], frozenset({"thai"})),
    **dict.fromkeys(["indiano", "indiana"], frozenset({"indian"})),
    **dict.fromkeys(["mexicano", "mexicana"], frozenset({"mexican"})),
    **dict.fromkeys(["italiano", "italiana"], frozenset({"italian"})),
    "arabe": frozenset({"middle-eastern"}),
    **dict.fromkeys(["classico", "classica"], frozenset({"classic"})),
}


def _normalize(word: str) -> str:
    """Lowercase, strip accents, and drop a plural 's' so 'noodle' matches 'noodles'."""
    decomposed = unicodedata.normalize("NFKD", word.lower())
    word = "".join(c for c in decomposed if not unicodedata.combining(c))
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _words(text: str) -> list[str]:
    return [_normalize(word) for word in _WORD.findall(text)]


# Keys normalized like query words ("chinês" -> "chines" -> "chine"), so lookups match.
_ALIASES = {_normalize(word): tags for word, tags in TAG_ALIASES.items()}


def _query_words(query: str) -> set[str]:
    """Words of the query plus the English tag words its Portuguese aliases stand for."""
    words = set(_words(query))
    for word in list(words):
        for tag in _ALIASES.get(word, ()):
            words.update(_words(tag))
    return words


def matched_tags(query: str, tags: Iterable[str]) -> set[str]:
    """Return the tags whose words all appear in the query (directly or via an alias).

    Multi-word tags such as `middle-eastern` need every word present.
    """
    query_words = _query_words(query)
    return {tag for tag in tags if (tag_words := _words(tag)) and set(tag_words) <= query_words}
