"""Tests for how earlier turns of a conversation shape the next answer."""

from menu_assistant.llm import ChatMessage
from menu_assistant.models import Allergen
from menu_assistant.rag.conversation import (
    LLM_CONTEXT_TURNS,
    recent_turns,
    restrictions_from_history,
    retrieval_query,
)


def user(content: str) -> ChatMessage:
    return ChatMessage(role="user", content=content)


def assistant(content: str) -> ChatMessage:
    return ChatMessage(role="assistant", content=content)


def test_restrictions_from_every_user_turn_are_kept() -> None:
    history = [
        user("I'm allergic to peanuts"),
        assistant("Try the Elote [elote]."),
        user("something vegan, no onion"),
        assistant("Try the Edamame [edamame]."),
    ]

    restrictions = restrictions_from_history(history)

    assert restrictions.exclude_allergens == {Allergen.PEANUTS}
    assert restrictions.require_flags == {"vegan"}
    assert restrictions.exclude_ingredients == {"onion"}


def test_assistant_turns_never_add_restrictions() -> None:
    history = [user("spicy noodles?"), assistant("The Dan Dan Noodles have no peanuts... wait")]

    assert not restrictions_from_history(history)


def test_retrieval_query_adds_the_last_two_user_turns() -> None:
    history = [
        user("something light"),
        assistant("..."),
        user("I like spicy ramen"),
        assistant("..."),
        user("with pork"),
        assistant("..."),
    ]

    assert retrieval_query("and without egg?", history) == (
        "I like spicy ramen with pork and without egg?"
    )


def test_retrieval_query_without_history_is_the_question() -> None:
    assert retrieval_query("spicy ramen", []) == "spicy ramen"


def test_recent_turns_are_limited_and_start_with_the_guest() -> None:
    history = [turn for n in range(5) for turn in (user(f"q{n}"), assistant(f"a{n}"))]

    recent = recent_turns(history)

    assert len(recent) == LLM_CONTEXT_TURNS
    assert recent[0] == user("q2")
    assert recent[-1] == assistant("a4")


def test_recent_turns_drop_a_leading_assistant_turn() -> None:
    assert recent_turns([assistant("hello"), user("hi")]) == [user("hi")]
