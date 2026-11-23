"""Follow-up questions: what earlier turns of a conversation contribute to the next answer.

The server keeps no state: callers send the earlier turns with each question. Everything
here is deterministic, like the rest of the restriction handling:

- Restrictions stated in any earlier user turn keep applying ("I'm allergic to peanuts",
  then "and a dessert?"). They are never lifted by later text; a guest who changes their
  mind starts a new conversation. Wrongly keeping a restriction is the safe mistake.
- The retrieval query adds the last few user turns, so "and without gluten?" still
  searches for what the guest asked about before.
- Only recent turns go to the LLM, so the prompt stays small enough for local models.
"""

from collections.abc import Sequence

from menu_assistant.llm import ChatMessage
from menu_assistant.rag.restrictions import Restrictions, detect_restrictions

# Earlier user turns added to the retrieval query, most recent last.
QUERY_CONTEXT_TURNS = 2
# Earlier turns (user and assistant) passed to the LLM.
LLM_CONTEXT_TURNS = 6


def user_turns(history: Sequence[ChatMessage]) -> list[str]:
    return [turn.content for turn in history if turn.role == "user"]


def restrictions_from_history(history: Sequence[ChatMessage]) -> Restrictions:
    """Merge the restrictions detected in every earlier user turn."""
    restrictions = Restrictions()
    for content in user_turns(history):
        restrictions = restrictions.merge(detect_restrictions(content))
    return restrictions


def retrieval_query(question: str, history: Sequence[ChatMessage]) -> str:
    """The question, preceded by the last few user turns that give it context."""
    return " ".join([*user_turns(history)[-QUERY_CONTEXT_TURNS:], question])


def recent_turns(history: Sequence[ChatMessage]) -> list[ChatMessage]:
    """The last turns to show the LLM, starting with a user turn."""
    recent = list(history[-LLM_CONTEXT_TURNS:])
    while recent and recent[0].role != "user":
        recent.pop(0)
    return recent
