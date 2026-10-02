<!-- task-pipeline: validated -->
# Task 3.2: PyAIToolkit classifier construction and config resolution (card 3610201c)

Parent: Story 3 "facade and factory" (42134774), milestone e3bd09dc. Authority: `docs/superpowers/specs/2026-10-01-classifier-port-design.md` (present in the main checkout at `/home/mtts/Code/libs/py-ai-toolkit`, not tracked in this worktree), sections "Config" and "Constructor and behavior", plus Decision A (env resolved at init) and Decision B (activate on a passed config OR a non-empty `CLASSIFIER_API_KEY`). This card narrows that design; it does not change it.

## Base

Build on top of the 3.1 work (branch `m-classifier/task-3-1-feat-create-01df4db2`, commit fa48f8c), which this worktree already contains: `ClassifierConfig` in `py_ai_toolkit/core/domain/classifier.py` (all fields `str | None = None`, no env defaults), `ClassifierPort` exported from `py_ai_toolkit/core/ports`, and `create_classifier(api_key, model="jev-latest", base_url=None)` in `py_ai_toolkit/factories.py`, which lazily imports `JevAdapter` and raises the `[jev]` install-hint `ImportError` when the SDK is missing.

## Scope

Files: `py_ai_toolkit/core/toolkit.py` and `tests/unit/test_classifier.py` only.

- `PyAIToolkit.__init__` gains one last, optional keyword: `classifier_config: ClassifierConfig | None = None`. Existing parameters and their order are unchanged.
- New attribute `self.classifier: ClassifierPort | None`.
- Imports: `create_classifier` added to the existing `from py_ai_toolkit.factories import (...)` block; `ClassifierConfig` from `py_ai_toolkit.core.domain.classifier`; `ClassifierPort` from `py_ai_toolkit.core.ports`. `core/` must not import `jev_adapter` or `typesafe_sdk`.
- `LLMConfig` and the existing LLM client, prompt formatter, model handler and alternative-client construction are untouched.

## Observable behavior

Resolution happens inside `__init__` (never at import time). With `cfg` being `classifier_config`, or a value with all fields `None` when it is `None`:

- `api_key = cfg.api_key or os.getenv("CLASSIFIER_API_KEY")`
- `model = cfg.model or os.getenv("CLASSIFIER_MODEL") or "jev-latest"`
- `base_url = cfg.base_url or os.getenv("CLASSIFIER_BASE_URL")`

Activation:

- If `classifier_config is not None` or the resolved `api_key` is non-empty, `self.classifier = create_classifier(api_key, model, base_url)`.
- Otherwise `self.classifier = None` and construction behaves exactly as it does today.

Because resolution is at init, env vars set after `py_ai_toolkit` is imported are honored.

## Error paths

- `classifier_config` passed but no key resolvable (config key empty/None and `CLASSIFIER_API_KEY` unset or empty): raise `ValueError("ClassifierConfig requires an api_key or CLASSIFIER_API_KEY.")` before calling the factory.
- Key resolved but the `jev` extra is missing: `create_classifier`'s `ImportError` (install hint, chained) propagates out of `__init__` unchanged (fail fast, no wrapping, no fallback to `None`).
- Any other exception from `create_classifier` propagates unchanged.

## Out of scope

Sibling 3.3 (dd20073d): `classify()`, `aclose()`, firing `before_classify`/`after_classify` hooks, the unconfigured-call `ClassifierAdapterError` guard, the empty-questions `ValueError`, and exports in `py_ai_toolkit/__init__.py`. Already-done work: hook contexts (1.3), the adapter (2.x), the factory (3.1). Story-wide exclusions: LLM-backed or fallback adapter, chat/stream/embed on the classifier, normalization or derived confidence, streaming, sync client, own retry logic, ori integration.

## Tests

Placement rule: the classifier spec's "Testing" section (no standalone testing standard exists in this repo) puts facade, config-resolution and factory tests in `tests/unit/test_classifier.py`, using a fake `ClassifierPort` or a patched factory and no network. Every test below is therefore **unit tier, appended to the existing `tests/unit/test_classifier.py`** (do not recreate or duplicate the file; no integration or live tests). Style: plain pytest functions with `monkeypatch`/`unittest.mock`. Each test constructs the toolkit with an `LLMConfig(api_key=..., model=...)` (or sets `LLM_*` env) so the existing LLM client builds, and clears or sets `CLASSIFIER_API_KEY`, `CLASSIFIER_MODEL` and `CLASSIFIER_BASE_URL` via `monkeypatch` so ambient env cannot leak in. Unless stated, the factory is patched where toolkit looks it up, `monkeypatch.setattr("py_ai_toolkit.core.toolkit.create_classifier", fake)`, with `fake` recording its args and returning a `ClassifierPort` fake.

1. No config, classifier env cleared: `toolkit.classifier is None`, the fake factory is not called, and `llm_client`, `prompt_formatter`, `model_handler` are still built. (unit, `tests/unit/test_classifier.py`)
2. No config, `CLASSIFIER_API_KEY` (and model/base URL) set via `monkeypatch.setenv` after import: the factory receives the env values and `toolkit.classifier` is the object it returned. (unit, `tests/unit/test_classifier.py`)
3. Explicit `ClassifierConfig(api_key, model, base_url)` with all three env vars also set to different values: the factory receives the config values for each field. (unit, `tests/unit/test_classifier.py`)
4. Model fallback: config/key present without a model and `CLASSIFIER_MODEL` set gives the env model; with `CLASSIFIER_MODEL` cleared gives `"jev-latest"`. Base URL with nothing set is passed as `None`. (unit, `tests/unit/test_classifier.py`)
5. `ClassifierConfig()` with no key and classifier env cleared raises `ValueError` with the exact message `"ClassifierConfig requires an api_key or CLASSIFIER_API_KEY."`, and the factory is not called. (unit, `tests/unit/test_classifier.py`)
6. Empty `CLASSIFIER_API_KEY=""` with no config: `toolkit.classifier is None` (empty key does not activate). (unit, `tests/unit/test_classifier.py`)
7. Missing extra: real factory (not patched), a non-empty key (config or env), `monkeypatch.delitem(sys.modules, "py_ai_toolkit.adapters.jev_adapter", raising=False)` and `monkeypatch.setitem(sys.modules, "typesafe_sdk", None)` as in the existing `test_create_classifier_without_sdk_raises_install_hint`: `PyAIToolkit(...)` raises `ImportError` whose message is the install hint. (unit, `tests/unit/test_classifier.py`)

Use `pytest.importorskip("typesafe_sdk")` only if a test needs the real SDK; none of the above should.

---

# PyAIToolkit Classifier Construction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `PyAIToolkit` an optional `classifier` (a `ClassifierPort`) that is built at init from a `ClassifierConfig` and/or `CLASSIFIER_*` env vars via `create_classifier`, or left `None` when nothing configures it.

**Architecture:** All resolution lives in `PyAIToolkit.__init__` (`py_ai_toolkit/core/toolkit.py`), after the existing LLM parts are built. Task 1 adds the env-only activation path (no new parameter yet). Task 2 adds the `classifier_config` keyword, config-over-env precedence, and the missing-key `ValueError`. The factory is the only thing that touches `jev_adapter`; `core/` imports only `create_classifier`, `ClassifierConfig` and `ClassifierPort`.

**Tech Stack:** Python 3.11, pydantic v2, pytest with `monkeypatch`, uv.

**Spec:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-2-feat-pyaitoolkit-3610201c/docs/superpowers/specs/task-3-2-feat-pyaitoolkit-3610201c-design.md` (prepended above). Upstream authority: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md`, sections "Config" and "Constructor and behavior".

## Global Constraints

- Only two files change: `py_ai_toolkit/core/toolkit.py` and `tests/unit/test_classifier.py`.
- New parameter is last and optional: `classifier_config: ClassifierConfig | None = None`; existing parameters (`main_model_config`, `alternative_models_configs`) keep their order.
- New attribute: `self.classifier: ClassifierPort | None`.
- Resolution at init, never at import: `api_key = cfg.api_key or os.getenv("CLASSIFIER_API_KEY")`; `model = cfg.model or os.getenv("CLASSIFIER_MODEL") or "jev-latest"`; `base_url = cfg.base_url or os.getenv("CLASSIFIER_BASE_URL")`.
- Activation: `classifier_config is not None` or resolved `api_key` non-empty → `create_classifier(api_key, model, base_url)`; otherwise `None`.
- Exact error message: `ValueError("ClassifierConfig requires an api_key or CLASSIFIER_API_KEY.")`, raised before the factory is called.
- `ImportError` (and any other exception) from `create_classifier` propagates from `__init__` unwrapped.
- `core/` must never import `jev_adapter` or `typesafe_sdk`. `LLMConfig` is untouched.
- Do not implement `classify()`, `aclose()`, hook firing, the unconfigured-call guard, the empty-questions guard, or `py_ai_toolkit/__init__.py` exports (sibling 3.3, dd20073d).
- All tests are unit tests appended to `tests/unit/test_classifier.py`; no network, no `importorskip`.
- Verification: `uv run pytest tests/ --ignore=tests/test_run_task.py` and `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F`.

## Review Focus

- Config passes `api_key=""` while `CLASSIFIER_API_KEY` is set: the env key should be used (empty string is "not given", per the `or` chain), not the empty one. Pinned in Task 2 (`test_toolkit_empty_config_fields_fall_back_to_env`).
- Config passes `model=""` / `base_url=""`: should fall back to env then `"jev-latest"` / `None`, not send an empty model to Jev. Pinned in Task 2 (same test).
- `ClassifierConfig()` with `CLASSIFIER_API_KEY=""` (set but empty): must raise the `ValueError`, not call the factory with `""`. Pinned in Task 2 (`test_toolkit_config_with_empty_env_key_raises_value_error`).
- A non-ImportError failure inside `create_classifier` (e.g. SDK client constructor raising): must surface unchanged from `PyAIToolkit(...)`, never swallowed into `classifier = None`. Pinned in Task 2 (`test_toolkit_propagates_factory_errors_unchanged`).
- Classifier activation must not disturb the LLM side: with a classifier active, `llm_client` still uses the `LLMConfig` model and `alternative_llm_clients` is still built. Pinned in Task 1 (`test_toolkit_env_key_set_after_import_activates_classifier` asserts the LLM client model and alternative clients).

---

## File Structure

- Modify `py_ai_toolkit/core/toolkit.py` — imports (lines 8-30) and `PyAIToolkit.__init__` (lines 40-63). Responsibility unchanged: the facade wires ports built by factories.
- Modify `tests/unit/test_classifier.py` — add two imports to the top import block (lines 11-34) and append a `# PyAIToolkit classifier construction` section after the last test (`test_package_imports_survive_missing_sdk`, ending at line 571). Existing helpers reused: `MinimalClassifier` (line 413), `INSTALL_HINT` (line 469).

---

### Task 1: Env-only classifier activation on `PyAIToolkit`

**Files:**
- Modify: `py_ai_toolkit/core/toolkit.py:26-30` (factory imports), `py_ai_toolkit/core/toolkit.py:1-30` (add `ClassifierPort` import), `py_ai_toolkit/core/toolkit.py:62-63` (end of `__init__`)
- Test: `tests/unit/test_classifier.py` (imports at lines 32-34; append at end of file)

**Interfaces:**
- Consumes: `py_ai_toolkit.factories.create_classifier(api_key: str, model: str = "jev-latest", base_url: str | None = None) -> ClassifierPort` (3.1); `ClassifierPort` from `py_ai_toolkit.core.ports`; test helpers `MinimalClassifier`, `INSTALL_HINT` already in `tests/unit/test_classifier.py`.
- Produces: attribute `PyAIToolkit.classifier: ClassifierPort | None`; toolkit calls `create_classifier(api_key, model, base_url)` positionally (looked up as `py_ai_toolkit.core.toolkit.create_classifier`). Test helpers `CLASSIFIER_ENV`, `LLM_CONFIG`, `_clear_classifier_env(monkeypatch)`, `RecordingFactory` (with `.calls: list[tuple[str | None, str, str | None]]` and `.returned: MinimalClassifier`), `_patch_factory(monkeypatch) -> RecordingFactory` that Task 2 reuses.

- [ ] **Step 1: Add the test-file imports**

In `tests/unit/test_classifier.py`, replace lines 32-34:

```python
from py_ai_toolkit.core.domain.errors import ClassifierAdapterError, LLMAdapterError
from py_ai_toolkit.core.ports.classifier_port import ClassifierPort
from py_ai_toolkit.core.ports.llm_port import LLMPort
```

with:

```python
from py_ai_toolkit.core.domain.errors import ClassifierAdapterError, LLMAdapterError
from py_ai_toolkit.core.domain.schemas import LLMConfig
from py_ai_toolkit.core.ports.classifier_port import ClassifierPort
from py_ai_toolkit.core.ports.llm_port import LLMPort
from py_ai_toolkit.core.toolkit import PyAIToolkit
```

- [ ] **Step 2: Write the failing tests (append to the end of `tests/unit/test_classifier.py`)**

```python


# PyAIToolkit classifier construction

CLASSIFIER_ENV = ("CLASSIFIER_API_KEY", "CLASSIFIER_MODEL", "CLASSIFIER_BASE_URL")
LLM_CONFIG = LLMConfig(api_key="test-llm-key", model="test-llm-model")


def _clear_classifier_env(monkeypatch):
    for name in CLASSIFIER_ENV:
        monkeypatch.delenv(name, raising=False)


class RecordingFactory:
    def __init__(self):
        self.calls = []
        self.returned = MinimalClassifier()

    def __call__(self, api_key, model="jev-latest", base_url=None):
        self.calls.append((api_key, model, base_url))
        return self.returned


def _patch_factory(monkeypatch):
    factory = RecordingFactory()
    monkeypatch.setattr("py_ai_toolkit.core.toolkit.create_classifier", factory)
    return factory


def test_toolkit_without_classifier_config_or_env_has_no_classifier(monkeypatch):
    _clear_classifier_env(monkeypatch)
    factory = _patch_factory(monkeypatch)

    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)

    assert toolkit.classifier is None
    assert factory.calls == []
    assert isinstance(toolkit.llm_client, LLMPort)
    assert toolkit.llm_client._model == "test-llm-model"
    assert toolkit.prompt_formatter is not None
    assert toolkit.model_handler is not None


def test_toolkit_env_key_set_after_import_activates_classifier(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    monkeypatch.setenv("CLASSIFIER_MODEL", "env-model")
    monkeypatch.setenv("CLASSIFIER_BASE_URL", "https://env.invalid")
    factory = _patch_factory(monkeypatch)

    toolkit = PyAIToolkit(
        main_model_config=LLM_CONFIG,
        alternative_models_configs=[
            LLMConfig(api_key="alt-key", model="alt-model", embedding_model="")
        ],
    )

    assert factory.calls == [("env-key", "env-model", "https://env.invalid")]
    assert toolkit.classifier is factory.returned
    assert toolkit.llm_client._model == "test-llm-model"
    assert len(toolkit.alternative_llm_clients) == 1


def test_toolkit_empty_env_key_does_not_activate_classifier(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.setenv("CLASSIFIER_API_KEY", "")
    factory = _patch_factory(monkeypatch)

    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)

    assert toolkit.classifier is None
    assert factory.calls == []


def test_toolkit_env_key_without_jev_extra_raises_install_hint(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    monkeypatch.delitem(
        sys.modules, "py_ai_toolkit.adapters.jev_adapter", raising=False
    )
    monkeypatch.setitem(sys.modules, "typesafe_sdk", None)

    with pytest.raises(ImportError) as exc_info:
        PyAIToolkit(main_model_config=LLM_CONFIG)

    assert str(exc_info.value) == INSTALL_HINT
    assert isinstance(exc_info.value.__cause__, ImportError)
```

Note: `alternative_models_configs` entries go through `create_llm_client(**config.model_dump())`, so the `LLMConfig` passed must have only fields `create_llm_client` accepts (it does: all five `LLMConfig` fields match its parameters).

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_classifier.py -k "toolkit" -v`
Expected: FAIL — the first three fail with `AttributeError: 'PyAIToolkit' object has no attribute 'classifier'` or `AttributeError: <module 'py_ai_toolkit.core.toolkit'> has no attribute 'create_classifier'` (raised by `monkeypatch.setattr`); `test_toolkit_env_key_without_jev_extra_raises_install_hint` fails with `Failed: DID NOT RAISE <class 'ImportError'>`.

- [ ] **Step 4: Write the minimal implementation**

In `py_ai_toolkit/core/toolkit.py`, add the `ClassifierPort` import directly after the `from py_ai_toolkit.core.hooks import (...)` block (after line 25):

```python
from py_ai_toolkit.core.ports import ClassifierPort
```

Replace the factory import block (lines 26-30):

```python
from py_ai_toolkit.factories import (
    create_llm_client,
    create_model_handler,
    create_prompt_formatter,
)
```

with:

```python
from py_ai_toolkit.factories import (
    create_classifier,
    create_llm_client,
    create_model_handler,
    create_prompt_formatter,
)
```

Replace the last two lines of `__init__` (lines 62-63):

```python
        self.prompt_formatter = create_prompt_formatter()
        self.model_handler = create_model_handler()
```

with:

```python
        self.prompt_formatter = create_prompt_formatter()
        self.model_handler = create_model_handler()

        classifier_api_key = os.getenv("CLASSIFIER_API_KEY")
        classifier_model = os.getenv("CLASSIFIER_MODEL") or "jev-latest"
        classifier_base_url = os.getenv("CLASSIFIER_BASE_URL")
        self.classifier: ClassifierPort | None = None
        if classifier_api_key:
            self.classifier = create_classifier(
                classifier_api_key, classifier_model, classifier_base_url
            )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_classifier.py -v`
Expected: PASS (all existing domain/port/factory tests plus the four new `toolkit` tests).

- [ ] **Step 6: Run the full suite and lint**

Run: `uv run pytest tests/ --ignore=tests/test_run_task.py`
Expected: PASS.

Run: `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F`
Expected: `All checks passed!` (if it reports pre-existing findings in files inherited from earlier m-classifier branches, confirm none point at lines this task changed in `py_ai_toolkit/core/toolkit.py` or the appended section of `tests/unit/test_classifier.py`).

Also confirm the boundary: `grep -nE "jev_adapter|typesafe_sdk" py_ai_toolkit/core/toolkit.py` prints nothing.

- [ ] **Step 7: Commit**

```bash
git add py_ai_toolkit/core/toolkit.py tests/unit/test_classifier.py
git commit -m "feat: build PyAIToolkit classifier from CLASSIFIER_* env at init"
```

---

### Task 2: `classifier_config` keyword, config-over-env precedence, missing-key error

**Files:**
- Modify: `py_ai_toolkit/core/toolkit.py` (imports block lines 8-15 area; `__init__` signature lines 40-44; the classifier block added in Task 1)
- Test: `tests/unit/test_classifier.py` (append at end of file)

**Interfaces:**
- Consumes: from Task 1 — `PyAIToolkit.classifier`, toolkit's positional call `create_classifier(api_key, model, base_url)`, test helpers `LLM_CONFIG`, `_clear_classifier_env(monkeypatch)`, `RecordingFactory`, `_patch_factory(monkeypatch) -> RecordingFactory`, `INSTALL_HINT`. `ClassifierConfig(api_key: str | None = None, model: str | None = None, base_url: str | None = None)` from `py_ai_toolkit.core.domain.classifier` (already imported at the top of the test file).
- Produces: `PyAIToolkit.__init__(self, main_model_config: LLMConfig | None = None, alternative_models_configs: list[LLMConfig] | None = None, classifier_config: ClassifierConfig | None = None)`. Sibling 3.3 builds `classify()`/`aclose()` on `self.classifier`.

- [ ] **Step 1: Write the failing tests (append to the end of `tests/unit/test_classifier.py`)**

```python


MISSING_KEY_MESSAGE = "ClassifierConfig requires an api_key or CLASSIFIER_API_KEY."


def test_toolkit_explicit_config_beats_env_for_every_field(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    monkeypatch.setenv("CLASSIFIER_MODEL", "env-model")
    monkeypatch.setenv("CLASSIFIER_BASE_URL", "https://env.invalid")
    factory = _patch_factory(monkeypatch)

    toolkit = PyAIToolkit(
        main_model_config=LLM_CONFIG,
        classifier_config=ClassifierConfig(
            api_key="cfg-key",
            model="cfg-model",
            base_url="https://cfg.invalid",
        ),
    )

    assert factory.calls == [("cfg-key", "cfg-model", "https://cfg.invalid")]
    assert toolkit.classifier is factory.returned


def test_toolkit_model_falls_back_to_env_model(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.setenv("CLASSIFIER_MODEL", "env-model")
    factory = _patch_factory(monkeypatch)

    PyAIToolkit(
        main_model_config=LLM_CONFIG,
        classifier_config=ClassifierConfig(api_key="cfg-key"),
    )

    assert factory.calls == [("cfg-key", "env-model", None)]


def test_toolkit_model_falls_back_to_jev_latest_and_base_url_to_none(monkeypatch):
    _clear_classifier_env(monkeypatch)
    factory = _patch_factory(monkeypatch)

    PyAIToolkit(
        main_model_config=LLM_CONFIG,
        classifier_config=ClassifierConfig(api_key="cfg-key"),
    )

    assert factory.calls == [("cfg-key", "jev-latest", None)]


def test_toolkit_empty_config_fields_fall_back_to_env(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    monkeypatch.setenv("CLASSIFIER_MODEL", "env-model")
    monkeypatch.setenv("CLASSIFIER_BASE_URL", "https://env.invalid")
    factory = _patch_factory(monkeypatch)

    PyAIToolkit(
        main_model_config=LLM_CONFIG,
        classifier_config=ClassifierConfig(api_key="", model="", base_url=""),
    )

    assert factory.calls == [("env-key", "env-model", "https://env.invalid")]


def test_toolkit_config_without_key_raises_value_error(monkeypatch):
    _clear_classifier_env(monkeypatch)
    factory = _patch_factory(monkeypatch)

    with pytest.raises(ValueError) as exc_info:
        PyAIToolkit(main_model_config=LLM_CONFIG, classifier_config=ClassifierConfig())

    assert str(exc_info.value) == MISSING_KEY_MESSAGE
    assert factory.calls == []


def test_toolkit_config_with_empty_env_key_raises_value_error(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.setenv("CLASSIFIER_API_KEY", "")
    factory = _patch_factory(monkeypatch)

    with pytest.raises(ValueError) as exc_info:
        PyAIToolkit(
            main_model_config=LLM_CONFIG,
            classifier_config=ClassifierConfig(model="cfg-model"),
        )

    assert str(exc_info.value) == MISSING_KEY_MESSAGE
    assert factory.calls == []


def test_toolkit_propagates_factory_errors_unchanged(monkeypatch):
    _clear_classifier_env(monkeypatch)
    inner = RuntimeError("SDK client construction failed")

    def failing_factory(api_key, model="jev-latest", base_url=None):
        raise inner

    monkeypatch.setattr(
        "py_ai_toolkit.core.toolkit.create_classifier", failing_factory
    )

    with pytest.raises(RuntimeError) as exc_info:
        PyAIToolkit(
            main_model_config=LLM_CONFIG,
            classifier_config=ClassifierConfig(api_key="cfg-key"),
        )

    assert exc_info.value is inner


def test_toolkit_config_key_without_jev_extra_raises_install_hint(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.delitem(
        sys.modules, "py_ai_toolkit.adapters.jev_adapter", raising=False
    )
    monkeypatch.setitem(sys.modules, "typesafe_sdk", None)

    with pytest.raises(ImportError) as exc_info:
        PyAIToolkit(
            main_model_config=LLM_CONFIG,
            classifier_config=ClassifierConfig(api_key="cfg-key"),
        )

    assert str(exc_info.value) == INSTALL_HINT
    assert isinstance(exc_info.value.__cause__, ImportError)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_classifier.py -k "toolkit" -v`
Expected: the four Task 1 tests PASS; the eight new tests FAIL. Each new test fails because `__init__` does not accept the keyword: `TypeError: PyAIToolkit.__init__() got an unexpected keyword argument 'classifier_config'` (the ValueError/RuntimeError/ImportError tests surface that `TypeError` instead of the expected exception, which pytest reports as a failure, not a pass).

- [ ] **Step 3: Write the minimal implementation**

In `py_ai_toolkit/core/toolkit.py`, add the `ClassifierConfig` import directly above the existing `from py_ai_toolkit.core.domain.errors import WorkflowError` line (line 8):

```python
from py_ai_toolkit.core.domain.classifier import ClassifierConfig
```

Replace the `__init__` signature (lines 40-44 originally):

```python
    def __init__(
        self,
        main_model_config: LLMConfig | None = None,
        alternative_models_configs: list[LLMConfig] | None = None,
    ):
```

with:

```python
    def __init__(
        self,
        main_model_config: LLMConfig | None = None,
        alternative_models_configs: list[LLMConfig] | None = None,
        classifier_config: ClassifierConfig | None = None,
    ):
```

Replace the classifier block added in Task 1:

```python
        classifier_api_key = os.getenv("CLASSIFIER_API_KEY")
        classifier_model = os.getenv("CLASSIFIER_MODEL") or "jev-latest"
        classifier_base_url = os.getenv("CLASSIFIER_BASE_URL")
        self.classifier: ClassifierPort | None = None
        if classifier_api_key:
            self.classifier = create_classifier(
                classifier_api_key, classifier_model, classifier_base_url
            )
```

with:

```python
        resolved_config = (
            classifier_config if classifier_config is not None else ClassifierConfig()
        )
        classifier_api_key = resolved_config.api_key or os.getenv("CLASSIFIER_API_KEY")
        classifier_model = (
            resolved_config.model or os.getenv("CLASSIFIER_MODEL") or "jev-latest"
        )
        classifier_base_url = resolved_config.base_url or os.getenv(
            "CLASSIFIER_BASE_URL"
        )
        self.classifier: ClassifierPort | None = None
        if classifier_config is not None and not classifier_api_key:
            raise ValueError(
                "ClassifierConfig requires an api_key or CLASSIFIER_API_KEY."
            )
        if classifier_config is not None or classifier_api_key:
            self.classifier = create_classifier(
                classifier_api_key, classifier_model, classifier_base_url
            )
```

Note: `resolved_config.base_url or os.getenv(...)` yields `None` when neither is set (`"" or None` is `None`), matching the spec's "passed as `None`".

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_classifier.py -v`
Expected: PASS (all existing tests plus all twelve `toolkit` tests).

- [ ] **Step 5: Run the full verification gate**

Run: `uv run pytest tests/ --ignore=tests/test_run_task.py`
Expected: PASS.

Run: `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F`
Expected: `All checks passed!` (any E501 hits must not point at lines added by this card; the code above keeps every line under 88 characters).

Confirm the boundary and scope: `grep -nE "jev_adapter|typesafe_sdk" py_ai_toolkit/core/toolkit.py` prints nothing, and `git diff --name-only m-classifier/task-3-1-feat-create-01df4db2...HEAD` lists exactly `py_ai_toolkit/core/toolkit.py` and `tests/unit/test_classifier.py`.

- [ ] **Step 6: Commit**

```bash
git add py_ai_toolkit/core/toolkit.py tests/unit/test_classifier.py
git commit -m "feat: accept classifier_config on PyAIToolkit with config-over-env resolution"
```
