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
