"""Build the configured LLM client. The only place that knows which providers exist."""

from menu_assistant.config import Settings
from menu_assistant.llm.base import LLMClient
from menu_assistant.llm.ollama import OllamaClient


def llm_client_from_settings(settings: Settings) -> LLMClient:
    """Return a client for `settings.llm_provider`."""
    match settings.llm_provider:
        case "ollama":
            return OllamaClient(
                base_url=settings.ollama_base_url,
                model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
                temperature=settings.llm_temperature,
            )
