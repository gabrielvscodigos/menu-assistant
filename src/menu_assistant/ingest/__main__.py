"""Command-line entry point: `menu-ingest <menu.json>` (or `python -m menu_assistant.ingest`)."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from menu_assistant.config import Settings
from menu_assistant.console import use_utf8_output
from menu_assistant.ingest.indexer import index_menu
from menu_assistant.ingest.loader import MenuLoadError, load_menu
from menu_assistant.retrieval.embeddings import embedder_from_settings
from menu_assistant.retrieval.vector_store import open_collection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="menu-ingest",
        description="Validate a menu JSON file and index its dishes into ChromaDB.",
    )
    parser.add_argument("menu_path", type=Path, help="path to the menu JSON file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    use_utf8_output()
    args = build_parser().parse_args(argv)
    settings = Settings()

    try:
        menu = load_menu(args.menu_path)
    except MenuLoadError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    embedder = embedder_from_settings(settings)
    # Ingestion is the one place allowed to rebuild an index made with another model.
    collection = open_collection(
        settings.chroma_path,
        settings.collection_name,
        settings.index_signature,
        reset_on_mismatch=True,
    )
    result = index_menu(menu, collection, embedder)

    print(
        f"Indexed {result.indexed} dishes from '{menu.restaurant}' into collection "
        f"'{settings.collection_name}' at {settings.chroma_path} "
        f"({result.removed} stale removed)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
