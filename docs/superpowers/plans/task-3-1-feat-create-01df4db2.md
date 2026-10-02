<!-- task-pipeline: validated -->
# Task 3.1 — feat: `create_classifier` factory (card 01df4db2)

Parent: Story 3 "facade and factory" (42134774), milestone e3bd09dc. Governing design: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md` (sections "Architecture", "Facade and config" → Factory, "Testing"). This card narrows that design; it does not extend it.

## Scope

Files touched: `py_ai_toolkit/factories.py` and `tests/unit/test_classifier.py` (append only; the existing ~459 lines of domain-type tests stay as they are). Nothing else.

Add to `py_ai_toolkit/factories.py`:

```python
def create_classifier(
    api_key: str,
    model: str = "jev-latest",
    base_url: str | None = None,
) -> ClassifierPort:
```

- `ClassifierPort` joins the existing import line: `from py_ai_toolkit.core.ports import ClassifierPort, FormatterPort, LLMPort, ModellerPort`.
- Docstring in the same Args/Returns/Raises style as the other factories in the file. It documents the `ImportError` raised when the extra is missing.
- Inside the function body only: `from py_ai_toolkit.adapters.jev_adapter import JevAdapter`. `jev_adapter.py` imports `typesafe_sdk` at module top, so this import is the point that fails when the SDK is missing.
- On `ImportError` from that import, raise `ImportError("The Jev classifier requires the 'jev' extra: pip install 'py-ai-toolkit[jev]'.")` from the caught exception, so `__cause__` is the original error.
- On success, return `JevAdapter(api_key=api_key, model=model, base_url=base_url)` with no other processing.

## Observable behavior

- SDK installed: `create_classifier("key")` returns a `JevAdapter` instance, which is a `ClassifierPort`, with `model` defaulting to `"jev-latest"` and `base_url` defaulting to `None`. Values are passed through unchanged.
- SDK absent: calling `create_classifier(...)` raises the `ImportError` above, with `__cause__` set. It raises when called, not when the module is imported.
- SDK absent: `import py_ai_toolkit.adapters` and `import py_ai_toolkit.factories` still succeed.

## Constraints

- Nothing under `core/` may import `jev_adapter` or `typesafe_sdk`. `factories.py` is the only place that references `jev_adapter`, and only lazily, inside `create_classifier`. It has no top-level import of it.
- `py_ai_toolkit/adapters/__init__.py` stays unchanged. `JevAdapter` is not imported there and is not added to `__all__`.
- Do not touch `core/toolkit.py`, `py_ai_toolkit/__init__.py` or `core/hooks.py`. Those belong to siblings 3.2 (3610201c: `classifier_config`, env resolution, `self.classifier`, `ValueError` for a config without a key) and 3.3 (dd20073d: `classify`/`aclose`, hook firing, package exports).
- Out of scope:
  - LLM-backed or fallback classifier adapters
  - chat, stream or embed on the classifier
  - normalization or derived confidence
  - streaming
  - a sync client
  - retry logic of our own
  - ori integration

## Tests

Placement rule: the governing spec's "Testing" table puts "Missing extra" and factory tests in `tests/unit/test_classifier.py`. This repo has only the `tests/unit/` tier, written in plain pytest with `unittest.mock` and `pytest-asyncio`. All tests below therefore go in **`tests/unit/test_classifier.py` (unit tier)**. No integration or e2e tier exists, and this card must not create one. CI runs `pytest tests/ --ignore=tests/test_run_task.py`.

Do not put a module-level `pytest.importorskip("typesafe_sdk")` in `test_classifier.py`, because it would skip the existing domain tests. Guard per test instead.

1. **Factory returns a ClassifierPort when the SDK is present** (unit, `test_classifier.py`). Call `pytest.importorskip("typesafe_sdk")` inside the test. Then `create_classifier("key")` is an instance of `ClassifierPort`, and its `_model` is `"jev-latest"`. A second call with an explicit `model` and `base_url` shows those values are passed through.
2. **Missing extra raises ImportError with install hint** (unit, `test_classifier.py`).
   - Call `monkeypatch.delitem(sys.modules, "py_ai_toolkit.adapters.jev_adapter", raising=False)` first. Without it, the lazy import hits the cached module and the test passes vacuously.
   - Then call `monkeypatch.setitem(sys.modules, "typesafe_sdk", None)`.
   - `create_classifier("key")` must raise `ImportError` whose message contains `py-ai-toolkit[jev]`, and `exc.__cause__` must not be `None`.
3. **Package imports survive a missing SDK** (unit, `test_classifier.py`). With `typesafe_sdk` blocked, `import py_ai_toolkit.adapters` and `import py_ai_toolkit.factories` both succeed. Run them in a subprocess (`sys.executable -c ...`) that blocks `typesafe_sdk` through `sys.modules["typesafe_sdk"] = None` before importing. This is the same subprocess approach `test_jev_adapter.py` already uses, and it avoids the stale-cache problem that `importlib.reload` has.

Verification: `pytest tests/unit/test_classifier.py` passes. To run test 1 for real, the worktree's `uv` env needs the `jev` extra (`typesafe-sdk>=0.6.0`). Without it, test 1 skips and tests 2 and 3 still run.

---

# `create_classifier` Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `create_classifier(api_key, model="jev-latest", base_url=None) -> ClassifierPort` to `py_ai_toolkit/factories.py`. It lazily builds a `JevAdapter` and raises an install-hint `ImportError` when the `jev` extra is missing.

**Architecture:** `factories.py` is the composition seam. It is the only module allowed to reference `py_ai_toolkit.adapters.jev_adapter`, and only via an import inside the function body, so importing `py_ai_toolkit.adapters` or `py_ai_toolkit.factories` never loads `typesafe_sdk`. The `try` block wraps only the import statement. Construction errors from `JevAdapter` propagate unchanged and are never relabeled as a missing extra.

**Tech Stack:** Python 3, plain pytest, `monkeypatch`, `subprocess`, uv, ruff. The optional SDK is `typesafe-sdk>=0.6.0` via the `jev` extra.

**Spec:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-1-feat-create-01df4db2/docs/superpowers/specs/task-3-1-feat-create-01df4db2-design.md` (reproduced above). Governing design: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md`. It is gitignored, so read it by absolute path.

**Worktree / branch:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-1-feat-create-01df4db2` on `m-classifier/task-3-1-feat-create-01df4db2`, cut from `m-classifier/task-2-3-feat-jevadapter-1ada6fbf`. That base already has the following, and this plan relies on nothing else:
- `py_ai_toolkit/adapters/jev_adapter.py`. `JevAdapter.__init__(self, api_key, model="jev-latest", base_url=None)` is at lines 148-159. It stores `self._model` and builds `AsyncTypeSafeClient(api_key=..., model=..., base_url=...)`, a name imported at module top from `typesafe_sdk`.
- `py_ai_toolkit/core/ports/__init__.py`, which exports `ClassifierPort`.
- the `jev` and `dev` extras in `pyproject.toml`.

No sibling (3.2, 3.3) code exists on this branch.

**Environment note:** a plain `uv run` does not install the `jev` extra. Without it, `typesafe_sdk` is not importable in a fresh worktree `.venv`, so the SDK-present tests would silently skip. Every test command below therefore uses `uv run --extra dev --extra jev ...`. This is the repo verification command `uv run pytest tests/ --ignore=tests/test_run_task.py` with the extras added. If a run reports the SDK-present tests as `SKIPPED`, the step has failed. Run `uv sync --extra dev --extra jev` and rerun.

## Global Constraints

- Signature exactly: `create_classifier(api_key: str, model: str = "jev-latest", base_url: str | None = None) -> ClassifierPort`.
- Error message exactly: `The Jev classifier requires the 'jev' extra: pip install 'py-ai-toolkit[jev]'.` It is raised `from exc`, so `__cause__` is the original `ImportError`.
- `py_ai_toolkit/factories.py` has no top-level import of `py_ai_toolkit.adapters.jev_adapter` or `typesafe_sdk`.
- Nothing under `py_ai_toolkit/core/` imports `jev_adapter` or `typesafe_sdk`.
- `py_ai_toolkit/adapters/__init__.py` is unchanged, and `JevAdapter` stays out of `__all__`.
- Do not touch `py_ai_toolkit/core/toolkit.py`, `py_ai_toolkit/__init__.py`, or `py_ai_toolkit/core/hooks.py`.
- Files changed by this card: only `py_ai_toolkit/factories.py` and `tests/unit/test_classifier.py`. Append to the test file and keep its existing tests.
- No module-level `pytest.importorskip("typesafe_sdk")` in `tests/unit/test_classifier.py`.
- Out of scope:
  - LLM-backed or fallback adapters
  - chat/stream/embed on the classifier
  - normalization or derived confidence
  - streaming
  - a sync client
  - our own retry logic
  - ori integration
- Lint gate: `ruff check --select E,F` runs over every changed `.py` file in full, with the default line length of 88. No ruff config exists in `pyproject.toml`. `factories.py` already has two docstring lines over 88 columns (lines 16-17, in `create_llm_client`). They must be rewrapped with the same words, or the gate fails on this card's diff.

## Review Focus

1. An `ImportError` raised while *constructing* the adapter, after the import succeeded, must propagate as-is. It must not be relabeled as "requires the 'jev' extra". This pins that the `try` wraps only the import. Test: `test_create_classifier_does_not_relabel_construction_errors`.
2. Calling the factory a second time after a missing-SDK failure must raise the same install hint again. It must not pick up a stale, partially initialised module. Test: the two-iteration loop in `test_create_classifier_without_sdk_raises_install_hint`.
3. Defaults must actually reach the SDK client: `model="jev-latest"` and `base_url=None`. Checking only the adapter's `_model` is not enough. Test: `calls` assertion in `test_create_classifier_returns_classifier_port_with_defaults`.
4. Importing `py_ai_toolkit.factories` must not eagerly load `py_ai_toolkit.adapters.jev_adapter`, even when the SDK is installed. A top-level import would defeat the optional extra for every user. Test: the `not in sys.modules` assertion in `test_package_imports_survive_missing_sdk`.
5. The install-hint message must match exactly. Users copy the `pip install` command from it. Test: `str(exc_info.value) == INSTALL_HINT` in `test_create_classifier_without_sdk_raises_install_hint`.

---

### Task 1: `create_classifier` factory with lazy Jev import and install-hint error

**Files:**
- Modify: `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-1-feat-create-01df4db2/tests/unit/test_classifier.py`. Change the import block at lines 1-12 and append new tests after line 459, the end of the file.
- Modify: `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-1-feat-create-01df4db2/py_ai_toolkit/factories.py`. Change the import at line 2 and the docstring at lines 16-17, and append the new function after line 51, the end of the file.
- Test: `tests/unit/test_classifier.py` (unit tier, the only tier in this repo).

**Interfaces:**
- Consumes: `py_ai_toolkit.adapters.jev_adapter.JevAdapter(api_key: str, model: str = "jev-latest", base_url: str | None = None)`. It also uses that module's top-level name `AsyncTypeSafeClient`, which the tests monkeypatch, and `py_ai_toolkit.core.ports.ClassifierPort`.
- Produces: `py_ai_toolkit.factories.create_classifier(api_key: str, model: str = "jev-latest", base_url: str | None = None) -> ClassifierPort`. Sibling 3.2 will call it from `core/toolkit.py`.

- [ ] **Step 1: Add the test-file imports**

In `tests/unit/test_classifier.py`, replace lines 1-12:

```python
import asyncio
import importlib.util
import inspect
import typing
from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from py_ai_toolkit.core import ports as ports_package
from py_ai_toolkit.core.domain import classifier as classifier_module
```

with:

```python
import asyncio
import importlib.util
import inspect
import subprocess
import sys
import typing
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from py_ai_toolkit import factories
from py_ai_toolkit.core import ports as ports_package
from py_ai_toolkit.core.domain import classifier as classifier_module
```

The tests import `factories` as a module and do not use `from py_ai_toolkit.factories import create_classifier`. That way the missing function shows up as a per-test `AttributeError` during RED, and the existing domain tests in this file still collect and run.

- [ ] **Step 2: Append the failing tests**

Append to the end of `tests/unit/test_classifier.py`, after `test_classifier_port_exported_from_ports_package`:

```python


# create_classifier factory

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_HINT = (
    "The Jev classifier requires the 'jev' extra: pip install 'py-ai-toolkit[jev]'."
)


def _capture_sdk_client(monkeypatch):
    import py_ai_toolkit.adapters.jev_adapter as jev_adapter_module

    calls = []

    def fake_client(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(jev_adapter_module, "AsyncTypeSafeClient", fake_client)
    return jev_adapter_module, calls


def test_create_classifier_returns_classifier_port_with_defaults(monkeypatch):
    pytest.importorskip("typesafe_sdk")
    jev_adapter_module, calls = _capture_sdk_client(monkeypatch)

    classifier = factories.create_classifier("test-key")

    assert isinstance(classifier, ClassifierPort)
    assert isinstance(classifier, jev_adapter_module.JevAdapter)
    assert classifier._model == "jev-latest"
    assert calls == [
        {"api_key": "test-key", "model": "jev-latest", "base_url": None},
    ]


def test_create_classifier_passes_model_and_base_url_through(monkeypatch):
    pytest.importorskip("typesafe_sdk")
    _, calls = _capture_sdk_client(monkeypatch)

    classifier = factories.create_classifier(
        "other-key",
        model="jev-2026-09",
        base_url="https://example.invalid",
    )

    assert isinstance(classifier, ClassifierPort)
    assert classifier._model == "jev-2026-09"
    assert calls == [
        {
            "api_key": "other-key",
            "model": "jev-2026-09",
            "base_url": "https://example.invalid",
        },
    ]


def test_create_classifier_does_not_relabel_construction_errors(monkeypatch):
    pytest.importorskip("typesafe_sdk")
    import py_ai_toolkit.adapters.jev_adapter as jev_adapter_module

    inner = ImportError("raised while building the SDK client")

    def failing_client(**kwargs):
        raise inner

    monkeypatch.setattr(jev_adapter_module, "AsyncTypeSafeClient", failing_client)

    with pytest.raises(ImportError) as exc_info:
        factories.create_classifier("test-key")

    assert exc_info.value is inner


def test_create_classifier_without_sdk_raises_install_hint(monkeypatch):
    monkeypatch.delitem(
        sys.modules, "py_ai_toolkit.adapters.jev_adapter", raising=False
    )
    monkeypatch.setitem(sys.modules, "typesafe_sdk", None)

    for _ in range(2):
        with pytest.raises(ImportError) as exc_info:
            factories.create_classifier("test-key")

        assert str(exc_info.value) == INSTALL_HINT
        assert "py-ai-toolkit[jev]" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ImportError)


def test_package_imports_survive_missing_sdk():
    script = (
        "import sys; "
        "sys.modules['typesafe_sdk'] = None; "
        "import py_ai_toolkit.adapters, py_ai_toolkit.factories; "
        "assert callable(py_ai_toolkit.factories.create_classifier); "
        "assert 'py_ai_toolkit.adapters.jev_adapter' not in sys.modules"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
```

Notes for the implementer:
- `ClassifierPort` is already imported at the top of this file, from `py_ai_toolkit.core.ports.classifier_port`. It is the same class object the factory's return type refers to.
- `monkeypatch.delitem(..., raising=False)` evicts any `jev_adapter` module that earlier tests cached, for example the SDK-present tests above. Without the eviction, the lazy import would hit the cache and never touch the blocked `typesafe_sdk`. `monkeypatch` restores the evicted module afterwards, so later tests are unaffected.
- `monkeypatch.setattr` on `jev_adapter_module.AsyncTypeSafeClient` works because `JevAdapter.__init__` looks up `AsyncTypeSafeClient` as a module global at call time. The factory's lazy import returns that same cached module.
- The subprocess test is a guard: blocking the SDK must never break package import. Its `callable(...create_classifier)` assertion makes it fail during RED. Its `not in sys.modules` assertion pins the lazy import, Review Focus 4.

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-1-feat-create-01df4db2 && uv run --extra dev --extra jev pytest tests/unit/test_classifier.py -k "create_classifier or survive_missing_sdk" -v`

Expected: 5 tests FAIL and none are SKIPPED.
- The four in-process tests fail with `AttributeError: module 'py_ai_toolkit.factories' has no attribute 'create_classifier'`.
- `test_package_imports_survive_missing_sdk` fails on `assert result.returncode == 0`, and the captured stderr shows the same `AttributeError`.

If the SDK-present tests show `SKIPPED (could not import 'typesafe_sdk')`, the extras are missing. Run `uv sync --extra dev --extra jev`, then rerun.

- [ ] **Step 4: Confirm the existing domain tests still collect and pass**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-1-feat-create-01df4db2 && uv run --extra dev --extra jev pytest tests/unit/test_classifier.py -k "not create_classifier and not survive_missing_sdk" -q`

Expected: all pre-existing tests PASS, with no collection errors. This proves the import changes from Step 1 did not break the file.

- [ ] **Step 5: Implement `create_classifier`**

In `py_ai_toolkit/factories.py`, replace line 2:

```python
from py_ai_toolkit.core.ports import FormatterPort, LLMPort, ModellerPort
```

with:

```python
from py_ai_toolkit.core.ports import (
    ClassifierPort,
    FormatterPort,
    LLMPort,
    ModellerPort,
)
```

The single-line form would be 89 columns, which trips E501 at ruff's default limit of 88.

Then append to the end of the file, after `create_model_handler`:

```python


def create_classifier(
    api_key: str,
    model: str = "jev-latest",
    base_url: str | None = None,
) -> ClassifierPort:
    """
    Factory function to create a Jev classifier instance.

    Args:
        api_key (str): The Jev API key.
        model (str): The Jev model to classify with. Defaults to "jev-latest".
        base_url (Optional[str]): Jev API base URL override. Defaults to None.

    Returns:
        ClassifierPort: Configured classifier instance backed by JevAdapter

    Raises:
        ImportError: If the optional 'jev' extra (typesafe-sdk) is not installed
    """
    try:
        from py_ai_toolkit.adapters.jev_adapter import JevAdapter
    except ImportError as exc:
        raise ImportError(
            "The Jev classifier requires the 'jev' extra: "
            "pip install 'py-ai-toolkit[jev]'."
        ) from exc
    return JevAdapter(api_key=api_key, model=model, base_url=base_url)
```

The `return` statement must stay outside the `try`. Review Focus 1 depends on that.

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-1-feat-create-01df4db2 && uv run --extra dev --extra jev pytest tests/unit/test_classifier.py -k "create_classifier or survive_missing_sdk" -v`

Expected: 5 PASSED, 0 SKIPPED.

- [ ] **Step 7: Rewrap the two over-long pre-existing docstring lines in `factories.py`**

The lint gate checks the whole of every changed file, so lines 16-17 of `create_llm_client`'s docstring would fail E501. In `py_ai_toolkit/factories.py`, replace:

```python
        model (Optional[str]): The model to use for completions. Defaults to LLM_MODEL env var.
        embedding_model (Optional[str]): The model to use for embeddings. Defaults to EMBEDDING_MODEL env var.
```

with:

```python
        model (Optional[str]): The model to use for completions. Defaults to
            LLM_MODEL env var.
        embedding_model (Optional[str]): The model to use for embeddings.
            Defaults to EMBEDDING_MODEL env var.
```

Only the line breaks change; the wording stays the same.

- [ ] **Step 8: Verify the boundary constraints by inspection**

Run each of these:
- `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-1-feat-create-01df4db2 && git diff --name-only m-classifier/task-2-3-feat-jevadapter-1ada6fbf`

  Expected: exactly `py_ai_toolkit/factories.py` and `tests/unit/test_classifier.py`, plus this plan and spec under `docs/superpowers/` if they are tracked.
- Grep `py_ai_toolkit/core/` for `jev_adapter|typesafe_sdk`.

  Expected: no matches.
- Grep `py_ai_toolkit/adapters/__init__.py` for `Jev`.

  Expected: no matches.
- Grep `py_ai_toolkit/factories.py` for `jev_adapter`.

  Expected: exactly one match, the indented import inside `create_classifier`.

- [ ] **Step 9: Run the full verification gate**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-1-feat-create-01df4db2 && uv run --extra dev --extra jev pytest tests/ --ignore=tests/test_run_task.py -rs`

Expected:
- All tests pass.
- The `-rs` skip summary lists no skips from `tests/unit/test_classifier.py` or `tests/unit/test_jev_adapter.py`.
- Skips in `tests/live/` without `CLASSIFIER_API_KEY` are acceptable.

Then run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-1-feat-create-01df4db2 && git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F`

Expected: `All checks passed!`

`ruff` is not in the `dev` extra, so these commands use the `ruff` on `PATH` (verified: ruff 0.16.0 at `~/.local/bin/ruff`); do not wrap it in `uv run`. The command runs before the commit in Step 10, so `main...HEAD` does not yet include this card's uncommitted edits. Run it once more after Step 10 to cover them.

- [ ] **Step 10: Commit**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-1-feat-create-01df4db2
git add py_ai_toolkit/factories.py tests/unit/test_classifier.py
git commit -m "feat: add create_classifier factory with lazy Jev import"
git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F
```

Expected: the commit succeeds and the post-commit ruff run prints `All checks passed!`
