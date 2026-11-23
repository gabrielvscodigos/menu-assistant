"""Deterministic detection of the language a guest writes in (English, Portuguese, Spanish).

The LLM already answers in the guest's language, but some texts are written in code: the
staff-confirmation notice and the reply when no dish matches. Those are product rules,
so they are picked here from the question, never left to the LLM.

Detection counts common words that are distinctive for each language, plus letters only
one of them uses (`ã`, `ç` in Portuguese; `ñ`, `¿` in Spanish). Short or unclear
questions fall back to English, the language the menu is written in.
"""

import re
from enum import StrEnum

from menu_assistant.rag.restrictions import normalize


class Language(StrEnum):
    EN = "en"
    PT = "pt"
    ES = "es"


def _word_set(words: str) -> frozenset[str]:
    return frozenset(words.split())


# Accent-free, lowercase words. Words shared by two languages ("no", "algo", "comida",
# "que", "de", "para", "me") are left out, since they cannot tell them apart.
_WORDS: dict[Language, frozenset[str]] = {
    Language.EN: _word_set(
        "the i i'm im and with without something anything any want like what is are "
        "have has my you for of to dish dishes food can could would please here "
        "don't dont not"
    ),
    Language.PT: _word_set(
        "eu nao voce com sem um uma uns umas tem tenho quero gosto gostaria alguma "
        "algum isso esse essa mas muito pra do da dos das ao e os meu minha prato "
        "cardapio sobremesa sou estou posso"
    ),
    Language.ES: _word_set(
        "yo con sin un una unos unas tiene tengo quiero gusta gustaria alguna "
        "algun eso ese esa pero muy del el los las y mi plato carta postre "
        "soy estoy puedo hay"
    ),
}
# Letters that only appear in one of the three languages, checked before normalizing.
_LETTERS: dict[Language, re.Pattern[str]] = {
    Language.PT: re.compile(r"[ãõç]"),
    Language.ES: re.compile(r"[ñ¿¡]"),
}
_WORD = re.compile(r"[a-z']+")
# On a tie, prefer English (the menu's language), then Portuguese (the main audience).
_TIE_ORDER = (Language.EN, Language.PT, Language.ES)


def detect_language(question: str, default: Language = Language.EN) -> Language:
    """Return the most likely language of `question`; `default` when there is no clue."""
    scores = dict.fromkeys(_TIE_ORDER, 0)
    for language, letters in _LETTERS.items():
        if letters.search(question.lower()):
            scores[language] += 2
    for word in _WORD.findall(normalize(question)):
        for language, words in _WORDS.items():
            if word in words:
                scores[language] += 1
    if not any(scores.values()):
        return default
    return max(_TIE_ORDER, key=lambda language: scores[language])
