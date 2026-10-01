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
