# Task 2.1 — chore: `jev` optional extra and SDK compatibility check (card e6f3dce5)

Parent: Story 2 "Jev adapter and jev extra" (e01d0be7), milestone e3bd09dc. Source design: `docs/superpowers/specs/2026-10-01-classifier-port-design.md` (gitignored; read it from the main checkout at `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/`), sections "Packaging" and "Open questions".

## Scope

This card only changes packaging. It touches no Python code.

1. `pyproject.toml`: add `jev = ["typesafe-sdk>=<floor>"]` under `[project.optional-dependencies]`, next to the existing `dev` and `docs` entries. Do not change core `dependencies`, do not change `requires-python` (`>=3.11`), and do not change `version` (it stays `0.7.0`; the bump to `0.8.0` belongs to a later card).
2. `.github/workflows/test.yml`: change the install step from `pip install -e ".[dev]"` to `pip install -e ".[dev,jev]"` so the adapter tests from later cards run in CI. Do not add `typesafe-sdk` to `dev`. Leave the test step unchanged.
3. `uv.lock`: it is git-tracked and records optional dependencies per extra, so run `uv lock` after the `pyproject.toml` edit and commit the result (it adds `typesafe-sdk`, its transitive deps such as `httpx2`, and the `jev` extra). The lock's recorded `py-ai-toolkit` version is stale (0.6.1 vs 0.7.0); `uv lock` will refresh it, which is acceptable and not a version bump. If `uv lock` changes any pinned version of an existing package, STOP and treat it as a conflict under "Error path" unless the change is only the `py-ai-toolkit` self-version. Lockfile updates are expected to be additive.
4. `MANIFEST.in`: confirm that it needs no change, because there is no new non-Python package data. Do not edit it.

Replace `<floor>` in item 1 with the version chosen under Open question 1 (a bare `>=X.Y.Z` lower bound, no ceiling).

Out of scope, because sibling cards or later stories own it: `adapters/jev_adapter.py`, any change to `adapters/__init__.py`, any test file, factories, docs, the version bump, and the live test. Do not commit the unrelated uncommitted `.gitignore` change (`*.code-workspace`).

## Open question 1: the version floor

The floor is the oldest `typesafe-sdk` release that has `AsyncTypeSafeClient.system_one` and `SystemOneResponse` with `nouls`, `choices` and `scores`, and that has the `Score.criteria` shape the adapter will target. That shape is an ordered sequence, introduced in 0.6.0, which made 0.6.0 a breaking release. The known releases are 0.5.7, 0.6.0, 0.7.0, 0.7.1 and 0.7.2.

Determine the floor by experiment. Install 0.6.0 (and 0.5.7 for contrast) in throwaway venvs. For each, inspect `typesafe_sdk.AsyncTypeSafeClient.system_one` and the fields of `SystemOneResponse` and `Score`.

- Expected result: `>=0.6.0`.
- Conservative alternative: `>=0.7.0`, the first pydantic-based release, which also adds `response_model`. Choose it if 0.6.0 lacks a required attribute or exposes models in a way the adapter cannot map with the same code.

Record the chosen floor and why in the commit message.

## Open question 2: resolver compatibility

In a clean venv (`uv venv` then `uv pip install -e ".[jev]"`, or the pip equivalent), install the package with the extra. It must resolve with no conflict against `openai`, `instructor`, `pydantic>=2.12.4` and `httpx`. Note that `typesafe-sdk` depends on `httpx2`, which is a separate distribution from `httpx`. Also confirm that the SDK's `requires_python` (`>=3.10`) admits `>=3.11`, so no higher floor needs documenting. Record the outcome in the commit message: no `httpx2` conflict, and Python `>=3.11` confirmed.

## Error path

If the install hits a real resolver conflict, or no released SDK version exposes the required API: STOP. Report the conflict or the gap. Do not pin around it, do not add ceilings, and do not edit core dependencies.

## Observable behavior

- `pip install "py-ai-toolkit[jev]"` installs `typesafe-sdk` at or above the floor.
- A plain `pip install py-ai-toolkit` installs nothing new.
- CI installs `dev` and `jev`.
- `import py_ai_toolkit` behaves exactly as before.

## Tests

No new tests. This is a packaging-only card. Under the design's Testing section (the repo's only test-placement rule), every planned test belongs to the feature cards: `tests/unit/test_classifier.py`, `tests/unit/test_jev_adapter.py`, `tests/unit/test_hooks.py` and `tests/live/test_jev_live.py`. None of them covers packaging. This card is proven by:

- The clean-env `[jev]` install succeeding, recorded in the commit message.
- The existing unit suite (`tests/unit/`, tier: unit) staying green under the verification command `uv run pytest tests/ --ignore=tests/test_run_task.py`. Optionally, also run it with the extra present (`uv run --extra dev --extra jev pytest tests/ --ignore=tests/test_run_task.py`) to show that installing the SDK breaks nothing.
- Lint (`ruff check --select E,F` on changed `.py` files) being vacuous, because no `.py` files change.

## Commit message must include

- The chosen floor and the evidence for it (the API inspected per version, and the `Score.criteria` shape).
- The clean-env install result (no conflict with `httpx2`, `openai` or `instructor`).
- Python `>=3.11` confirmed against the SDK's `requires_python`.
- Confirmation that `MANIFEST.in` needs no change.
