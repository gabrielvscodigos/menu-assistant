"""Provider-neutral LLM interface. The rest of the app depends only on this module."""

from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from menu_assistant.models import NonEmptyStr


class ChatMessage(BaseModel):
    """One turn of a conversation, excluding the system prompt."""

    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant"]
    content: NonEmptyStr


class LLMError(Exception):
    """The LLM could not produce an answer (unreachable, misconfigured, or bad output).

    Messages are written for the person running the app and say how to fix the problem.
    """


class LLMClient(Protocol):
    """Generates a text reply from a system prompt and a conversation."""

    def generate(self, system: str, messages: Sequence[ChatMessage]) -> str:
        """Return the assistant's reply. Raises `LLMError` on any provider failure."""
        ...

    def check(self) -> None:
        """Confirm the provider is reachable and the model is available, cheaply.

        Raises `LLMError` explaining how to fix the problem. Used by health checks and
        by the CLI to fail fast, before loading the embedding model.
        """
        ...
