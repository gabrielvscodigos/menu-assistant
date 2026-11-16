# menu-assistant

[![CI](https://github.com/gabrielvscodigos/menu-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/gabrielvscodigos/menu-assistant/actions/workflows/ci.yml)

A retrieval-augmented generation (RAG) assistant that helps people choose what to eat
from a restaurant menu.

Ask things like *"I like spicy ramen, what else here would I enjoy?"* and get suggestions
grounded in each dish's ingredients, preparation, dietary flags, and allergens.

> **Status:** working end to end: menus are validated and indexed, retrieval is filtered
> and evaluated, and grounded answers from a local LLM (Ollama) are available from the
> command line and an HTTP API.

## Design principles

- **Grounded answers only.** The LLM answers exclusively from retrieved menu data and
  cites the dishes it used. If something is not on the menu, it says so.
- **Deterministic safety filters.** Allergen and dietary filtering is done with metadata
  filters in code, never delegated to the LLM.
- **Staff confirmation notice.** Every answer involving allergens or dietary restrictions
  reminds the user to confirm with restaurant staff.
- **Provider-agnostic LLM access.** The app depends only on an `LLMClient` interface;
  provider-specific code (currently a local Ollama client) lives in `llm/`.

## Tech stack

| Concern          | Choice                                   |
| ---------------- | ---------------------------------------- |
| Language         | Python 3.12, managed with [uv]           |
| API              | FastAPI                                  |
| Vector store     | ChromaDB (local, persistent)             |
| Embeddings       | sentence-transformers (multilingual)     |
| LLM              | Local model via Ollama (`llama3.2`)      |
| Quality          | pytest, ruff, mypy (strict)              |

How the pieces fit together is described in [docs/architecture.md](docs/architecture.md).

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

The first run downloads the embedding model (~1.1 GB) into the Hugging Face cache.
Re-running is idempotent: dishes are upserted by id and dishes no longer on the menu are
removed from the index. If the embedding model changes, ingestion rebuilds the index;
search refuses to use an index built with a different model.

## Run with Docker

The whole stack (API, Ollama, the model download, and menu ingestion) starts with one
command. Only [Docker](https://docs.docker.com/get-docker/) is needed:

```bash
docker compose up --build
```

Then open <http://localhost:8000/docs>. The first start downloads `llama3.2` (~2 GB) and
the embedding model (~1.1 GB) into named volumes, so it takes a few minutes; later starts
reuse them. Use another Ollama model with `MENU_ASSISTANT_LLM_MODEL=qwen2.5:7b docker
compose up`. Everything runs on CPU; `docker compose down -v` removes the volumes.

## Ask for suggestions

With the menu indexed and Ollama running:

```bash
uv run python -m menu_assistant.rag "I like spicy ramen, what else here would I enjoy?"
uv run python -m menu_assistant.rag "I'm allergic to peanuts. Any spicy noodles?"
uv run python -m menu_assistant.rag "something light" --exclude soy --diet vegan
uv run python -m menu_assistant.rag "Quero uma sobremesa vegana"   # course: dessert
```

Example output:

```text
You might enjoy the Spicy Miso Ramen [spicy-miso-ramen] and the Dan Dan Noodles
[dan-dan-noodles]. Both have a spicy kick: the ramen has a rich, savory broth, while
the noodles come in a numbing, spicy sesame sauce.

Sources:
  - Spicy Miso Ramen [spicy-miso-ramen]
  - Dan Dan Noodles [dan-dan-noodles]
Restrictions applied: none
```

How an answer is produced:

1. **Restrictions are decided in code.** `--exclude` / `--diet` options are combined with
   restrictions detected in the question ("allergic to peanuts", "sou vegano",
   "sin gluten"), using deterministic patterns in English, Portuguese, and Spanish.
   A requested course ("a vegan dessert", "um prato principal") is detected the same way,
   or set with `--course`.
2. **Retrieval applies them as exact filters**, so excluded dishes never reach the LLM.
   If nothing passes, a fixed "no match" reply is returned without calling the LLM.
3. **The LLM writes the reply** from the retrieved dishes only, citing them as `[dish-id]`.
4. **The output is checked in code.** Citations of dishes that were not retrieved are
   removed, cited dish names are mapped to ids, and list items that do not name a
   retrieved dish (invented suggestions like "Coconut Ice Cream") are dropped. Whenever allergens or diets are
   involved, the staff-confirmation notice is added by code, not by the LLM.

Known limitation of the default 3B model: it sometimes adds suggestions the menu does
not support (e.g. "ask for extra chili"). Safety and course filtering are unaffected,
because they never depend on the LLM. Larger models (`qwen2.5:7b`) follow the rules better.

## HTTP API

```bash
uv run uvicorn menu_assistant.api.main:app --reload
```

Interactive docs (Swagger UI) are at <http://127.0.0.1:8000/docs>.

| Method | Path      | Description                                                  |
| ------ | --------- | ------------------------------------------------------------ |
| GET    | `/health` | `ok`, or `degraded` with a fix-it message if the index is not ready |
| POST   | `/ask`    | Grounded suggestions for a question                          |

```bash
curl -X POST http://127.0.0.1:8000/ask   -H "Content-Type: application/json"   -d '{"question": "Any spicy noodles?", "exclude_allergens": ["peanuts"]}'
```

```json
{
  "answer": "... Spicy Miso Ramen [spicy-miso-ramen] ...",
  "sources": [{"id": "spicy-miso-ramen", "name": "Spicy Miso Ramen", "course": "main",
               "allergens": ["eggs", "gluten", "sesame", "soy"], "dietary_flags": [], "score": 0.91}],
  "candidates": ["... every dish the LLM was given ..."],
  "applied_restrictions": {"exclude_allergens": ["peanuts"], "require_flags": [], "course": null},
  "notice": "Allergen and dietary information comes from the menu and may be incomplete. ..."
}
```

An optional `course` (`starter`, `main`, `side`, `dessert`) overrides the course detected
in the question. Unknown allergens, flags, or courses are rejected with `422`. If Ollama is unreachable, `/ask`
returns `503` with the reason.

## Configuration

Settings are read from environment variables or a `.env` file. Copy
[`.env.example`](.env.example) to `.env` to override the defaults:

| Variable                                   | Default                          |
| ------------------------------------------ | -------------------------------- |
| `MENU_ASSISTANT_CHROMA_PATH`               | `.chroma`                        |
| `MENU_ASSISTANT_COLLECTION_NAME`           | `menu`                           |
| `MENU_ASSISTANT_EMBEDDING_MODEL`           | `intfloat/multilingual-e5-base`  |
| `MENU_ASSISTANT_EMBEDDING_QUERY_PREFIX`    | `query: `                        |
| `MENU_ASSISTANT_EMBEDDING_DOCUMENT_PREFIX` | `passage: `                      |
| `MENU_ASSISTANT_TAG_BOOST`                 | `0.05`                           |
| `MENU_ASSISTANT_LLM_PROVIDER`              | `ollama`                         |
| `MENU_ASSISTANT_LLM_MODEL`                 | `llama3.2`                       |
| `MENU_ASSISTANT_LLM_TEMPERATURE`           | `0.2`                            |
| `MENU_ASSISTANT_LLM_TIMEOUT_SECONDS`       | `120`                            |
| `MENU_ASSISTANT_OLLAMA_BASE_URL`           | `http://localhost:11434`         |

The retrieval defaults were chosen by evaluation; see [docs/evaluation.md](docs/evaluation.md).

### Local LLM (Ollama)

Answers are generated by a local model through [Ollama](https://ollama.com). Install it,
then pull the default model:

```bash
ollama pull llama3.2
```

Any other Ollama model works by setting `MENU_ASSISTANT_LLM_MODEL` (larger models such as
`qwen2.5:7b` follow grounding instructions more reliably).

## Development

| Task              | Command                                         |
| ----------------- | ----------------------------------------------- |
| Run tests         | `uv run pytest`                                 |
| Test coverage     | `uv run pytest --cov` (CI fails below 90%)      |
| Lint              | `uv run ruff check .`                           |
| Format            | `uv run ruff format .`                          |
| Type check        | `uv run mypy src tests`                         |
| Evaluate retrieval| `uv run python -m menu_assistant.eval`          |
| Evaluate answers  | `uv run python -m menu_assistant.eval.answers`  |
| Run the API       | `uv run uvicorn menu_assistant.api.main:app --reload` |

## Evaluation

Retrieval is measured on 44 hand-labeled queries (taste preferences, allergen/diet
filters, Brazilian Portuguese and Spanish questions) with recall@5, MRR, and a filter-violation
count that must stay at zero.

| Configuration                                   | recall@5  | MRR       | violations |
| ----------------------------------------------- | --------: | --------: | ---------: |
| Baseline (MiniLM-L12, pure vector search)       |     0.750 |     0.783 |          0 |
| multilingual-e5-base + tag boost (34 cases)     |     0.956 |     0.934 |          0 |
| **Current** (+ Portuguese tag aliases, 44 cases) | **0.989** | **0.966** |          0 |

Generated answers are checked separately on 28 questions (with Ollama running) using
deterministic rules, not an LLM judge:

| Check (llama3.2)                                       | Result |
| ------------------------------------------------------ | -----: |
| Cases passing every check                              |    93% |
| Replies naming a dish retrieval excluded               |      0 |
| Staff notice present exactly when expected             |   100% |
| Off-menu requests acknowledged ("not on the menu")     |    83% |
| Raw replies citing an id the model was not given       | 0–9%\* |
| Replies with a listed dish the model was not given     | 0–9%\* |

\* across runs; removed in code before the user sees them. The model also sometimes
invents prices, which the menu does not have.

Method, the full experiment grid, remaining misses, and caveats are in
[docs/evaluation.md](docs/evaluation.md).

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
  retrieval/  embeddings, vector store, filters, tag-boost ranking
  llm/        LLMClient interface and provider implementations
  rag/        restriction detection, prompt building, grounded answers
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
