# Design decisions

Short notes on choices with trade-offs. Newest entries at the bottom.

## 001 — uv for environment and dependency management

**Decision:** use uv for Python installation, virtual environments, dependency
resolution, and the lockfile (`uv.lock`, committed).

**Why:** one fast tool replaces pyenv + venv + pip-tools/Poetry, and the lockfile gives
reproducible installs locally and in CI.

**Trade-off:** contributors need uv installed; plain `pip install -e .` still works
because the project uses standard `pyproject.toml` metadata.

## 002 — `src/` layout

**Decision:** application code lives in `src/menu_assistant/`, tests in `tests/`.

**Why:** tests run against the installed package, not whatever happens to be in the
working directory, which catches packaging mistakes early and avoids accidental imports.

**Trade-off:** slightly more nesting than a flat layout.

## 003 — Strict mypy

**Decision:** run mypy with `strict = true` on both `src` and `tests`.

**Why:** data crosses several boundaries (menu files, vector store, LLM, HTTP), and strict
typing together with Pydantic models catches mismatches before runtime. Starting strict
is much cheaper than tightening later.

**Trade-off:** more annotations, and some third-party libraries without type stubs may
need targeted `ignore_missing_imports` overrides.

## 004 — pytest `importlib` import mode

**Decision:** configure pytest with `--import-mode=importlib`; test folders have no
`__init__.py`.

**Why:** it is the mode pytest recommends for new projects. Test modules do not get
added to `sys.path`, so mirrored test file names across folders cannot clash.

**Trade-off:** test modules cannot import each other directly; shared helpers go in
`conftest.py` fixtures.

## 005 — Closed vocabularies and consistency checks for menu data

**Decision:** allergens, dietary flags, and courses are enums (allergens follow the 14 EU
major allergens). Menu validation rejects unknown fields and values, and rejects dishes
whose flags contradict their allergens (e.g. `vegan` + `eggs`, `gluten_free` + `gluten`).
`vegan` also requires `vegetarian` and `dairy_free`.

**Why:** allergen filtering is deterministic and safety-relevant. With free-text values, a
typo like `"glutten"` would silently slip past a filter. Failing loudly at ingestion is far
safer than a wrong recommendation. Requiring implied flags keeps filters simple: asking
for vegetarian dishes is a single flag check.

**Trade-off:** adding a new allergen or flag needs a code change, and menus must use the
exact vocabulary. Free-form descriptors (`spicy`, `japanese`) stay in open `tags`.

## 006 — Domain models at the package root

**Decision:** `Dish` and `Menu` live in `menu_assistant/models.py`, not inside `ingest/`.

**Why:** ingestion, retrieval, prompt building, and the API all use these models. Keeping
them at the root avoids other packages depending on `ingest` internals.

**Trade-off:** one module outside the planned subpackages.

## 007 — One document per dish, allergens only in metadata

**Decision:** each dish is indexed as a single document (name, course, description,
ingredients, preparation, tags, dietary flags). Allergens are *not* part of the embedded
text. Every allergen and dietary flag is stored as an explicit boolean metadata key
(`allergen_peanuts`, `diet_vegan`, ...), and the full dish is stored as JSON.

**Why:**
- Dishes are short, so splitting them would only fragment context. One document per dish
  keeps results and citations one-to-one with the menu.
- Embeddings do not understand negation: with allergens in the text, "no peanuts" would
  pull peanut dishes *closer*. Exclusion belongs in exact metadata filters.
- Explicit `False` values mean a filter never depends on a key being absent.
- Storing the dish JSON lets answers be grounded in exact menu data without re-reading the
  source file.

**Trade-off:** metadata is larger (one key per allergen and flag), and the index must be
rebuilt if the vocabulary changes.

## 008 — Local multilingual embedding model on CPU-only PyTorch

**Status:** model choice superseded by 010; the rest still applies.

**Decision:** embed with `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
behind an `Embedder` protocol, computed by our code (Chroma's built-in embedding function
is disabled). PyTorch is installed from the CPU-only wheel index.

**Why:** the model is small, runs on CPU, needs no API key, and handles questions in
languages other than the menu's (a Portuguese query finds the right English dish). The
protocol lets tests use a fake embedder, and lets the model be swapped after evaluation.
CPU-only wheels avoid several GB of CUDA libraries locally and in CI.

**Trade-off:** first run downloads ~470 MB; ranking quality is modest for a small model
(to be measured in the evaluation milestone). No GPU acceleration.

## 009 — Restrictions are enforced twice, both in code

**Decision:** a `SearchRequest` carries the query plus hard restrictions (allergens to
exclude, required dietary flags, course). `build_where()` turns them into an exact
ChromaDB metadata filter, and every result is then re-checked against the full dish data
(`satisfies()`) before it is returned. Mismatches are dropped and logged.

**Why:** allergen safety must not depend on a single mechanism. The metadata filter keeps
search efficient and returns the best *allowed* dishes rather than filtering a top-k
afterwards; the second check means a stale or corrupted index entry can never surface a
dish that breaks the user's restrictions.

**Trade-off:** if an index entry is wrong, the search returns fewer than `k` results
instead of failing loudly. The warning in the logs is the signal to re-run ingestion.

## 010 — multilingual-e5-base with a small tag boost

**Decision:** default to `intfloat/multilingual-e5-base` (with its `query: ` /
`passage: ` prefixes) and re-rank a pool of 20 filtered candidates with a `+0.05` bonus
per dish tag named in the query. Each index records the embedding setup it was built
with; search refuses a mismatched index, and ingestion rebuilds it.

**Why:** measured on the evaluation set (see `docs/evaluation.md`), this raised
recall@5 from 0.750 to 0.956 and MRR from 0.783 to 0.934 with zero filter violations.
The model fixes cuisine and multilingual matching; the tag boost fixes attribute words
like "spicy" that small embedding models underweight. The index signature check stops
silently wrong results when the model changes, because vectors from different models
are not comparable.

**Trade-off:** a ~1.1 GB model download and slower embedding than MiniLM;
`multilingual-e5-small` with the same boost (0.904 / 0.894) is the lighter fallback. The
boost weight was tuned on a small set without a held-out split, and tag matching only
works for English queries.

## 011 — LLM behind a small protocol, Ollama over plain HTTP

**Decision:** the app talks to LLMs only through `LLMClient.generate(system, messages)`
in `llm/base.py`. Providers live in `llm/` and are chosen in one factory from settings.
The first provider is a local Ollama server, called directly over HTTP with `httpx`
rather than the `ollama` SDK.

**Why:**
- A one-method protocol is easy to fake in tests and easy to implement for another
  provider without touching retrieval or prompting code.
- A local model means no API key or cost while developing.
- Ollama's chat endpoint is a single JSON call; `httpx` (already used by ChromaDB) covers
  it, and an injectable transport makes tests network-free. Failures become an `LLMError`
  with a fix-it message (start Ollama, `ollama pull <model>`, raise the timeout).

**Trade-off:** we maintain the small request/response mapping ourselves, and the default
`llama3.2` (3B) is fast but weaker at following grounding instructions than larger models.

## 012 — Grounded answering: code decides, the LLM only writes

**Decision:** in `rag/`, everything safety-relevant happens in code around the LLM call:
- Restrictions come from explicit options plus deterministic pattern detection in the
  question (EN/PT/ES); the LLM never decides what to filter.
- If no dish passes the filters, a fixed reply is returned and the LLM is not called.
- The prompt contains only retrieved dishes, with every fact the model may use, and
  asks for `[dish-id]` citations.
- After generation, citations are verified: ids of dishes that were not retrieved are
  removed, and dish names written in brackets are mapped to ids.
- The "confirm with staff" notice is attached by code whenever restrictions were applied
  or the question mentions allergens or diets.

**Why:** the domain rules say allergen filtering must be deterministic, answers must cite
dishes, and allergen answers must carry a notice. Small local models do not follow
instructions reliably, so each rule is enforced where it can be tested.

**Trade-off:** pattern detection can miss unusual phrasings (explicit options are the
reliable path) and is deliberately conservative, so it may exclude a dish the user
mentioned casually. The LLM can still add unsupported side remarks inside its text;
measuring that needs an answer-quality evaluation (planned).

## 013 — API: load once at startup, degrade instead of crashing

**Decision:** `create_app()` builds the `AnswerService` once in the FastAPI lifespan and
keeps it on `app.state`; routes get it through a dependency. If the index is missing or
was built with another model, the app still starts: `/health` reports `degraded` with the
fix, and `/ask` returns `503`. LLM failures also map to `503`. `/ask` is a plain `def`
handler so FastAPI runs it in a worker thread.

**Why:** loading the embedding model per request would take seconds; a missing index is
an operator mistake that deserves a clear message, not a crash loop. Embedding and LLM
calls are blocking, so running them on the event loop would stall every other request.
`create_app()` takes a service factory, so tests run the real app with fakes.

**Trade-off:** fixing the index requires restarting the API after re-ingesting. Requests
are handled by FastAPI's thread pool, which is fine for a demo but not for heavy traffic.

## 014 — Ollama as the only LLM provider

**Decision:** ship only the local Ollama provider. The original plan named a hosted API
as the default; it is dropped for now.

**Why:** the project must run end to end with no API key, account, or cost, for the
author and for anyone cloning it. The `LLMClient` protocol keeps the door open: a hosted
provider is one new module in `llm/` plus a factory branch (see
[architecture.md](architecture.md#extending)).

**Trade-off:** answer quality is bounded by models that run on a laptop (`llama3.2` 3B
by default), which follow grounding instructions less reliably than large hosted models.
The code-side checks in decision 012 exist largely to compensate.

## 015 — Course requests are detected in code and filter retrieval

**Decision:** `rag/course.py` detects an explicitly named course (EN/PT/ES: "dessert",
"sobremesa", "postre", "main course", "entrada", ...) and passes it to retrieval as an
exact filter. An explicit `--course` / API `course` wins. Vague words ("something
sweet"), negations ("no dessert"), and questions naming several courses set no filter.
The course is not part of `Restrictions`, so it never triggers the safety notice.

**Why:** the 3B model ignored the course asked for ("vegan dessert" also got a starter).
Filtering before generation means the model only ever sees dishes of that course, the
same "code decides, the LLM only writes" approach as allergens.

**Trade-off:** an explicit course with nothing matching gives the "no match" reply rather
than a near miss from another course. Detection is a word list: "entrée" is left out
because it means a main in the US and a starter elsewhere, and bare "main" is ignored
because of phrases like "main ingredient".

## 016 — Answer quality is measured with deterministic checks, not an LLM judge

**Decision:** `python -m menu_assistant.eval.answers` runs labeled questions through the
real `AnswerService` and scores each reply with rules in code: invented citation ids
(in the raw output), menu dishes named without being retrieved, at least one relevant
citation, at most three recommendations, a correct staff notice, and "not on the menu"
acknowledgement for off-menu questions. Only a notice failure fails the command.

**Why:** the rules mirror the product's promises exactly, cost nothing, and give the same
score for the same reply. The only available model is a local 3B model, which is not a
trustworthy judge. Scoring the raw output shows how much the citation verification is
actually doing.

**Trade-off:** rules cannot judge helpfulness, tone, or the reply's language, and can miss
invented details inside a sentence. The "unavailable" check is a phrase list. Scores
depend on a live model, so the evaluation is not part of CI and results vary slightly
between runs.

## 017 — Docker Compose for a one-command demo

**Decision:** a multi-stage `Dockerfile` builds the API from `uv.lock` (no dev
dependencies, CPU-only PyTorch, non-root user). `compose.yaml` runs it next to the
official Ollama image, with a one-shot service that pulls the model first. The API
container re-runs ingestion on every start; models and the index live in named volumes.

**Why:** a reviewer can try the project without installing Python, uv, or Ollama.
Ingesting one menu takes seconds and is idempotent, so doing it at start-up removes a
manual step and can never leave a stale index. Models are downloaded at run time instead
of baked into the image, which keeps the image small and the build fast.

**Trade-off:** the first start is slow (about 3 GB of downloads), and Ollama runs on CPU
unless GPU access is configured for the container. Re-ingesting at every start would be
wasteful for large menus; then ingestion should become a separate job.
