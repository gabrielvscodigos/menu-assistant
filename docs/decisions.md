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
