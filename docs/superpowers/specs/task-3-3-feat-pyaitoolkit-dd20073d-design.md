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
