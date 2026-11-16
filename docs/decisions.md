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
