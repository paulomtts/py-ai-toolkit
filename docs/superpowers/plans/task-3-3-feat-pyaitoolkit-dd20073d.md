<!-- task-pipeline: validated -->
# Task 3.3 — feat: PyAIToolkit.classify and aclose (card dd20073d)

Parent story: 42134774 "Story 3: facade and factory" (milestone e3bd09dc). Blocked by 3.2 (3610201c, done). Milestone design: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md` (read by absolute path; gitignored). This spec narrows that design to one subtask.

## Base

This worktree (`m-classifier/task-3-3-feat-pyaitoolkit-dd20073d`) already contains the 3.2 work: domain types in `core/domain/classifier.py`, `ClassifierAdapterError` in `core/domain/errors.py`, `ClassifierPort` (abstract `classify`, default no-op `aclose`) in `core/ports/classifier_port.py`, `BeforeClassifyContext` / `AfterClassifyContext` and `Hooks.before_classify` / `Hooks.after_classify` in `core/hooks.py`, `factories.create_classifier`, and the `classifier_config` kwarg plus `self.classifier: ClassifierPort | None` in `core/toolkit.py`.

## Scope

Files touched: `py_ai_toolkit/core/toolkit.py`, `py_ai_toolkit/__init__.py`, `tests/unit/test_classifier.py`. Nothing else.

### 1. `PyAIToolkit.classify`

Signature: `async def classify(self, state: str | dict | list, questions: Mapping[str, Question], *, hooks: Hooks | None = None) -> ClassifierResponse`.

Behavior, in order:

1. If `self.classifier is None`, raise `ClassifierAdapterError("Classifier not configured: pass ClassifierConfig (or set CLASSIFIER_API_KEY) and install `py-ai-toolkit[jev]`.")`.
2. If `questions` is empty, raise `ValueError("questions must not be empty.")`.
3. Both guards run before any hook fires.
4. If `hooks` is set, `await _fire_hook(hooks.before_classify, BeforeClassifyContext(state=state, questions=questions, model=self.classifier._model))`.
5. Time the call with `time.perf_counter()`: `response = await self.classifier.classify(state, questions)`; `elapsed_ms = (perf_counter() - start) * 1000`.
6. If `hooks` is set, `await _fire_hook(hooks.after_classify, AfterClassifyContext(response=response, model=self.classifier._model, elapsed_ms=elapsed_ms, usage=response.usage))`.
7. Return `response` unchanged (same object).

Mirror the existing `embed` pattern (`if hooks: await _fire_hook(hooks.after_embed, ...)`). There is no try/except around the port call: when the classifier raises, the exception propagates unchanged and `after_classify` does not fire (`before_classify` already has). `_model` is read straight off the adapter, the same way `embed` reads `InstructorAdapter._model`. `ClassifierPort` declares no `_model`, so test fakes must set it. Add `BeforeClassifyContext` and `AfterClassifyContext` to the existing `core.hooks` import block. Add `Mapping`, plus `Question` and `ClassifierResponse` from `core.domain.classifier`, as needed. `core/` must not import `jev_adapter` or `typesafe_sdk`.

### 2. `PyAIToolkit.aclose`

`async def aclose(self) -> None`: if `self.classifier is not None`, `await self.classifier.aclose()`. Otherwise do nothing and don't raise. It does not close `llm_client` or anything else.

### 3. Public exports

In `py_ai_toolkit/__init__.py`, import and add to `__all__`: `ClassifierConfig`, `ClassifierResponse`, `ClassifierUsage`, `NoulQuestion`, `ChoiceQuestion`, `ScoreQuestion`, `NoulAnswer`, `ChoiceAnswer`, `ScoreAnswer`, `Question`, `Answer`, `ClassifierAdapterError`. Do not change `__version__` (stays 0.7.0).

## Out of scope

- LLM-backed or fallback classifier adapter.
- chat/stream/embed on the classifier.
- Normalization or derived confidence.
- Streaming, a sync client, own retry logic.
- ori integration.
- `LLMConfig` changes.
- 3.1/3.2 factory and construction logic.
- JevAdapter, domain types, port and hook definitions.
- docs/guide, `mkdocs.yml`, version bump, `test_hooks.py` frozen tests, live tests.

## Tests

Placement rule: the milestone spec's Testing section puts facade-with-fake-port tests in `tests/unit/test_classifier.py`, which is the plain pytest unit tier with no network. Every test below goes in that tier and file, appended to the existing file. They are plain sync pytest functions that drive coroutines through the file's existing `run(coro)` helper; never use `asyncio.run`, because it breaks `test_hooks.py`'s `get_event_loop()`. Reuse `FIXED_RESPONSE`, `MinimalClassifier`, `_clear_classifier_env`, `RecordingFactory` and `_patch_factory(monkeypatch)` where they fit. Add a `FakeClassifier(ClassifierPort)` that sets `self._model`, records `classify` args and `aclose` calls, and can be told to raise from `classify`. Get a toolkit with the fake either via `_patch_factory` or by assigning `toolkit.classifier = fake`.

All tests are unit tier (`tests/unit/test_classifier.py`):

1. `classify` returns the fake's response (identity with `FIXED_RESPONSE`), and the fake received exactly the `state` and `questions` passed in.
2. With hooks set, `before_classify` fires, then `after_classify`, recorded into one list. The contexts carry the right `state`/`questions`/`model`, and `response`/`usage`/`model` respectively.
3. `AfterClassifyContext.elapsed_ms >= 0`.
4. `hooks=None` (the default) works and returns the response.
5. Fake raises: the error propagates (`pytest.raises`), `before_classify` fired, and `after_classify` did not.
6. Unconfigured toolkit (`self.classifier is None`; env cleared via `monkeypatch.delenv` / `_clear_classifier_env`): `classify` raises `ClassifierAdapterError` with the exact message, and neither hook fires.
7. Empty `questions` (`{}`) raises `ValueError("questions must not be empty.")`, and neither hook fires.
8. `aclose` delegates: the fake records exactly one `aclose` call.
9. `aclose` with no classifier completes without error.
10. Exports: each new name imports from `py_ai_toolkit` and is listed in `__all__`.

## Verification

Run the suite via `uv` (CI equivalent: `pytest tests/ --ignore=tests/test_run_task.py` with `.[dev,jev]`). Lint only the changed `.py` files with `ruff check --select E,F --ignore E501`.

---

# PyAIToolkit.classify and aclose Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `PyAIToolkit.classify` (guarded, hook-instrumented pass-through to the configured `ClassifierPort`), `PyAIToolkit.aclose` (delegates to the classifier), and the public classifier exports in `py_ai_toolkit/__init__.py`.

**Architecture:** The facade method lives in `py_ai_toolkit/core/toolkit.py` and mirrors the existing `embed`/`chat` pattern: guards first, then `before_classify`, a `perf_counter`-timed port call, then `after_classify` on success only, returning the port's response object unchanged. `aclose` is a two-line delegation. The exports are plain re-imports in the package root. All tests are unit-tier, use a fake `ClassifierPort`, and touch no network.

**Tech Stack:** Python 3, pydantic, pytest (sync test functions that drive coroutines through the file's private-loop `run()` helper), `uv`, `ruff`.

**Spec:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-3-feat-pyaitoolkit-dd20073d/docs/superpowers/specs/task-3-3-feat-pyaitoolkit-dd20073d-design.md` (prepended above in full).

**Worktree:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-3-3-feat-pyaitoolkit-dd20073d`, branch `m-classifier/task-3-3-feat-pyaitoolkit-dd20073d`, cut from `m-classifier/task-3-2-feat-pyaitoolkit-3610201c`. All paths below are relative to this worktree. Run every command from the worktree root.

## Global Constraints

- Files touched: `py_ai_toolkit/core/toolkit.py`, `py_ai_toolkit/__init__.py`, `tests/unit/test_classifier.py`. Nothing else.
- Unconfigured message, verbatim: `Classifier not configured: pass ClassifierConfig (or set CLASSIFIER_API_KEY) and install `py-ai-toolkit[jev]`.`
- Empty-questions message, verbatim: `questions must not be empty.`
- Both guards run before any hook fires; the classifier-is-None guard runs first.
- No try/except around the port call: errors propagate unchanged, and `after_classify` does not fire.
- `aclose` does not close `llm_client` or anything else.
- `__version__` stays `"0.7.0"`.
- `core/` must not import `jev_adapter` or `typesafe_sdk`.
- Tests: unit tier only, in `tests/unit/test_classifier.py`, as plain sync pytest functions using the file's `run(coro)` helper. Never use `asyncio.run`.

## Review Focus

1. `state` given as a dict or a list (both allowed by the signature) must reach the classifier and `BeforeClassifyContext` as the same object, not just as a str. Task 1 pins this by parametrizing the pass-through test over str/dict/list.
2. A `Hooks` with only `after_classify` set (no `before_classify`) must not crash, and the one hook it has must still fire. Task 1 adds `test_classify_with_only_after_hook_fires_it`.
3. Calling `classify` with `hooks=None` on a classifier that has no `_model` attribute (for example the existing `MinimalClassifier`, or any third-party port) must still work, because `_model` is only needed for hook contexts. Task 1 adds `test_classify_without_hooks_does_not_need_model_attribute`, and the implementation reads `_model` only inside the `if hooks:` blocks.
4. An empty non-dict `Mapping` (for example `MappingProxyType({})`) must be rejected exactly like `{}`. Task 1 adds `test_classify_rejects_empty_non_dict_mapping`.
5. If `before_classify` raises, the classifier must not be called and the hook's exception must propagate. Task 1 adds `test_classify_before_hook_error_skips_classifier`. A related guard-order case, an unconfigured toolkit that also gets empty questions, must raise `ClassifierAdapterError`, not `ValueError`. Task 1 adds `test_classify_unconfigured_guard_runs_before_empty_check`.

---

### Task 1: `PyAIToolkit.classify`

**Files:**
- Modify: `py_ai_toolkit/core/toolkit.py:1-26` (imports) and append a method after `embed_batch` (currently ends at line 218)
- Test: `tests/unit/test_classifier.py` (imports at lines 1-36; append new section at end of file, after line 782)

**Interfaces:**
- Consumes (already on branch): `ClassifierPort` (`classify(state, questions)` abstract, `aclose()` default no-op) from `py_ai_toolkit.core.ports.classifier_port`; `BeforeClassifyContext(state, questions, model)`, `AfterClassifyContext(response, model, elapsed_ms, usage)`, `Hooks.before_classify`, `Hooks.after_classify`, `_fire_hook(hook, ctx)` from `py_ai_toolkit.core.hooks`; `ClassifierResponse`, `Question` from `py_ai_toolkit.core.domain.classifier`; `ClassifierAdapterError` from `py_ai_toolkit.core.domain.errors`; test helpers `run`, `FIXED_RESPONSE`, `MinimalClassifier`, `_clear_classifier_env`, `_patch_factory`, `LLM_CONFIG` in `tests/unit/test_classifier.py`.
- Produces: `async PyAIToolkit.classify(self, state: str | dict | list, questions: Mapping[str, Question], *, hooks: Hooks | None = None) -> ClassifierResponse`; test helpers `FakeClassifier(response=FIXED_RESPONSE, error=None, model="fake-model")` (attributes `_model`, `calls: list[tuple]`, `aclose_calls: int`), `_toolkit_with(monkeypatch, classifier) -> PyAIToolkit`, `_recording_hooks() -> tuple[Hooks, list]`, and constants `UNCONFIGURED_MESSAGE`, `QUESTIONS`. Task 2 uses `FakeClassifier`, `_toolkit_with` and `run`.

- [ ] **Step 1: Add the test imports**

In `tests/unit/test_classifier.py`, add `from types import MappingProxyType` after line 8 (`from pathlib import Path`), so the stdlib block reads:

```python
import asyncio
import importlib.util
import inspect
import subprocess
import sys
import typing
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any
```

Then add this line directly after `from py_ai_toolkit.core.domain.schemas import LLMConfig` (currently line 33):

```python
from py_ai_toolkit.core.hooks import AfterClassifyContext, BeforeClassifyContext, Hooks
```

- [ ] **Step 2: Write the failing tests**

Append to the end of `tests/unit/test_classifier.py`:

```python
# PyAIToolkit.classify

UNCONFIGURED_MESSAGE = (
    "Classifier not configured: pass ClassifierConfig (or set CLASSIFIER_API_KEY) "
    "and install `py-ai-toolkit[jev]`."
)
QUESTIONS = {"q": NoulQuestion()}


class FakeClassifier(ClassifierPort):
    def __init__(self, response=FIXED_RESPONSE, error=None, model="fake-model"):
        self._model = model
        self.response = response
        self.error = error
        self.calls = []
        self.aclose_calls = 0

    async def classify(self, state, questions):
        self.calls.append((state, questions))
        if self.error is not None:
            raise self.error
        return self.response

    async def aclose(self):
        self.aclose_calls += 1


def _toolkit_with(monkeypatch, classifier):
    _clear_classifier_env(monkeypatch)
    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)
    toolkit.classifier = classifier
    return toolkit


def _recording_hooks():
    events = []

    async def before(ctx):
        events.append(("before", ctx))

    async def after(ctx):
        events.append(("after", ctx))

    return Hooks(before_classify=before, after_classify=after), events


@pytest.mark.parametrize("state", ["plain text", {"text": "hi"}, ["a", "b"]])
def test_classify_returns_port_response_and_passes_args(monkeypatch, state):
    fake = FakeClassifier()
    toolkit = _toolkit_with(monkeypatch, fake)

    result = run(toolkit.classify(state, QUESTIONS))

    assert result is FIXED_RESPONSE
    assert len(fake.calls) == 1
    assert fake.calls[0][0] is state
    assert fake.calls[0][1] is QUESTIONS


def test_classify_fires_before_then_after_with_contexts(monkeypatch):
    fake = FakeClassifier(model="jev-test")
    toolkit = _toolkit_with(monkeypatch, fake)
    hooks, events = _recording_hooks()
    state = {"text": "hi"}

    result = run(toolkit.classify(state, QUESTIONS, hooks=hooks))

    assert [name for name, _ in events] == ["before", "after"]
    before_ctx = events[0][1]
    after_ctx = events[1][1]
    assert isinstance(before_ctx, BeforeClassifyContext)
    assert before_ctx.state is state
    assert before_ctx.questions is QUESTIONS
    assert before_ctx.model == "jev-test"
    assert isinstance(after_ctx, AfterClassifyContext)
    assert after_ctx.response is result
    assert after_ctx.usage is FIXED_RESPONSE.usage
    assert after_ctx.model == "jev-test"


def test_classify_reports_non_negative_elapsed_ms(monkeypatch):
    toolkit = _toolkit_with(monkeypatch, FakeClassifier())
    hooks, events = _recording_hooks()

    run(toolkit.classify("text", QUESTIONS, hooks=hooks))

    after_ctx = events[-1][1]
    assert isinstance(after_ctx.elapsed_ms, float)
    assert after_ctx.elapsed_ms >= 0


def test_classify_without_hooks_returns_response(monkeypatch):
    fake = FakeClassifier()
    toolkit = _toolkit_with(monkeypatch, fake)

    result = run(toolkit.classify("text", QUESTIONS))

    assert result is FIXED_RESPONSE
    assert len(fake.calls) == 1


def test_classify_without_hooks_does_not_need_model_attribute(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    factory = _patch_factory(monkeypatch)
    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)
    assert not hasattr(factory.returned, "_model")

    result = run(toolkit.classify("text", QUESTIONS))

    assert result is FIXED_RESPONSE


def test_classify_with_only_after_hook_fires_it(monkeypatch):
    toolkit = _toolkit_with(monkeypatch, FakeClassifier())
    seen = []

    async def after(ctx):
        seen.append(ctx)

    run(toolkit.classify("text", QUESTIONS, hooks=Hooks(after_classify=after)))

    assert len(seen) == 1
    assert seen[0].response is FIXED_RESPONSE


def test_classify_error_propagates_and_skips_after_hook(monkeypatch):
    error = ClassifierAdapterError("Jev request failed")
    toolkit = _toolkit_with(monkeypatch, FakeClassifier(error=error))
    hooks, events = _recording_hooks()

    with pytest.raises(ClassifierAdapterError) as exc_info:
        run(toolkit.classify("text", QUESTIONS, hooks=hooks))

    assert exc_info.value is error
    assert [name for name, _ in events] == ["before"]


def test_classify_before_hook_error_skips_classifier(monkeypatch):
    fake = FakeClassifier()
    toolkit = _toolkit_with(monkeypatch, fake)
    error = RuntimeError("hook failed")

    async def before(ctx):
        raise error

    with pytest.raises(RuntimeError) as exc_info:
        run(toolkit.classify("text", QUESTIONS, hooks=Hooks(before_classify=before)))

    assert exc_info.value is error
    assert fake.calls == []


def test_classify_unconfigured_raises_without_firing_hooks(monkeypatch):
    _clear_classifier_env(monkeypatch)
    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)
    assert toolkit.classifier is None
    hooks, events = _recording_hooks()

    with pytest.raises(ClassifierAdapterError) as exc_info:
        run(toolkit.classify("text", QUESTIONS, hooks=hooks))

    assert exc_info.value.message == UNCONFIGURED_MESSAGE
    assert str(exc_info.value) == UNCONFIGURED_MESSAGE
    assert events == []


def test_classify_unconfigured_guard_runs_before_empty_check(monkeypatch):
    _clear_classifier_env(monkeypatch)
    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)

    with pytest.raises(ClassifierAdapterError) as exc_info:
        run(toolkit.classify("text", {}))

    assert exc_info.value.message == UNCONFIGURED_MESSAGE


def test_classify_empty_questions_raises_without_firing_hooks(monkeypatch):
    fake = FakeClassifier()
    toolkit = _toolkit_with(monkeypatch, fake)
    hooks, events = _recording_hooks()

    with pytest.raises(ValueError) as exc_info:
        run(toolkit.classify("text", {}, hooks=hooks))

    assert str(exc_info.value) == "questions must not be empty."
    assert events == []
    assert fake.calls == []


def test_classify_rejects_empty_non_dict_mapping(monkeypatch):
    fake = FakeClassifier()
    toolkit = _toolkit_with(monkeypatch, fake)

    with pytest.raises(ValueError) as exc_info:
        run(toolkit.classify("text", MappingProxyType({})))

    assert str(exc_info.value) == "questions must not be empty."
    assert fake.calls == []
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `uv run pytest tests/unit/test_classifier.py -k "test_classify_" -v`
Expected: every selected test FAILS with `AttributeError: 'PyAIToolkit' object has no attribute 'classify'`.

- [ ] **Step 4: Extend the toolkit imports**

In `py_ai_toolkit/core/toolkit.py`, replace lines 1-26 (from `import os` through the closing `)` of the `core.hooks` import) with:

```python
import os
import random
import time
from collections.abc import Mapping
from typing import Any, AsyncGenerator, Type, TypeVar

from pydantic import BaseModel

from py_ai_toolkit.core.domain.classifier import (
    ClassifierConfig,
    ClassifierResponse,
    Question,
)
from py_ai_toolkit.core.domain.errors import ClassifierAdapterError, WorkflowError
from py_ai_toolkit.core.domain.schemas import (
    CompletionResponse,
    EmbeddingResponse,
    LLMConfig,
    SingleShotValidationConfig,
    ValidationConfig,
)
from py_ai_toolkit.core.hooks import (
    Hooks,
    _fire_hook,
    BeforeRenderContext,
    AfterRenderContext,
    BeforeLLMCallContext,
    AfterLLMCallContext,
    AfterEmbedContext,
    AfterEmbedBatchContext,
    BeforeClassifyContext,
    AfterClassifyContext,
)
```

Leave the `from py_ai_toolkit.core.ports import ClassifierPort` and `from py_ai_toolkit.factories import (...)` blocks that follow unchanged.

- [ ] **Step 5: Implement `classify`**

In `py_ai_toolkit/core/toolkit.py`, insert this method directly after the `embed_batch` method (after its `return responses` line) and before `async def chat(`:

```python
    async def classify(
        self,
        state: str | dict | list,
        questions: Mapping[str, Question],
        *,
        hooks: Hooks | None = None,
    ) -> ClassifierResponse:
        """
        Classifies a state against named questions using the configured classifier.

        Args:
            state: The text or JSON-like content to classify
            questions: Question name to question definition
            hooks (Hooks | None): Optional hooks to fire before/after the classifier call

        Returns:
            ClassifierResponse: The classifier's response, unchanged
        """
        if self.classifier is None:
            raise ClassifierAdapterError(
                "Classifier not configured: pass ClassifierConfig (or set "
                "CLASSIFIER_API_KEY) and install `py-ai-toolkit[jev]`."
            )
        if not questions:
            raise ValueError("questions must not be empty.")

        if hooks:
            await _fire_hook(
                hooks.before_classify,
                BeforeClassifyContext(
                    state=state,
                    questions=questions,
                    model=self.classifier._model,
                ),
            )

        start = time.perf_counter()
        response = await self.classifier.classify(state, questions)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if hooks:
            await _fire_hook(
                hooks.after_classify,
                AfterClassifyContext(
                    response=response,
                    model=self.classifier._model,
                    elapsed_ms=elapsed_ms,
                    usage=response.usage,
                ),
            )

        return response
```

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `uv run pytest tests/unit/test_classifier.py -k "test_classify_" -v`
Expected: all selected tests PASS.

- [ ] **Step 7: Run the whole unit file to check nothing regressed**

Run: `uv run pytest tests/unit/test_classifier.py tests/unit/test_hooks.py -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add py_ai_toolkit/core/toolkit.py tests/unit/test_classifier.py
git commit -m "feat: add PyAIToolkit.classify with guards and classify hooks"
```

---

### Task 2: `PyAIToolkit.aclose`

**Files:**
- Modify: `py_ai_toolkit/core/toolkit.py` (insert a method directly after `classify` from Task 1)
- Test: `tests/unit/test_classifier.py` (append at end of file)

**Interfaces:**
- Consumes: `FakeClassifier` (attribute `aclose_calls: int`), `_toolkit_with(monkeypatch, classifier)`, `run`, `_clear_classifier_env`, `LLM_CONFIG` from Task 1 / the existing test file; `ClassifierPort.aclose()`.
- Produces: `async PyAIToolkit.aclose(self) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to the end of `tests/unit/test_classifier.py`:

```python
# PyAIToolkit.aclose


def test_aclose_delegates_to_classifier(monkeypatch):
    fake = FakeClassifier()
    toolkit = _toolkit_with(monkeypatch, fake)

    result = run(toolkit.aclose())

    assert result is None
    assert fake.aclose_calls == 1


def test_aclose_without_classifier_is_noop(monkeypatch):
    _clear_classifier_env(monkeypatch)
    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)
    assert toolkit.classifier is None

    assert run(toolkit.aclose()) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_classifier.py -k "test_aclose_" -v`
Expected: both FAIL with `AttributeError: 'PyAIToolkit' object has no attribute 'aclose'`.

- [ ] **Step 3: Implement `aclose`**

In `py_ai_toolkit/core/toolkit.py`, insert directly after the `classify` method's `return response` line and before `async def chat(`:

```python
    async def aclose(self) -> None:
        """
        Releases the classifier's resources, if a classifier is configured.
        """
        if self.classifier is not None:
            await self.classifier.aclose()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_classifier.py -k "test_aclose_" -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add py_ai_toolkit/core/toolkit.py tests/unit/test_classifier.py
git commit -m "feat: add PyAIToolkit.aclose delegating to the classifier"
```

---

### Task 3: Public classifier exports

**Files:**
- Modify: `py_ai_toolkit/__init__.py:1-24`
- Test: `tests/unit/test_classifier.py` (append at end of file)

**Interfaces:**
- Consumes: `ClassifierConfig`, `ClassifierResponse`, `ClassifierUsage`, `NoulQuestion`, `ChoiceQuestion`, `ScoreQuestion`, `NoulAnswer`, `ChoiceAnswer`, `ScoreAnswer`, `Question`, `Answer` from `py_ai_toolkit.core.domain.classifier`; `ClassifierAdapterError` from `py_ai_toolkit.core.domain.errors` (all already imported at the top of the test file under the same names).
- Produces: these twelve names importable from `py_ai_toolkit` and listed in `py_ai_toolkit.__all__`.

- [ ] **Step 1: Write the failing test**

Append to the end of `tests/unit/test_classifier.py`. The package is imported inside the test so a missing name fails only this test, not the whole module:

```python
# Public exports

CLASSIFIER_EXPORTS = {
    "ClassifierConfig": ClassifierConfig,
    "ClassifierResponse": ClassifierResponse,
    "ClassifierUsage": ClassifierUsage,
    "NoulQuestion": NoulQuestion,
    "ChoiceQuestion": ChoiceQuestion,
    "ScoreQuestion": ScoreQuestion,
    "NoulAnswer": NoulAnswer,
    "ChoiceAnswer": ChoiceAnswer,
    "ScoreAnswer": ScoreAnswer,
    "Question": Question,
    "Answer": Answer,
    "ClassifierAdapterError": ClassifierAdapterError,
}


@pytest.mark.parametrize("name", sorted(CLASSIFIER_EXPORTS))
def test_classifier_names_exported_from_package(name):
    import py_ai_toolkit

    assert name in py_ai_toolkit.__all__
    assert getattr(py_ai_toolkit, name) is CLASSIFIER_EXPORTS[name]


def test_package_version_unchanged():
    import py_ai_toolkit

    assert py_ai_toolkit.__version__ == "0.7.0"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_classifier.py -k "test_classifier_names_exported_from_package or test_package_version_unchanged" -v`
Expected: the 12 `test_classifier_names_exported_from_package[...]` cases FAIL with `AssertionError` (name not in `__all__`); `test_package_version_unchanged` PASSES (it guards against a bump).

- [ ] **Step 3: Add the exports**

Replace the whole of `py_ai_toolkit/__init__.py` with:

```python
__version__ = "0.7.0"

from grafo import Chunk, Node, TreeExecutor

from .core.base import BaseWorkflow
from .core.domain.classifier import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    ClassifierConfig,
    ClassifierResponse,
    ClassifierUsage,
    NoulAnswer,
    NoulQuestion,
    Question,
    ScoreAnswer,
    ScoreQuestion,
)
from .core.domain.errors import ClassifierAdapterError, WorkflowError
from .core.domain.schemas import CompletionResponse, EmbeddingResponse, LLMConfig
from .core.domain.models import BaseIssue
from .core.hooks import Hooks
from .core.toolkit import PyAIToolkit

__all__ = [
    "PyAIToolkit",
    "CompletionResponse",
    "EmbeddingResponse",
    "Node",
    "TreeExecutor",
    "Chunk",
    "BaseWorkflow",
    "WorkflowError",
    "BaseIssue",
    "Hooks",
    "LLMConfig",
    "ClassifierConfig",
    "ClassifierResponse",
    "ClassifierUsage",
    "NoulQuestion",
    "ChoiceQuestion",
    "ScoreQuestion",
    "NoulAnswer",
    "ChoiceAnswer",
    "ScoreAnswer",
    "Question",
    "Answer",
    "ClassifierAdapterError",
]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_classifier.py -k "test_classifier_names_exported_from_package or test_package_version_unchanged" -v`
Expected: all PASS.

- [ ] **Step 5: Run the full verification gate**

Run: `uv run pytest tests/ --ignore=tests/test_run_task.py`
Expected: all PASS (live tests, if any, skip without a key).

Run: `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F --ignore E501`
Expected: `All checks passed!` (this covers every `.py` file the milestone branch changed against `main`, including this card's three files). `py_ai_toolkit/__init__.py` keeps its existing `__version__ = "0.7.0"` line above the imports. pycodestyle-style E402 allows module-level dunder assignments there, so it should not be flagged. If ruff does report E402 on `py_ai_toolkit/__init__.py`, append `  # noqa: E402` to each `from ... import` line in that file (the multi-line `from .core.domain.classifier import (` goes on its opening line), then rerun the command. Do not move or change `__version__`.

- [ ] **Step 6: Commit**

```bash
git add py_ai_toolkit/__init__.py tests/unit/test_classifier.py
git commit -m "feat: export classifier types and ClassifierAdapterError from package root"
```
