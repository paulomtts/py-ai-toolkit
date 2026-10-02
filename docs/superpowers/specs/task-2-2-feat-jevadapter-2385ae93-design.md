# Task 2.2 (2385ae93): JevAdapter classify mapping

Parent: Story 2 "Jev adapter and jev extra" (e01d0be7), milestone e3bd09dc. Narrows the milestone design `docs/superpowers/specs/2026-10-01-classifier-port-design.md` (sections "Types", "Adapter", and the question/answer mapping table) to the adapter's construction and happy-path mapping only.

## Preconditions

The working branch must contain 1.1 (`core/domain/classifier.py`), 1.2 (`core/ports/classifier_port.py` plus the `ClassifierPort` export from `core/ports/__init__.py`) and 2.1 (the `jev` extra, `typesafe-sdk>=0.6.0`). The 2.2 worktree already has all three; if a rebuilt branch lacks them, merge the sibling branches first. `typesafe_sdk` is not installed by default; install it with `uv sync --extra jev` (or `uv pip install "typesafe-sdk>=0.6.0"`) before running the adapter tests, otherwise they skip.

Before coding, confirm the real SDK names against https://docs.typesafe.ai/sdk/python/api.md. The verified surface this spec assumes is `AsyncTypeSafeClient(*, api_key, model, retry, timeout, headers, transport, http_client, base_url)`, `system_one(state, questions, *, model, retry, timeout, response_model)` returning `SystemOneResponse` (`model`, `usage`, `answers`, `nouls`, `choices`, `scores`), and question classes `Noul`, `Choice`, `Score`. If a name differs, follow the SDK and note it in the PR. Do not change our domain types.

## Scope

Files to create (the only files this card touches):

- `py_ai_toolkit/adapters/jev_adapter.py`
- `tests/unit/test_jev_adapter.py`

Out of scope:

- 2.3 owns the `TypeSafeError` -> `ClassifierAdapterError` try/except mapping and `aclose()`. `classify` gets no error handling here, and `ClassifierPort`'s default no-op `aclose` is left in place.
- Do not edit `py_ai_toolkit/adapters/__init__.py`. It must not import `JevAdapter` or list it in `__all__`.
- Do not edit `pyproject.toml` and do not bump the version.
- Also out of scope: factory or facade wiring, live tests (`tests/live/`), docs, any retry logic, normalization or derived confidence, streaming, and a sync client.

## Behavior

`jev_adapter.py` is the only module in the package that imports `typesafe_sdk`. It imports port and domain types the same way `instructor_adapter.py` does (`from py_ai_toolkit.core.ports import ClassifierPort`, with domain types from `py_ai_toolkit.core.domain.classifier`).

`JevAdapter(ClassifierPort).__init__(self, api_key: str, model: str = "jev-latest", base_url: str | None = None)`:
- stores `self._model = model`, which the facade reads for hooks, just as it reads `InstructorAdapter._model`;
- builds `self._client = AsyncTypeSafeClient(api_key=api_key, model=model, base_url=base_url)`;
- passes no `retry=`, `timeout=` or `headers=` overrides, so SDK defaults apply.

`async classify(self, state, questions: Mapping[str, Question]) -> ClassifierResponse`:
1. Builds a new dict that maps each question name to an SDK question. Each type gets its own explicit function, and nothing passes through `model_dump`:
   - `NoulQuestion` -> `Noul(instructions=..., criteria=...)`. The SDK's noul criteria is a plain dict (`TypedDict` with optional `true` and `false` keys), not a pydantic model, so our `NoulCriteria` is translated field by field into a new dict that holds only the keys whose value is not `None` (`{"true": ...}`, `{"false": ...}`, both, or `{}`). `None` criteria stays `None`.
   - `ChoiceQuestion` -> `Choice(instructions=..., criteria=<dict copy>)`.
   - `ScoreQuestion` -> `Score(instructions=..., criteria=<list copy, order preserved>)`.
   - Dispatch is by `isinstance` over the closed union. An unexpected type raises `TypeError`, and no SDK call happens.
2. Calls `await self._client.system_one(state, sdk_questions)` with no extra keyword arguments. The model comes from the client.
3. Builds a `ClassifierResponse`:
   - `model = response.model`
   - `usage = ClassifierUsage(input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)`. Both values pass through as `int | None`.
   - `answers` merges three sets of entries, each copied field by field:
     - every `response.nouls` entry -> `NoulAnswer(noul=...)`, which has no confidence;
     - every `response.choices` entry -> `ChoiceAnswer(choice, probabilities: dict[str, float], confidence)`;
     - every `response.scores` entry -> `ScoreAnswer(score, probabilities={int(k): v}, confidence, legend={int(k): v})`.
   - Values stay raw. Nothing is normalized or rounded.

SDK exceptions propagate unchanged until 2.3 lands. Our own pydantic `ValidationError`s also propagate.

## Tests

Tier rule: this repo has no test-tier taxonomy. The only layout is `tests/unit/`, and the milestone design places this file at `tests/unit/test_jev_adapter.py`. All tests below go in the **unit** tier (`tests/unit/`). They use a stubbed client, make no network calls, and are plain pytest functions in the style of `tests/unit/test_hooks.py`, with `pytest-asyncio` for the async ones. The module starts with `pytest.importorskip("typesafe_sdk")`.

Fixture: build a `JevAdapter` and replace `adapter._client` with a stub whose `system_one` is an `AsyncMock`. Its return value is a real `SystemOneResponse`, built with keyword arguments (`SystemOneResponse(model=..., usage=Usage(...), answers={...})`) from the SDK's `NoulAnswer`, `ChoiceAnswer` and `ScoreAnswer`, holding one answer of each kind plus usage. Do not use `model_validate`: it does not exist on `typesafe-sdk` 0.6.0 (a msgspec struct, while 0.7.x is pydantic), and on 0.7.x it rejects string score keys. The real response already carries int score keys, so the string-key coercion is tested separately with a `types.SimpleNamespace` stand-in response (see test 5).

1. `test_init_keeps_model` (unit): `_model` defaults to `"jev-latest"` and keeps an explicit value. Constructing the adapter makes no network call.
2. `test_question_mapping` (unit): `system_one` is awaited once with `state` and a dict whose values are instances of the SDK classes `Noul`, `Choice` and `Score`. Their `instructions` and `criteria` match the inputs: noul true/false (as a dict), the choice dict, and the score list in order. No `retry` or `model` kwarg is passed.
3. `test_noul_criteria_none` (unit): a `NoulQuestion` without criteria maps to `Noul` with `criteria` `None`; one with only `true` set maps to criteria `{"true": ...}`.
4. `test_answer_mapping` (unit): the result is a `ClassifierResponse`. `nouls`, `choices` and `scores` hold the expected names and raw values, and `model` and `usage` are copied.
5. `test_score_keys_coerced_to_int` (unit): the stub's `system_one` returns a `SimpleNamespace` with `model`, `usage`, `nouls={}`, `choices={}` and a `scores` entry whose `probabilities` and `legend` keys are strings (`"1"`, `"2"`). The resulting `ScoreAnswer.probabilities` and `legend` keys are `int`.
6. `test_usage_none_passthrough` (unit): usage tokens of `None` stay `None`.
7. `test_adapters_package_does_not_import_sdk` (unit): runs a subprocess with `sys.executable -c "import sys, py_ai_toolkit.adapters; assert 'typesafe_sdk' not in sys.modules"` and checks that it exits 0.

## Verification

- Full suite: `uv run pytest tests/ --ignore=tests/test_run_task.py`. Install the `jev` extra first so the adapter tests run instead of skipping.
- Typecheck: none.
- Lint: `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F`
