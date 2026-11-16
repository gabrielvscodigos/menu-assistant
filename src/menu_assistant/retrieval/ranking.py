"""Lexical tag matching used to re-rank semantic search results.

Small embedding models capture *what* a dish is (ramen, tacos) much better than its
*attributes* (spicy, Italian). Dish tags already encode those attributes, so a query that
names a tag gets a small, explicit ranking bonus for dishes carrying it.
"""

import re
from collections.abc import Iterable

_WORD = re.compile(r"\w+")


def _normalize(word: str) -> str:
    """Lowercase and drop a plural 's' so 'noodle' matches 'noodles'."""
    word = word.lower()
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _words(text: str) -> list[str]:
    return [_normalize(word) for word in _WORD.findall(text)]


def matched_tags(query: str, tags: Iterable[str]) -> set[str]:
    """Return the tags whose words all appear in the query.

    Multi-word tags such as `middle-eastern` need every word present.
    """
    query_words = set(_words(query))
    return {tag for tag in tags if (tag_words := _words(tag)) and set(tag_words) <= query_words}
