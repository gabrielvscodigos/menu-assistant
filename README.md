# menu-assistant

[![CI](https://github.com/gabrielvscodigos/menu-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/gabrielvscodigos/menu-assistant/actions/workflows/ci.yml)

A retrieval-augmented generation (RAG) assistant that helps people choose what to eat
from a restaurant menu.

Ask things like *"I like spicy ramen, what else here would I enjoy?"* and get suggestions
grounded in each dish's ingredients, preparation, dietary flags, and allergens.

> **Status:** early development. Menus can be validated, indexed into ChromaDB, and
> searched with deterministic allergen/dietary filters; answer generation and the API are
> not implemented yet.

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

Index the sample menu into the local vector store:

```bash
uv run python -m menu_assistant.ingest data/menu.json
```

The first run downloads the embedding model (~470 MB) into the Hugging Face cache.
Re-running is idempotent: dishes are upserted by id and dishes no longer on the menu are
removed from the index.

## Configuration

Settings are read from environment variables or a `.env` file. Copy
[`.env.example`](.env.example) to `.env` to override the defaults:

| Variable                          | Default                                                       |
| --------------------------------- | ------------------------------------------------------------- |
| `MENU_ASSISTANT_CHROMA_PATH`      | `.chroma`                                                     |
| `MENU_ASSISTANT_COLLECTION_NAME`  | `menu`                                                        |
| `MENU_ASSISTANT_EMBEDDING_MODEL`  | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |

## Development

| Task              | Command                                         |
| ----------------- | ----------------------------------------------- |
| Run tests         | `uv run pytest`                                 |
| Lint              | `uv run ruff check .`                           |
| Format            | `uv run ruff format .`                          |
| Type check        | `uv run mypy src tests`                         |

## Menu data

Menus are JSON files validated against the models in
[`src/menu_assistant/models.py`](src/menu_assistant/models.py). Each dish has:

| Field           | Description                                                        |
| --------------- | ------------------------------------------------------------------ |
| `id`            | Stable slug (`spicy-miso-ramen`), used for indexing and citations  |
| `name`          | Display name                                                       |
| `course`        | `starter`, `main`, `side`, or `dessert`                            |
| `description`   | Short description of the dish                                      |
| `ingredients`   | Non-empty list of ingredients                                      |
| `preparation`   | How the dish is made                                               |
| `tags`          | Free-form lowercase tags (`spicy`, `japanese`, `noodles`, ...)     |
| `dietary_flags` | `vegan`, `vegetarian`, `gluten_free`, `dairy_free`, `halal`        |
| `allergens`     | The 14 EU major allergens (`gluten`, `peanuts`, `sesame`, ...)     |

Validation rejects unknown fields, unknown allergens or flags, duplicate ids, and
contradictions such as a `vegan` dish listing `eggs` or a `gluten_free` dish listing
`gluten`.

[`data/menu.json`](data/menu.json) is a **fictional** sample menu with 25 dishes across
several cuisines, used for development, tests, and evaluation.

## Project structure

```
src/menu_assistant/
  models.py   menu domain models (Dish, Menu, allergens, dietary flags)
  config.py   settings from environment variables / .env
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
