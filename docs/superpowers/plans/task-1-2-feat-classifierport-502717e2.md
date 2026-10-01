<!-- task-pipeline: validated -->
# Task 1.2 — feat: ClassifierPort and ClassifierAdapterError (card 502717e2)

Parent: story eaac0cc9 "Story 1: classifier core types and port" (milestone e3bd09dc). Governing design: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md` (gitignored; read by absolute path). This card narrows that design; it adds no new decisions.

Depends on 1.1 (dc5d79a4, done): `py_ai_toolkit/core/domain/classifier.py` (`Question`, `ClassifierResponse`, ...) and `tests/unit/test_classifier.py` are already present in this worktree's branch. Blocks 1.3 (5b5a930e, hooks).

## Scope

1. `py_ai_toolkit/core/domain/errors.py` — add `ClassifierAdapterError(Exception)`, the same shape as `LLMAdapterError` / `FormatterAdapterError` in that file: a docstring ("Exception raised when an error occurs in the classifier adapter."), `__init__(self, message: str = "")`, `super().__init__(message)`, `self.message = message`. Append it after `FormatterAdapterError`.
2. New `py_ai_toolkit/core/ports/classifier_port.py` — `class ClassifierPort(ABC)`, styled like `core/ports/llm_port.py` (class docstring, method docstrings, `pass` bodies):
   - `@abstractmethod async def classify(self, state: str | dict[str, Any] | list[Any], questions: Mapping[str, Question]) -> ClassifierResponse`
   - non-abstract `async def aclose(self) -> None` with the docstring "Release network resources. Default: no-op." It does nothing and returns `None` (decision C).
   - Imports: `ABC`, `abstractmethod`; `Mapping` from `collections.abc`; `Any` from `typing`; `Question`, `ClassifierResponse` from `py_ai_toolkit.core.domain.classifier`. Nothing else.
3. `py_ai_toolkit/core/ports/__init__.py` — add `from .classifier_port import ClassifierPort` and add `"ClassifierPort"` to `__all__`. Keep the existing three exports.
4. Append tests to the existing `tests/unit/test_classifier.py` (see below).

## Out of scope / must not touch

- The port is separate from `LLMPort` (decision 1). It has no `chat`, `stream`, `embed`, `embed_batch` or `asend`, and it does not subclass `LLMPort`.
- `core/` imports no adapters and no `typesafe_sdk`. There is no SDK dependency and no network access.
- No export from `py_ai_toolkit/__init__.py`. Do not edit `adapters/`, `factories.py`, `toolkit.py`, `core/hooks.py` (owned by 1.3), `tests/unit/test_hooks.py` or `pyproject.toml`.
- These are excluded for the whole milestone: Jev or LLM-backed/fallback adapter, normalization or derived confidence, streaming, sync client, own retry logic, ori integration.
- No validation logic in the port. `classify` is abstract, and the inputs are checked by adapters and the facade later.

## Observable behavior

- `ClassifierPort()`, or a subclass that does not implement `classify`, raises `TypeError` when instantiated (ABC).
- A subclass that implements only `classify` can be instantiated. Its `classify` returns the subclass's `ClassifierResponse`, and its inherited `aclose()` awaits to `None` without error.
- `ClassifierAdapterError("boom").message == "boom"`, and `str(err) == "boom"`. `ClassifierAdapterError()` defaults `.message` to `""`. It is an `Exception` subclass and not a subclass of `LLMAdapterError`.
- `from py_ai_toolkit.core.ports import ClassifierPort` works.

## Tests

All of these go in tier `tests/unit/`, appended to `tests/unit/test_classifier.py`. The test placement rule from the exploration applies: the repo's only test tier is `tests/unit/`, and the governing spec puts fake-port, domain-type and hook tests there. These tests need no network and no SDK, so they do not go in the live tier (`tests/test_run_task.py`, or the planned `tests/live/`). Add a section-comment header (e.g. `# --- ClassifierPort / ClassifierAdapterError ---`) and move the new imports to the top of the file, matching its existing style of plain pytest functions. Run async calls with `asyncio.run(...)` only (not `get_event_loop()`, which `test_hooks.py` uses but which is deprecated and can raise on newer Pythons when no loop exists). Do not add `@pytest.mark.asyncio`.

- `test_classifier_port_cannot_be_instantiated_without_classify` (unit): both `ClassifierPort()` and an empty subclass raise `TypeError`.
- `test_classifier_port_minimal_subclass_classifies` (unit): a subclass that implements only `classify` returns a fixed `ClassifierResponse`. Instantiation succeeds and awaiting `classify("state", {"q": NoulQuestion()})` returns that response.
- `test_classifier_port_aclose_default_is_noop` (unit): on the minimal subclass, awaiting `aclose()` returns `None` and raises nothing.
- `test_classifier_adapter_error_carries_message` (unit): `.message` and `str()` equal the given message, the default is `""`, and the error can be raised and caught as `Exception`.
- `test_classifier_port_exported_from_ports_package` (unit, optional): `py_ai_toolkit.core.ports.ClassifierPort is` the class from `classifier_port`, and `"ClassifierPort"` is in `__all__`.

## Verification

Use the card's verification field as supplied. CI runs `pytest tests/ --ignore=tests/test_run_task.py`, and the new tests and the existing `tests/unit/` suite must pass under it.

---

# ClassifierPort and ClassifierAdapterError Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `ClassifierAdapterError` exception and the `ClassifierPort` ABC (abstract `classify`, no-op `aclose`) to py-ai-toolkit's core, exported from `py_ai_toolkit.core.ports`, with unit tests.

**Architecture:** Hexagonal core: `core/domain/errors.py` gets one new exception class shaped like `LLMAdapterError`. A new port module `core/ports/classifier_port.py` defines an ABC that depends only on the 1.1 domain types in `core/domain/classifier.py`. It is fully separate from `LLMPort`. The ports package re-exports it. No adapter, facade, factory or hook changes.

**Tech Stack:** Python >= 3.11, pydantic v2 (domain types from 1.1), `abc`, pytest (plain functions, async run via `asyncio.run`), uv, ruff (default rule set; no ruff config in repo).

**Spec:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-1-2-feat-classifierport-502717e2/docs/superpowers/specs/task-1-2-feat-classifierport-502717e2-design.md` (prepended above). Governing design: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md`.

All paths below are relative to the worktree root `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-1-2-feat-classifierport-502717e2`. Run every command from that directory. The branch `m-classifier/task-1-2-feat-classifierport-502717e2` is cut from `m-classifier/task-1-1-feat-classifier-dc5d79a4`, so `py_ai_toolkit/core/domain/classifier.py` and `tests/unit/test_classifier.py` exist; nothing from 1.3 or later exists.

## Global Constraints

- The port is separate from `LLMPort`: no `chat`, `stream`, `embed`, `embed_batch` or `asend`; does not subclass `LLMPort`.
- `core/` imports no adapters and no `typesafe_sdk`; no SDK dependency, no network access.
- No export from `py_ai_toolkit/__init__.py`.
- Do not edit `adapters/`, `factories.py`, `toolkit.py`, `core/hooks.py`, `tests/unit/test_hooks.py`, `pyproject.toml`.
- Milestone-wide exclusions: Jev or LLM-backed/fallback adapter, normalization or derived confidence, streaming, sync client, own retry logic, ori integration.
- No validation logic in the port; `classify` is abstract.
- Decision C: `aclose` is non-abstract, default no-op, docstring exactly "Release network resources. Default: no-op."
- `ClassifierAdapterError` docstring: "Exception raised when an error occurs in the classifier adapter."
- Tests: only in `tests/unit/test_classifier.py` (append; do not recreate), plain pytest functions, imports at the top of the file, async via `asyncio.run(...)` only, no `@pytest.mark.asyncio`.
- Verification commands: `uv run pytest tests/ --ignore=tests/test_run_task.py` and `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check`.

## Review Focus

- A caller wrapping an SDK failure with `raise ClassifierAdapterError(msg) from exc` expects the original exception on `__cause__` and the message on `.message`; pinned in Task 1's error test.
- Code that does `except LLMAdapterError` must NOT swallow classifier errors (separate hierarchies, decision 1); pinned in Task 1's error test.
- `state` arrives as any of `str`, `dict`, `list` (JSON forms) and the questions mapping must reach the subclass's `classify` unchanged (the port adds no validation or copying); pinned in Task 2 by `test_classifier_port_passes_state_and_questions_through`.
- Someone implementing the port expects only `classify` to be required (the abstract set is exactly `{"classify"}`) and no LLM methods to be inherited; pinned in Task 2 by `test_classifier_port_is_separate_from_llm_port`.
- A subclass that overrides `aclose` (as `JevAdapter` will) expects its override to run instead of the no-op; pinned in Task 2 by `test_classifier_port_aclose_override_is_used`.

---

### Task 1: ClassifierAdapterError

**Files:**
- Modify: `py_ai_toolkit/core/domain/errors.py` (append after `FormatterAdapterError`, currently ending at line 28)
- Test: `tests/unit/test_classifier.py` (imports block lines 1-21; append new section at end of file, after line 345)

**Interfaces:**
- Consumes: nothing new.
- Produces: `py_ai_toolkit.core.domain.errors.ClassifierAdapterError(Exception)` with `__init__(self, message: str = "")` and attribute `message: str`.

- [ ] **Step 1: Add the import to the top of the test file**

In `tests/unit/test_classifier.py`, directly after the closing `)` of the `from py_ai_toolkit.core.domain.classifier import (...)` block (line 21), add:

```python
from py_ai_toolkit.core.domain.errors import ClassifierAdapterError, LLMAdapterError
```

- [ ] **Step 2: Append the failing test section at the end of the file**

Append to the end of `tests/unit/test_classifier.py`:

```python


# ClassifierAdapterError


def test_classifier_adapter_error_carries_message():
    err = ClassifierAdapterError("boom")

    assert err.message == "boom"
    assert str(err) == "boom"
    assert ClassifierAdapterError().message == ""
    assert isinstance(err, Exception)
    assert not isinstance(err, LLMAdapterError)
    with pytest.raises(Exception) as caught:
        raise ClassifierAdapterError("raised")
    assert caught.value.message == "raised"


def test_classifier_adapter_error_keeps_cause_and_escapes_llm_handler():
    cause = RuntimeError("sdk failure")

    with pytest.raises(ClassifierAdapterError) as caught:
        try:
            try:
                raise cause
            except RuntimeError as exc:
                raise ClassifierAdapterError("Jev request failed") from exc
        except LLMAdapterError:
            pytest.fail("ClassifierAdapterError must not be caught as LLMAdapterError")

    assert caught.value.__cause__ is cause
    assert caught.value.message == "Jev request failed"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_classifier.py -v`
Expected: collection ERROR for the whole file with `ImportError: cannot import name 'ClassifierAdapterError' from 'py_ai_toolkit.core.domain.errors'`.

- [ ] **Step 4: Implement ClassifierAdapterError**

Append to `py_ai_toolkit/core/domain/errors.py` after `FormatterAdapterError`:

```python


class ClassifierAdapterError(Exception):
    """
    Exception raised when an error occurs in the classifier adapter.
    """

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_classifier.py -v`
Expected: all tests PASS, including `test_classifier_adapter_error_carries_message` and `test_classifier_adapter_error_keeps_cause_and_escapes_llm_handler`.

- [ ] **Step 6: Commit**

```bash
git add py_ai_toolkit/core/domain/errors.py tests/unit/test_classifier.py
git commit -m "feat: add ClassifierAdapterError"
```

---

### Task 2: ClassifierPort and its package export

**Files:**
- Create: `py_ai_toolkit/core/ports/classifier_port.py`
- Modify: `py_ai_toolkit/core/ports/__init__.py` (lines 1-5)
- Test: `tests/unit/test_classifier.py` (imports block at top; append new section at end of file)

**Interfaces:**
- Consumes: `Question`, `ClassifierResponse`, `ClassifierUsage`, `NoulAnswer`, `NoulQuestion`, `ChoiceQuestion` from `py_ai_toolkit.core.domain.classifier` (1.1); `LLMPort` from `py_ai_toolkit.core.ports.llm_port` (test only).
- Produces: `py_ai_toolkit.core.ports.classifier_port.ClassifierPort(ABC)` with
  - `@abstractmethod async def classify(self, state: str | dict[str, Any] | list[Any], questions: Mapping[str, Question]) -> ClassifierResponse`
  - `async def aclose(self) -> None` (non-abstract no-op)
  - re-exported as `py_ai_toolkit.core.ports.ClassifierPort`, with `"ClassifierPort"` in `py_ai_toolkit.core.ports.__all__`.

- [ ] **Step 1: Add the imports to the top of the test file**

In `tests/unit/test_classifier.py`, change the first line from:

```python
import importlib.util
```

to:

```python
import asyncio
import importlib.util
```

Then, directly after the `from py_ai_toolkit.core.domain.errors import ClassifierAdapterError, LLMAdapterError` line added in Task 1, add:

```python
from py_ai_toolkit.core import ports as ports_package
from py_ai_toolkit.core.ports.classifier_port import ClassifierPort
from py_ai_toolkit.core.ports.llm_port import LLMPort
```

- [ ] **Step 2: Append the failing test section at the end of the file**

Append to the end of `tests/unit/test_classifier.py`:

```python


# ClassifierPort

FIXED_RESPONSE = ClassifierResponse(
    model="fake-classifier",
    answers={"q": NoulAnswer(noul=0.5)},
    usage=ClassifierUsage(input_tokens=3, output_tokens=1),
)


class MinimalClassifier(ClassifierPort):
    async def classify(self, state, questions):
        self.received = (state, questions)
        return FIXED_RESPONSE


def test_classifier_port_cannot_be_instantiated_without_classify():
    class EmptyClassifier(ClassifierPort):
        pass

    with pytest.raises(TypeError):
        ClassifierPort()
    with pytest.raises(TypeError):
        EmptyClassifier()


def test_classifier_port_minimal_subclass_classifies():
    classifier = MinimalClassifier()

    result = asyncio.run(classifier.classify("state", {"q": NoulQuestion()}))

    assert result is FIXED_RESPONSE


@pytest.mark.parametrize("state", JSON_FORMS[:3])
def test_classifier_port_passes_state_and_questions_through(state):
    classifier = MinimalClassifier()
    questions = {"is_spam": NoulQuestion(), "topic": ChoiceQuestion(criteria={"a": None})}

    asyncio.run(classifier.classify(state, questions))

    received_state, received_questions = classifier.received
    assert received_state is state
    assert received_questions is questions


def test_classifier_port_aclose_default_is_noop():
    classifier = MinimalClassifier()

    assert asyncio.run(classifier.aclose()) is None


def test_classifier_port_aclose_override_is_used():
    class ClosingClassifier(MinimalClassifier):
        async def aclose(self):
            self.closed = True

    classifier = ClosingClassifier()

    asyncio.run(classifier.aclose())

    assert classifier.closed is True


def test_classifier_port_is_separate_from_llm_port():
    assert ClassifierPort.__abstractmethods__ == frozenset({"classify"})
    assert not issubclass(ClassifierPort, LLMPort)
    for name in ("chat", "stream", "embed", "embed_batch", "asend"):
        assert not hasattr(ClassifierPort, name)


def test_classifier_port_exported_from_ports_package():
    assert ports_package.ClassifierPort is ClassifierPort
    assert "ClassifierPort" in ports_package.__all__
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_classifier.py -v`
Expected: collection ERROR for the whole file with `ModuleNotFoundError: No module named 'py_ai_toolkit.core.ports.classifier_port'`.

- [ ] **Step 4: Create the port module**

Create `py_ai_toolkit/core/ports/classifier_port.py`:

```python
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from py_ai_toolkit.core.domain.classifier import ClassifierResponse, Question


class ClassifierPort(ABC):
    """
    Abstract base class for classifier ports.
    """

    @abstractmethod
    async def classify(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: Mapping[str, Question],
    ) -> ClassifierResponse:
        """
        Answers structured questions about a state.

        Args:
            state (str | dict[str, Any] | list[Any]): The state to classify
            questions (Mapping[str, Question]): The questions to answer, by name

        Returns:
            ClassifierResponse: The answers from the classifier
        """
        pass

    async def aclose(self) -> None:
        """Release network resources. Default: no-op."""
        pass
```

- [ ] **Step 5: Run the tests to verify only the export test fails**

Run: `uv run pytest tests/unit/test_classifier.py -v`
Expected: every test PASSES except `test_classifier_port_exported_from_ports_package`, which FAILS with `AttributeError: module 'py_ai_toolkit.core.ports' has no attribute 'ClassifierPort'`.

- [ ] **Step 6: Export the port from the ports package**

Replace the full contents of `py_ai_toolkit/core/ports/__init__.py` with:

```python
from .classifier_port import ClassifierPort
from .formatter_port import FormatterPort
from .llm_port import LLMPort
from .modeller_port import ModellerPort

__all__ = ["LLMPort", "FormatterPort", "ModellerPort", "ClassifierPort"]
```

- [ ] **Step 7: Run the tests to verify they all pass**

Run: `uv run pytest tests/unit/test_classifier.py -v`
Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add py_ai_toolkit/core/ports/classifier_port.py py_ai_toolkit/core/ports/__init__.py tests/unit/test_classifier.py
git commit -m "feat: add ClassifierPort and export it from core.ports"
```

---

### Task 3: Full verification

**Files:**
- None created or modified (only if a check below finds a problem in files from Tasks 1-2).

**Interfaces:**
- Consumes: everything from Tasks 1-2.
- Produces: nothing new.

- [ ] **Step 1: Run the full CI test suite**

Run: `uv run pytest tests/ --ignore=tests/test_run_task.py`
Expected: all tests PASS (existing `tests/unit/` suite plus the new tests); no errors.

- [ ] **Step 2: Run ruff on changed Python files**

Run: `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check`
Expected: `All checks passed!`. (The list also includes 1.1's files because this branch stacks on 1.1, which is not yet on `main`.)

- [ ] **Step 3: Confirm the must-not-touch files are untouched by this card**

Run: `git diff --name-only m-classifier/task-1-1-feat-classifier-dc5d79a4...HEAD`
Expected: exactly these four paths (plus the spec/plan docs under `docs/superpowers/` if they are committed):

```
py_ai_toolkit/core/domain/errors.py
py_ai_toolkit/core/ports/__init__.py
py_ai_toolkit/core/ports/classifier_port.py
tests/unit/test_classifier.py
```

No `py_ai_toolkit/__init__.py`, `adapters/`, `factories.py`, `toolkit.py`, `core/hooks.py`, `tests/unit/test_hooks.py` or `pyproject.toml`.

- [ ] **Step 4: Confirm core has no adapter or SDK imports**

Run: `grep -rnE "typesafe_sdk|py_ai_toolkit\.adapters|from \.\.\.?adapters" py_ai_toolkit/core/`
Expected: no output.

- [ ] **Step 5: Commit (only if Steps 1-4 required a fix)**

```bash
git add py_ai_toolkit/core/domain/errors.py py_ai_toolkit/core/ports/__init__.py py_ai_toolkit/core/ports/classifier_port.py tests/unit/test_classifier.py
git commit -m "fix: address verification findings for ClassifierPort"
```
