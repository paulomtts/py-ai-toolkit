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
