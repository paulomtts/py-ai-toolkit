<!-- task-pipeline: validated -->
# Task 1.3 (5b5a930e): before/after_classify hooks — design

Parent: Story 1 "classifier core types and port" (eaac0cc9), milestone e3bd09dc. Narrows the "Hooks" section of `docs/superpowers/specs/2026-10-01-classifier-port-design.md` (gitignored; read by absolute path from `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/`) to this one subtask. Blocked by 1.2 (502717e2), which is done.

## Scope

Files touched: only `py_ai_toolkit/core/hooks.py` and `tests/unit/test_hooks.py`.

In `py_ai_toolkit/core/hooks.py`:

- Import `Question`, `ClassifierResponse` and `ClassifierUsage` from `py_ai_toolkit.core.domain.classifier`. Sibling 1.1 created that module, and it is present on this card's branch: `Question` is the discriminated `Annotated[...]` alias at line 38, `ClassifierUsage` is at line 77 and `ClassifierResponse` at line 82. Also import `Mapping` (from `collections.abc` or `typing`).
- Add two frozen contexts after the existing ones, using `@dataclass(frozen=True)` like the existing ones:
  - `BeforeClassifyContext(state: str | dict[str, Any] | list[Any], questions: Mapping[str, Question], model: str)`
  - `AfterClassifyContext(response: ClassifierResponse, model: str, elapsed_ms: float, usage: ClassifierUsage)`
- Add the aliases `BeforeClassifyHook = Callable[[BeforeClassifyContext], Awaitable[None]]` and `AfterClassifyHook = Callable[[AfterClassifyContext], Awaitable[None]]` to the existing alias block.
- Append `before_classify: BeforeClassifyHook | None = None` and `after_classify: AfterClassifyHook | None = None` as the last two fields of the non-frozen `Hooks` dataclass, after `on_retry`. Do not reorder the existing fields, so that existing positional and keyword construction keeps working.

## Observable behavior

- Both contexts are immutable. Assigning to any field raises `dataclasses.FrozenInstanceError`.
- `AfterClassifyContext.usage` deliberately duplicates `response.usage`, to match `AfterEmbedContext`, where usage is a first-class field. The dataclass does not check that the two agree. Keeping them consistent is the caller's job, and that caller is the later `toolkit.classify` story.
- `Hooks()` has `before_classify is None` and `after_classify is None`. Every existing field keeps its default and position.
- Decision D (from the milestone): `after_classify` fires only on success, and there is no error or `on_classify_error` hook. This card only defines the types. It does not fire anything.
- The contexts do no validation of their own. They hold whatever they are given, as the existing contexts do.

## Error paths

None are introduced. The only failure mode this card adds is the `FrozenInstanceError` raised when someone mutates a context.

## Out of scope

- Wiring the hooks into `PyAIToolkit.classify` (`core/toolkit.py`). That belongs to a later story.
- Exporting the new names from `py_ai_toolkit/__init__.py`. Sibling 1.1 says "do not export yet".
- `docs/guide/hooks.md`, which is left to a later docs card.
- Any file owned by a sibling (`core/domain/classifier.py`, `core/domain/errors.py`, `core/ports/classifier_port.py`, `tests/unit/test_classifier.py`) or by a later story (`toolkit.py`, `jev_adapter.py`, `factories.py`, `pyproject.toml`).
- Anything in the story-level exclusions: adapters, SDK or network use in `core/`, normalization, streaming, a sync client, retry logic, and ori integration.

## Tests

Test-placement rule: this repo has no testing standards doc. The milestone spec's file table is the de facto rule, and it assigns pure-type and hook tests to `tests/unit/`, with "frozen-ness tests for the two new contexts" going in `tests/unit/test_hooks.py`. These are pure dataclasses, so neither the live tier nor any other tier applies. All of the tests below go in `tests/unit/test_hooks.py` (unit tier). Add the new names to the existing `from py_ai_toolkit.core.hooks import (...)` block, and import the classifier types from `py_ai_toolkit.core.domain.classifier`. Build the fixtures from the real domain types: `ClassifierUsage(input_tokens=..., output_tokens=...)`, a `ClassifierResponse(model=..., answers={...}, usage=...)` that holds a real answer such as `NoulAnswer(noul=0.5)`, and real question models such as `NoulQuestion()` or `ChoiceQuestion(criteria={...})`.

1. `test_before_classify_context_is_frozen` (unit): construct the context with a state, a `{"q": NoulQuestion()}` mapping and a model. Assigning to a field inside `pytest.raises(FrozenInstanceError)` must raise. This follows the existing pattern at lines 27-80.
2. `test_before_classify_context_holds_fields` (unit): the values passed to the constructor are readable back, including a dict state and a list state. This covers the `str | dict | list` state union.
3. `test_after_classify_context_is_frozen` (unit): construct the context with a real `ClassifierResponse`, a model, `elapsed_ms` and a `ClassifierUsage`. Assigning to a field must raise `FrozenInstanceError`.
4. `test_after_classify_context_carries_usage` (unit): `ctx.usage` and `ctx.response.usage` both hold the token counts that were passed in. This shows the duplication is intended.
5. `test_hooks_classify_fields_default_to_none` (unit): `Hooks()` has `before_classify is None` and `after_classify is None`. Write this as a separate test. Do not rewrite the existing `test_hooks_defaults_to_none`.
6. `test_hooks_accepts_classify_callbacks` (unit): `Hooks(before_classify=fn, after_classify=fn)` stores both callbacks.
7. `test_hooks_existing_construction_unaffected` (unit): keyword construction in the style of `test_hooks_accepts_callbacks` still works with the new fields left at None. Positional construction `Hooks(a, b)` still binds to `before_render` and `after_render`.

## Verification

- `uv run pytest tests/ --ignore=tests/test_run_task.py` passes.
- `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F` is clean. Lint covers only the changed files, because main already has repo-wide ruff errors.
- There is no typecheck command.

---

# before/after_classify Hooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `BeforeClassifyContext`/`AfterClassifyContext` frozen hook contexts, their hook aliases, and the `before_classify`/`after_classify` fields on `Hooks`, without wiring them anywhere.

**Architecture:** Pure type additions in `py_ai_toolkit/core/hooks.py`, following the existing `@dataclass(frozen=True)` context pattern and the `Callable[[Ctx], Awaitable[None]]` alias pattern. The classifier types come from `py_ai_toolkit/core/domain/classifier.py`, which already exists on this branch (cut from the 1.2 branch). The two new `Hooks` fields go last so the positional order of existing fields is unchanged.

**Tech Stack:** Python dataclasses, pydantic v2 (classifier domain models), pytest, uv, ruff.

**Spec:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-1-3-feat-before-after-5b5a930e/docs/superpowers/specs/task-1-3-feat-before-after-5b5a930e-design.md` (reproduced verbatim above). Milestone spec: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md`, "Hooks" section.

All commands run from the worktree root `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-1-3-feat-before-after-5b5a930e` on branch `m-classifier/task-1-3-feat-before-after-5b5a930e`.

## Global Constraints

- Files touched: only `py_ai_toolkit/core/hooks.py` and `tests/unit/test_hooks.py`.
- Both contexts use `@dataclass(frozen=True)`.
- `BeforeClassifyContext(state: str | dict[str, Any] | list[Any], questions: Mapping[str, Question], model: str)` — field order exactly as written.
- `AfterClassifyContext(response: ClassifierResponse, model: str, elapsed_ms: float, usage: ClassifierUsage)` — field order exactly as written.
- `before_classify: BeforeClassifyHook | None = None` and `after_classify: AfterClassifyHook | None = None` are the LAST two fields of `Hooks`, after `on_retry`; existing fields are not reordered.
- No wiring into `core/toolkit.py`; no export from `py_ai_toolkit/__init__.py`; no edit to `docs/guide/hooks.md`.
- No SDK import or network access in `core/`.
- Decision D: `after_classify` is success-only; no error hook is added.
- Contexts do no validation; `usage` duplicates `response.usage` deliberately and agreement is not checked.
- Verification: `uv run pytest tests/ --ignore=tests/test_run_task.py` and `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F`. No typecheck command.

## Review Focus

1. Mutating any field (not only the one the existing pattern happens to test) of either context must raise `FrozenInstanceError` — pinned by looping over every field in the Task 1 frozen tests.
2. An adapter that reports no token counts produces `ClassifierUsage()` with `None` tokens; `AfterClassifyContext` must hold it unchanged without error — pinned by `test_after_classify_context_accepts_unreported_usage` in Task 1.
3. The context must hold the caller's questions mapping as given (no copy, no re-validation), since the contexts do no validation — pinned by the `ctx.questions is questions` assertion in `test_before_classify_context_holds_fields` in Task 1.
4. A caller constructing `Hooks` positionally with all nine existing callbacks must still bind each to the same field; the new fields must sit at positions 10 and 11 — pinned by the `fields(Hooks)` order assertion in `test_hooks_existing_construction_unaffected` in Task 2.
5. Mixing classify callbacks with existing callbacks in one `Hooks(...)` call must leave unrelated fields at None — pinned by the `after_render is None`/`on_retry is None` assertions in `test_hooks_accepts_classify_callbacks` in Task 2.

---

### Task 1: Classify hook contexts and aliases

**Files:**
- Modify: `py_ai_toolkit/core/hooks.py:1-10` (imports), `:67-71` (append contexts after `OnRetryContext`), `:74-82` (alias block)
- Test: `tests/unit/test_hooks.py:1-24` (imports), append new tests after `test_on_retry_context_is_frozen` (line 79)

**Interfaces:**
- Consumes: `Question`, `ClassifierResponse`, `ClassifierUsage`, `NoulQuestion`, `ChoiceQuestion`, `NoulAnswer` from `py_ai_toolkit.core.domain.classifier` (already on branch).
- Produces: `BeforeClassifyContext`, `AfterClassifyContext`, `BeforeClassifyHook`, `AfterClassifyHook` in `py_ai_toolkit.core.hooks`. Task 2 uses `BeforeClassifyHook` and `AfterClassifyHook` as `Hooks` field types.

- [ ] **Step 1: Add the imports to the test file**

In `tests/unit/test_hooks.py`, replace lines 10-24:

```python
from py_ai_toolkit.core.domain.schemas import (
    CompletionResponse,
    SingleShotValidationConfig,
)
from py_ai_toolkit.core.hooks import (
    AfterLLMCallContext,
    AfterRenderContext,
    AfterValidationContext,
    BeforeLLMCallContext,
    BeforeRenderContext,
    BeforeValidationContext,
    Hooks,
    OnRetryContext,
    _fire_hook,
)
```

with:

```python
from py_ai_toolkit.core.domain.classifier import (
    ChoiceQuestion,
    ClassifierResponse,
    ClassifierUsage,
    NoulAnswer,
    NoulQuestion,
)
from py_ai_toolkit.core.domain.schemas import (
    CompletionResponse,
    SingleShotValidationConfig,
)
from py_ai_toolkit.core.hooks import (
    AfterClassifyContext,
    AfterLLMCallContext,
    AfterRenderContext,
    AfterValidationContext,
    BeforeClassifyContext,
    BeforeLLMCallContext,
    BeforeRenderContext,
    BeforeValidationContext,
    Hooks,
    OnRetryContext,
    _fire_hook,
)
```

- [ ] **Step 2: Write the failing context tests**

In `tests/unit/test_hooks.py`, insert directly after `test_on_retry_context_is_frozen` (after line 78 in the original file, before `def test_hooks_defaults_to_none():`):

```python
def _classifier_response(usage: ClassifierUsage) -> ClassifierResponse:
    return ClassifierResponse(
        model="jev-1",
        answers={"q": NoulAnswer(noul=0.5)},
        usage=usage,
    )


def test_before_classify_context_is_frozen():
    ctx = BeforeClassifyContext(
        state="some text",
        questions={"q": NoulQuestion()},
        model="jev-1",
    )
    for name, value in (("state", "other"), ("questions", {}), ("model", "other")):
        with pytest.raises(FrozenInstanceError):
            setattr(ctx, name, value)


def test_before_classify_context_holds_fields():
    questions = {
        "q": NoulQuestion(),
        "c": ChoiceQuestion(criteria={"yes": None, "no": "not at all"}),
    }

    text_ctx = BeforeClassifyContext(
        state="some text", questions=questions, model="jev-1"
    )
    assert text_ctx.state == "some text"
    assert text_ctx.questions is questions
    assert text_ctx.model == "jev-1"

    dict_ctx = BeforeClassifyContext(
        state={"ticket": "refund please"}, questions=questions, model="jev-1"
    )
    assert dict_ctx.state == {"ticket": "refund please"}

    list_ctx = BeforeClassifyContext(
        state=["turn 1", {"turn": 2}], questions=questions, model="jev-1"
    )
    assert list_ctx.state == ["turn 1", {"turn": 2}]


def test_after_classify_context_is_frozen():
    usage = ClassifierUsage(input_tokens=12, output_tokens=3)
    ctx = AfterClassifyContext(
        response=_classifier_response(usage),
        model="jev-1",
        elapsed_ms=42.0,
        usage=usage,
    )
    for name, value in (
        ("response", None),
        ("model", "other"),
        ("elapsed_ms", 0.0),
        ("usage", ClassifierUsage()),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(ctx, name, value)


def test_after_classify_context_carries_usage():
    usage = ClassifierUsage(input_tokens=12, output_tokens=3)
    ctx = AfterClassifyContext(
        response=_classifier_response(usage),
        model="jev-1",
        elapsed_ms=42.0,
        usage=usage,
    )
    assert ctx.model == "jev-1"
    assert ctx.elapsed_ms == 42.0
    assert ctx.response.answers["q"].noul == 0.5
    assert ctx.usage.input_tokens == 12
    assert ctx.usage.output_tokens == 3
    assert ctx.response.usage.input_tokens == 12
    assert ctx.response.usage.output_tokens == 3


def test_after_classify_context_accepts_unreported_usage():
    usage = ClassifierUsage()
    ctx = AfterClassifyContext(
        response=_classifier_response(usage),
        model="jev-1",
        elapsed_ms=1.5,
        usage=usage,
    )
    assert ctx.usage.input_tokens is None
    assert ctx.usage.output_tokens is None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_hooks.py -v`
Expected: collection ERROR for `tests/unit/test_hooks.py` with `ImportError: cannot import name 'AfterClassifyContext' from 'py_ai_toolkit.core.hooks'`.

- [ ] **Step 4: Add the imports to hooks.py**

In `py_ai_toolkit/core/hooks.py`, replace lines 1-10:

```python
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Type

from pydantic import BaseModel

from py_ai_toolkit.core.domain.schemas import (
    CompletionResponse,
    EmbeddingUsage,
    ValidationConfig,
)
```

with:

```python
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Type

from pydantic import BaseModel

from py_ai_toolkit.core.domain.classifier import (
    ClassifierResponse,
    ClassifierUsage,
    Question,
)
from py_ai_toolkit.core.domain.schemas import (
    CompletionResponse,
    EmbeddingUsage,
    ValidationConfig,
)
```

- [ ] **Step 5: Add the two contexts**

In `py_ai_toolkit/core/hooks.py`, replace:

```python
@dataclass(frozen=True)
class OnRetryContext:
    current_retry: int
    max_retries: int
    evaluations: str
```

with:

```python
@dataclass(frozen=True)
class OnRetryContext:
    current_retry: int
    max_retries: int
    evaluations: str


@dataclass(frozen=True)
class BeforeClassifyContext:
    state: str | dict[str, Any] | list[Any]
    questions: Mapping[str, Question]
    model: str


@dataclass(frozen=True)
class AfterClassifyContext:
    response: ClassifierResponse
    model: str
    elapsed_ms: float
    usage: ClassifierUsage
```

- [ ] **Step 6: Add the two aliases**

In `py_ai_toolkit/core/hooks.py`, replace:

```python
OnRetryHook = Callable[[OnRetryContext], Awaitable[None]]
```

with:

```python
OnRetryHook = Callable[[OnRetryContext], Awaitable[None]]
BeforeClassifyHook = Callable[[BeforeClassifyContext], Awaitable[None]]
AfterClassifyHook = Callable[[AfterClassifyContext], Awaitable[None]]
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_hooks.py -v`
Expected: PASS for all tests, including `test_before_classify_context_is_frozen`, `test_before_classify_context_holds_fields`, `test_after_classify_context_is_frozen`, `test_after_classify_context_carries_usage`, `test_after_classify_context_accepts_unreported_usage`.

- [ ] **Step 8: Commit**

```bash
git add py_ai_toolkit/core/hooks.py tests/unit/test_hooks.py
git commit -m "feat: add BeforeClassifyContext and AfterClassifyContext hook contexts"
```

---

### Task 2: before_classify/after_classify fields on Hooks

**Files:**
- Modify: `py_ai_toolkit/core/hooks.py` (`Hooks` dataclass, after the `on_retry` field)
- Test: `tests/unit/test_hooks.py:2` (dataclasses import), append new tests after `test_hooks_accepts_callbacks`

**Interfaces:**
- Consumes: `BeforeClassifyHook`, `AfterClassifyHook` from Task 1 (`py_ai_toolkit.core.hooks`).
- Produces: `Hooks.before_classify: BeforeClassifyHook | None = None` and `Hooks.after_classify: AfterClassifyHook | None = None` as fields 10 and 11; the later `toolkit.classify` story reads them.

- [ ] **Step 1: Extend the dataclasses import in the test file**

In `tests/unit/test_hooks.py`, replace line 2:

```python
from dataclasses import FrozenInstanceError
```

with:

```python
from dataclasses import FrozenInstanceError, fields
```

- [ ] **Step 2: Write the failing Hooks tests**

In `tests/unit/test_hooks.py`, insert directly after `test_hooks_accepts_callbacks` (before `def test_fire_hook_calls_callback():`):

```python
def test_hooks_classify_fields_default_to_none():
    hooks = Hooks()
    assert hooks.before_classify is None
    assert hooks.after_classify is None


def test_hooks_accepts_classify_callbacks():
    async def on_before(ctx):
        pass

    async def on_after(ctx):
        pass

    hooks = Hooks(
        before_classify=on_before,
        after_classify=on_after,
        after_embed=on_after,
    )
    assert hooks.before_classify is on_before
    assert hooks.after_classify is on_after
    assert hooks.after_embed is on_after
    assert hooks.after_render is None
    assert hooks.on_retry is None


def test_hooks_existing_construction_unaffected():
    async def first(ctx):
        pass

    async def second(ctx):
        pass

    keyword = Hooks(before_render=first, after_llm_call=second)
    assert keyword.before_render is first
    assert keyword.after_llm_call is second
    assert keyword.before_classify is None
    assert keyword.after_classify is None

    positional = Hooks(first, second)
    assert positional.before_render is first
    assert positional.after_render is second
    assert positional.before_classify is None
    assert positional.after_classify is None

    assert [f.name for f in fields(Hooks)] == [
        "before_render",
        "after_render",
        "before_llm_call",
        "after_llm_call",
        "after_embed",
        "after_embed_batch",
        "before_validation",
        "after_validation",
        "on_retry",
        "before_classify",
        "after_classify",
    ]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_hooks.py -k "classify_fields_default or classify_callbacks or existing_construction" -v`
Expected: FAIL — `test_hooks_classify_fields_default_to_none` and `test_hooks_existing_construction_unaffected` with `AttributeError: 'Hooks' object has no attribute 'before_classify'`; `test_hooks_accepts_classify_callbacks` with `TypeError: Hooks.__init__() got an unexpected keyword argument 'before_classify'`.

- [ ] **Step 4: Append the two fields to Hooks**

In `py_ai_toolkit/core/hooks.py`, replace:

```python
    after_validation: AfterValidationHook | None = None
    on_retry: OnRetryHook | None = None
```

with:

```python
    after_validation: AfterValidationHook | None = None
    on_retry: OnRetryHook | None = None
    before_classify: BeforeClassifyHook | None = None
    after_classify: AfterClassifyHook | None = None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_hooks.py -v`
Expected: PASS for every test in the file, including the existing `test_hooks_defaults_to_none` and `test_hooks_accepts_callbacks` (unchanged).

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest tests/ --ignore=tests/test_run_task.py`
Expected: all tests pass (no failures, no errors).

- [ ] **Step 7: Lint the changed files**

Run: `ruff check --select E,F py_ai_toolkit/core/hooks.py tests/unit/test_hooks.py`
Expected: `All checks passed!` (the committed-history gate runs in Step 9, after the commit, so these uncommitted edits are covered now).

- [ ] **Step 8: Commit**

```bash
git add py_ai_toolkit/core/hooks.py tests/unit/test_hooks.py
git commit -m "feat: add before_classify and after_classify fields to Hooks"
```

- [ ] **Step 9: Re-run the lint gate against committed history**

Run: `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F`
Expected: `All checks passed!`
