"""Application settings loaded from environment variables and an optional `.env` file."""

from pathlib import Path

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
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
