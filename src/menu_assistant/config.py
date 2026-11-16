"""Application settings loaded from environment variables and an optional `.env` file."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def index_signature(self) -> str:
        """Identifies how documents were embedded; a different value needs a re-index."""
        return f"{self.embedding_model}|document_prefix={self.embedding_document_prefix!r}"
