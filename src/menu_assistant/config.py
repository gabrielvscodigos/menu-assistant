"""Application settings loaded from environment variables and an optional `.env` file."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Version of the dish data stored in the index. Bump it when that data changes shape
# (2 added prices, 3 added translations), so an old index asks to be rebuilt instead of
# failing.
INDEX_FORMAT_VERSION = 3


class Settings(BaseSettings):
    """Runtime configuration. Every field can be overridden with a `MENU_ASSISTANT_*` variable."""

    model_config = SettingsConfigDict(
        env_prefix="MENU_ASSISTANT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    chroma_path: Path = Path(".chroma")
    collection_name: str = "menu"
    embedding_model: str = "intfloat/multilingual-e5-base"
    # Instruction prefixes some models expect (E5 uses "query: " and "passage: ").
    embedding_query_prefix: str = "query: "
    embedding_document_prefix: str = "passage: "
    # Ranking bonus per dish tag mentioned in the query; 0 disables tag boosting.
    tag_boost: float = Field(default=0.05, ge=0.0)

    # LLM used to write answers. Provider-specific code lives in `menu_assistant.llm`.
    llm_provider: Literal["ollama"] = "ollama"
    llm_model: str = "llama3.2"
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_timeout_seconds: float = Field(default=120.0, gt=0.0)
    ollama_base_url: str = "http://localhost:11434"

    @property
    def index_signature(self) -> str:
        """Identifies how the index was built; a different value needs a re-index.

        Covers how documents were embedded and the format of the dish data stored with
        them (`INDEX_FORMAT_VERSION`).
        """
        return (
            f"{self.embedding_model}|document_prefix={self.embedding_document_prefix!r}"
            f"|format={INDEX_FORMAT_VERSION}"
        )
