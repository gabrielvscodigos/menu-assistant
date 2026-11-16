# menu-assistant

[![CI](https://github.com/gabrielvscodigos/menu-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/gabrielvscodigos/menu-assistant/actions/workflows/ci.yml)

A retrieval-augmented generation (RAG) assistant that helps people choose what to eat
from a restaurant menu.

Ask things like *"I like spicy ramen, what else here would I enjoy?"* and get suggestions
grounded in each dish's ingredients, preparation, dietary flags, and allergens.

> **Status:** early development. The project skeleton and dev tooling are in place;
> ingestion, retrieval, and the API are not implemented yet.

## Design principles

- **Grounded answers only.** The LLM answers exclusively from retrieved menu data and
  cites the dishes it used. If something is not on the menu, it says so.
- **Deterministic safety filters.** Allergen and dietary filtering is done with metadata
  filters in code, never delegated to the LLM.
- **Staff confirmation notice.** Every answer involving allergens or dietary restrictions
  reminds the user to confirm with restaurant staff.
- **Provider-agnostic LLM access.** The app depends only on an `LLMClient` interface;
  provider-specific code (Anthropic API, Ollama) lives in `llm/`.

## Tech stack

| Concern          | Choice                                   |
| ---------------- | ---------------------------------------- |
| Language         | Python 3.12, managed with [uv]           |
| API              | FastAPI                                  |
| Vector store     | ChromaDB (local, persistent)             |
| Embeddings       | sentence-transformers (multilingual)     |
| LLM              | Anthropic API (default) or Ollama        |
| Quality          | pytest, ruff, mypy (strict)              |

Runtime dependencies are added as each feature lands.

## Getting started

Prerequisite: [uv] installed. uv downloads Python 3.12 automatically if needed.

```bash
git clone https://github.com/gabrielvscodigos/menu-assistant.git
cd menu-assistant
uv sync
```

## Development

| Task              | Command                                         |
| ----------------- | ----------------------------------------------- |
| Run tests         | `uv run pytest`                                 |
| Lint              | `uv run ruff check .`                           |
| Format            | `uv run ruff format .`                          |
| Type check        | `uv run mypy src tests`                         |

## Project structure

```
src/menu_assistant/
  api/        FastAPI app and routes
  ingest/     menu loading, validation, chunking, indexing
  retrieval/  embeddings, vector store, filters, ranking
  llm/        LLMClient interface and provider implementations
  rag/        prompt building and answer generation
  eval/       evaluation dataset and metrics
data/         sample (fictional) menu data
tests/        mirrors src/ structure
docs/         architecture notes and decisions
```

Design decisions and their trade-offs are recorded in
[docs/decisions.md](docs/decisions.md).

## License

See [LICENSE](LICENSE).

[uv]: https://docs.astral.sh/uv/
