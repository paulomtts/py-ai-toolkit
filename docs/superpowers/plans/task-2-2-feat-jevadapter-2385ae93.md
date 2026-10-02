<!-- task-pipeline: validated -->
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

---

# JevAdapter classify mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `JevAdapter(ClassifierPort)` in `py_ai_toolkit/adapters/jev_adapter.py`. It maps our classifier questions to `typesafe_sdk` `Noul`/`Choice`/`Score`, awaits `AsyncTypeSafeClient.system_one`, and maps the `SystemOneResponse` back into our `ClassifierResponse`.

**Architecture:** This is a single driven adapter module and the only place in the package that imports `typesafe_sdk`. Module-level per-type mapping functions (question side and answer side) keep `classify` to three lines: map, call, map back. `py_ai_toolkit/adapters/__init__.py` is untouched, so importing the adapters package never loads the optional SDK.

**Tech Stack:** Python >=3.11, pydantic v2, `typesafe-sdk>=0.6.0` (optional `jev` extra), pytest, pytest-asyncio (`@pytest.mark.asyncio`), `unittest.mock.AsyncMock`, uv.

**Spec:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-2-feat-jevadapter-2385ae93/docs/superpowers/specs/task-2-2-feat-jevadapter-2385ae93-design.md` (prepended above). Milestone design: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md`.

All paths below are relative to the worktree root `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-2-feat-jevadapter-2385ae93`, and all commands run from that directory.

## Global Constraints

- The card creates or edits only `py_ai_toolkit/adapters/jev_adapter.py` and `tests/unit/test_jev_adapter.py`.
- Do not edit `py_ai_toolkit/adapters/__init__.py`. It must not import `JevAdapter` or list it in `__all__`.
- Do not edit `pyproject.toml` and do not bump the version (it stays `0.7.0`).
- The SDK floor is `typesafe-sdk>=0.6.0`, from the `jev` extra that 2.1 already added.
- The default model is `"jev-latest"`. The constructor signature is `__init__(self, api_key: str, model: str = "jev-latest", base_url: str | None = None)`.
- Construct `AsyncTypeSafeClient(api_key=api_key, model=model, base_url=base_url)` only. Pass no `retry=`, `timeout=` or `headers=`.
- Call `system_one(state, sdk_questions)` with no keyword arguments.
- `classify` has no try/except, there is no error mapping, and there is no `aclose` override. Those belong to 2.3 (1ada6fbf).
- Map field by field and never use `model_dump`. Values stay raw, with no normalization or rounding, and `noul` has no confidence.
- Score `probabilities` and `legend` keys are coerced with `int(k)`.
- Every test lives in the unit tier at `tests/unit/test_jev_adapter.py`, uses no network, and starts with `pytest.importorskip("typesafe_sdk")`.
- Async tests use `@pytest.mark.asyncio` (the repo has no `asyncio_mode` setting; see `tests/unit/test_tools.py:60`).
- Lint is `ruff check --select E,F`. Imports placed after `importorskip` need `# noqa: E402`.

## Review Focus

1. A question that is not one of our three types (for example a raw dict `{"type": "noul"}`) should raise `TypeError` before any SDK call is made. This is pinned in Task 2 by `test_unknown_question_type_raises_before_call`.
2. A choice label described as `None` (for example `{"angry": None}`) should reach the SDK as `None`, neither dropped nor stringified. This is pinned in Task 2 by the `"angry": None` assertion in `test_question_mapping`.
3. A response with no answers should give a `ClassifierResponse` with `answers == {}`, not an error. This is pinned in Task 1 by `test_empty_answers`.
4. Structured (dict) `state` and dict `instructions` should pass through unchanged, not stringified. This is pinned in Task 2 by `test_structured_state_and_instructions_pass_through`.
5. A `NoulCriteria` with only `false` set should map to `{"false": ...}`, and one with both fields `None` should map to `{}`, not `None`. This is pinned in Task 2 by extra assertions in `test_noul_criteria_none`.

---

### Task 0: Preconditions and SDK install

There is no code change in this task. It makes sure the dependencies this card consumes are present so later RED failures are the intended ones.

**Files:** none.

**Interfaces:**
- Consumes: `py_ai_toolkit/core/domain/classifier.py` (1.1), `py_ai_toolkit/core/ports/classifier_port.py` with `ClassifierPort` exported from `py_ai_toolkit/core/ports/__init__.py` (1.2), and the `jev` extra in `pyproject.toml` (2.1).
- Produces: an env where `import typesafe_sdk` works.

- [ ] **Step 1: Verify 1.1, 1.2 and 2.1 are on this branch**

Run:
```bash
test -f py_ai_toolkit/core/domain/classifier.py \
  && test -f py_ai_toolkit/core/ports/classifier_port.py \
  && grep -q '^from .classifier_port import ClassifierPort' py_ai_toolkit/core/ports/__init__.py \
  && grep -q 'typesafe-sdk>=0.6.0' pyproject.toml \
  && echo OK
```
Expected: `OK`.

If it does not print `OK`, merge the missing sibling branches and re-run the check:
```bash
git merge --no-edit m-classifier/task-1-1-feat-classifier-dc5d79a4 m-classifier/task-1-2-feat-classifierport-502717e2
```

- [ ] **Step 2: Install the SDK together with the dev extra**

`uv sync` removes extras that are not listed, and pytest and pytest-asyncio live in the `dev` extra. Pass both extras:
```bash
uv sync --extra dev --extra jev
```
Expected: the command exits 0 and lists `typesafe-sdk` among the installed packages.

- [ ] **Step 3: Confirm the SDK names this plan uses**

Check the names against https://docs.typesafe.ai/sdk/python/api.md, then run:
```bash
uv run python -c "import typesafe_sdk as t; print(t.__version__); t.AsyncTypeSafeClient, t.SystemOneResponse, t.Usage, t.Noul, t.Choice, t.Score, t.NoulAnswer, t.ChoiceAnswer, t.ScoreAnswer"
```
Expected: a version `>=0.6.0` is printed and there is no `AttributeError`. On SDK 0.7.2 the names are confirmed in `typesafe_sdk/__init__.py`: `AsyncTypeSafeClient.__init__(*, api_key, model, retry, timeout, headers, transport, http_client, base_url)`, `system_one(state, questions, *, model, retry, timeout, response_model)`, and the `nouls`/`choices`/`scores` cached properties on `SystemOneResponse`. If a name differs, use the SDK's name in Tasks 1 and 2 and record it for the PR. Do not change the domain types.

---

### Task 1: JevAdapter construction and answer mapping

**Files:**
- Create: `py_ai_toolkit/adapters/jev_adapter.py`
- Test: `tests/unit/test_jev_adapter.py` (create)

**Interfaces:**
- Consumes: `ClassifierPort` (`py_ai_toolkit.core.ports`) with abstract `async classify(self, state: str | dict[str, Any] | list[Any], questions: Mapping[str, Question]) -> ClassifierResponse`; domain types from `py_ai_toolkit.core.domain.classifier`, which are `Answer`, `ChoiceAnswer(choice: str, probabilities: dict[str, float], confidence: float)`, `ClassifierResponse(model: str, answers: dict[str, Answer], usage: ClassifierUsage)`, `ClassifierUsage(input_tokens: int | None, output_tokens: int | None)`, `NoulAnswer(noul: float)`, `Question` and `ScoreAnswer(score: float, probabilities: dict[int, float], confidence: float, legend: dict[int, JSONContent])`.
- Produces: `class JevAdapter(ClassifierPort)` with `self._model: str` and `self._client: AsyncTypeSafeClient`, plus the module function `_to_classifier_response(response: SystemOneResponse) -> ClassifierResponse`. `classify` temporarily passes `questions` through unmapped; Task 2 replaces that line.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_jev_adapter.py`:

```python
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

typesafe_sdk = pytest.importorskip("typesafe_sdk")

from py_ai_toolkit.adapters.jev_adapter import JevAdapter  # noqa: E402
from py_ai_toolkit.core.domain.classifier import (  # noqa: E402
    ChoiceAnswer,
    ChoiceQuestion,
    ClassifierResponse,
    ClassifierUsage,
    NoulAnswer,
    NoulCriteria,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE = "I was charged twice. Please help."


def _questions():
    return {
        "billing": NoulQuestion(
            instructions="Is this about billing?",
            criteria=NoulCriteria(
                true="mentions a charge",
                false="no charge mentioned",
            ),
        ),
        "tone": ChoiceQuestion(
            instructions="What is the tone?",
            criteria={"calm": "measured wording", "angry": None},
        ),
        "urgency": ScoreQuestion(
            instructions="How urgent is it?",
            criteria=["low", "medium", "high"],
        ),
    }


def _sdk_response(input_tokens=12, output_tokens=3):
    return typesafe_sdk.SystemOneResponse(
        model="jev-2026-09",
        usage=typesafe_sdk.Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        answers={
            "billing": typesafe_sdk.NoulAnswer(noul=0.87),
            "tone": typesafe_sdk.ChoiceAnswer(
                choice="angry",
                probabilities={"calm": 0.2, "angry": 0.8},
                confidence=0.6,
            ),
            "urgency": typesafe_sdk.ScoreAnswer(
                score=1.4,
                probabilities={0: 0.1, 1: 0.4, 2: 0.5},
                confidence=0.7,
                legend={0: "low", 1: "medium", 2: "high"},
            ),
        },
    )


def _adapter_returning(response):
    adapter = JevAdapter(api_key="test-key")
    adapter._client = SimpleNamespace(system_one=AsyncMock(return_value=response))
    return adapter


def test_init_keeps_model():
    assert JevAdapter(api_key="test-key")._model == "jev-latest"

    adapter = JevAdapter(
        api_key="test-key",
        model="jev-2026-09",
        base_url="https://example.invalid",
    )
    assert adapter._model == "jev-2026-09"
    assert isinstance(adapter._client, typesafe_sdk.AsyncTypeSafeClient)


@pytest.mark.asyncio
async def test_answer_mapping():
    adapter = _adapter_returning(_sdk_response())

    result = await adapter.classify(STATE, _questions())

    assert isinstance(result, ClassifierResponse)
    assert result.model == "jev-2026-09"
    assert result.usage == ClassifierUsage(input_tokens=12, output_tokens=3)
    assert set(result.answers) == {"billing", "tone", "urgency"}
    assert result.nouls == {"billing": NoulAnswer(noul=0.87)}
    assert result.choices == {
        "tone": ChoiceAnswer(
            choice="angry",
            probabilities={"calm": 0.2, "angry": 0.8},
            confidence=0.6,
        )
    }
    assert result.scores == {
        "urgency": ScoreAnswer(
            score=1.4,
            probabilities={0: 0.1, 1: 0.4, 2: 0.5},
            confidence=0.7,
            legend={0: "low", 1: "medium", 2: "high"},
        )
    }


@pytest.mark.asyncio
async def test_score_keys_coerced_to_int():
    response = SimpleNamespace(
        model="jev-2026-09",
        usage=SimpleNamespace(input_tokens=1, output_tokens=2),
        nouls={},
        choices={},
        scores={
            "urgency": SimpleNamespace(
                score=1.75,
                probabilities={"1": 0.25, "2": 0.75},
                confidence=0.5,
                legend={"1": "medium", "2": "high"},
            )
        },
    )
    adapter = _adapter_returning(response)

    result = await adapter.classify(
        STATE, {"urgency": ScoreQuestion(criteria=["low", "medium", "high"])}
    )

    score = result.scores["urgency"]
    assert score.probabilities == {1: 0.25, 2: 0.75}
    assert score.legend == {1: "medium", 2: "high"}
    assert all(type(key) is int for key in [*score.probabilities, *score.legend])


@pytest.mark.asyncio
async def test_usage_none_passthrough():
    adapter = _adapter_returning(_sdk_response(input_tokens=None, output_tokens=None))

    result = await adapter.classify(STATE, _questions())

    assert result.usage.input_tokens is None
    assert result.usage.output_tokens is None


@pytest.mark.asyncio
async def test_empty_answers():
    response = typesafe_sdk.SystemOneResponse(
        model="jev-2026-09",
        usage=typesafe_sdk.Usage(input_tokens=5, output_tokens=0),
        answers={},
    )
    adapter = _adapter_returning(response)

    result = await adapter.classify(STATE, _questions())

    assert result.answers == {}
    assert result.model == "jev-2026-09"
    assert result.usage == ClassifierUsage(input_tokens=5, output_tokens=0)


def test_adapters_package_does_not_import_sdk():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, py_ai_toolkit.adapters; "
            "assert 'typesafe_sdk' not in sys.modules",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
```

Note: our domain `ScoreAnswer` is lax pydantic and would coerce `"1"` to `1` by itself, so `test_score_keys_coerced_to_int` pins the observable contract (int keys), not the mechanism. The explicit `int(k)` in the adapter is still required by the spec. `test_adapters_package_does_not_import_sdk` is a regression guard. It fails here only because the module cannot be collected, and after GREEN it keeps anyone from wiring `JevAdapter` into `adapters/__init__.py`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_jev_adapter.py -v`
Expected: a collection ERROR with `ModuleNotFoundError: No module named 'py_ai_toolkit.adapters.jev_adapter'`. If the output says `SKIPPED ... could not import 'typesafe_sdk'` instead, Task 0 Step 2 was not done.

- [ ] **Step 3: Write the minimal implementation**

Create `py_ai_toolkit/adapters/jev_adapter.py`:

```python
"""Jev classifier adapter over the TypeSafe AI SDK.

This is the only module in py_ai_toolkit that imports typesafe_sdk. It is
deliberately not re-exported from py_ai_toolkit.adapters, so the SDK stays
an optional dependency (the `jev` extra).
"""

from collections.abc import Mapping
from typing import Any

from typesafe_sdk import AsyncTypeSafeClient, SystemOneResponse

from py_ai_toolkit.core.domain.classifier import (
    Answer,
    ChoiceAnswer,
    ClassifierResponse,
    ClassifierUsage,
    NoulAnswer,
    Question,
    ScoreAnswer,
)
from py_ai_toolkit.core.ports import ClassifierPort


def _to_classifier_response(response: SystemOneResponse) -> ClassifierResponse:
    answers: dict[str, Answer] = {}
    for name, noul in response.nouls.items():
        answers[name] = NoulAnswer(noul=noul.noul)
    for name, choice in response.choices.items():
        answers[name] = ChoiceAnswer(
            choice=choice.choice,
            probabilities=dict(choice.probabilities),
            confidence=choice.confidence,
        )
    for name, score in response.scores.items():
        answers[name] = ScoreAnswer(
            score=score.score,
            probabilities={int(k): v for k, v in score.probabilities.items()},
            confidence=score.confidence,
            legend={int(k): v for k, v in score.legend.items()},
        )
    return ClassifierResponse(
        model=response.model,
        answers=answers,
        usage=ClassifierUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        ),
    )


class JevAdapter(ClassifierPort):
    """
    TypeSafe AI (Jev) implementation of the classifier port.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "jev-latest",
        base_url: str | None = None,
    ):
        self._model = model
        self._client = AsyncTypeSafeClient(
            api_key=api_key,
            model=model,
            base_url=base_url,
        )

    async def classify(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: Mapping[str, Question],
    ) -> ClassifierResponse:
        response = await self._client.system_one(state, questions)
        return _to_classifier_response(response)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_jev_adapter.py -v`
Expected: 6 passed (`test_init_keeps_model`, `test_answer_mapping`, `test_score_keys_coerced_to_int`, `test_usage_none_passthrough`, `test_empty_answers`, `test_adapters_package_does_not_import_sdk`).

- [ ] **Step 5: Lint the two files**

Run: `ruff check --select E,F py_ai_toolkit/adapters/jev_adapter.py tests/unit/test_jev_adapter.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add py_ai_toolkit/adapters/jev_adapter.py tests/unit/test_jev_adapter.py
git commit -m "feat: add JevAdapter with SystemOneResponse answer mapping"
```

---

### Task 2: Question mapping to SDK Noul, Choice and Score

**Files:**
- Modify: `py_ai_toolkit/adapters/jev_adapter.py` (imports, new mapping functions above `_to_classifier_response`, and the body of `JevAdapter.classify`)
- Test: `tests/unit/test_jev_adapter.py` (append tests)

**Interfaces:**
- Consumes: from Task 1, `JevAdapter`, `_to_classifier_response`, and the test helpers `_questions()`, `_sdk_response()`, `_adapter_returning(response)` and `STATE`. Also our `NoulQuestion(instructions, criteria: NoulCriteria | None)`, `NoulCriteria(true, false)`, `ChoiceQuestion(instructions, criteria: dict[str, JSONContent | None])` and `ScoreQuestion(instructions, criteria: list[JSONContent])`, plus the SDK's `Noul(instructions, criteria: NoulCriteria-TypedDict | None)`, `Choice(instructions, criteria: Mapping)` and `Score(instructions, criteria: Sequence)`.
- Produces: `_noul_criteria(criteria: NoulCriteria | None) -> dict[str, Any] | None`, `_to_noul(question: NoulQuestion) -> Noul`, `_to_choice(question: ChoiceQuestion) -> Choice`, `_to_score(question: ScoreQuestion) -> Score`, and `_to_sdk_question(question: Question) -> Noul | Choice | Score` (it raises `TypeError` on an unknown type). `classify` now sends `{name: _to_sdk_question(q)}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_jev_adapter.py`:

```python
@pytest.mark.asyncio
async def test_question_mapping():
    adapter = _adapter_returning(_sdk_response())

    await adapter.classify(STATE, _questions())

    system_one = adapter._client.system_one
    system_one.assert_awaited_once()
    args, kwargs = system_one.await_args
    assert kwargs == {}
    state, sdk_questions = args
    assert state == STATE
    assert set(sdk_questions) == {"billing", "tone", "urgency"}

    billing = sdk_questions["billing"]
    assert isinstance(billing, typesafe_sdk.Noul)
    assert billing.instructions == "Is this about billing?"
    assert billing.criteria == {
        "true": "mentions a charge",
        "false": "no charge mentioned",
    }

    tone = sdk_questions["tone"]
    assert isinstance(tone, typesafe_sdk.Choice)
    assert tone.instructions == "What is the tone?"
    assert dict(tone.criteria) == {"calm": "measured wording", "angry": None}

    urgency = sdk_questions["urgency"]
    assert isinstance(urgency, typesafe_sdk.Score)
    assert urgency.instructions == "How urgent is it?"
    assert list(urgency.criteria) == ["low", "medium", "high"]


@pytest.mark.asyncio
async def test_noul_criteria_none():
    adapter = _adapter_returning(_sdk_response())

    await adapter.classify(
        STATE,
        {
            "no_criteria": NoulQuestion(instructions="Is this spam?"),
            "only_true": NoulQuestion(criteria=NoulCriteria(true="asks for a refund")),
            "only_false": NoulQuestion(criteria=NoulCriteria(false="no refund asked")),
            "empty": NoulQuestion(criteria=NoulCriteria()),
        },
    )

    _, sdk_questions = adapter._client.system_one.await_args.args
    assert all(isinstance(q, typesafe_sdk.Noul) for q in sdk_questions.values())
    assert sdk_questions["no_criteria"].criteria is None
    assert sdk_questions["only_true"].criteria == {"true": "asks for a refund"}
    assert sdk_questions["only_false"].criteria == {"false": "no refund asked"}
    assert sdk_questions["empty"].criteria == {}


@pytest.mark.asyncio
async def test_unknown_question_type_raises_before_call():
    adapter = _adapter_returning(_sdk_response())

    with pytest.raises(TypeError):
        await adapter.classify(STATE, {"raw": {"type": "noul"}})

    adapter._client.system_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_structured_state_and_instructions_pass_through():
    adapter = _adapter_returning(_sdk_response())
    state = {"message": "I was charged twice.", "attachments": ["receipt.pdf"]}
    instructions = {"question": "Is this about billing?", "scope": ["charges"]}

    await adapter.classify(
        state, {"billing": NoulQuestion(instructions=instructions)}
    )

    sent_state, sdk_questions = adapter._client.system_one.await_args.args
    assert sent_state == state
    assert isinstance(sdk_questions["billing"], typesafe_sdk.Noul)
    assert sdk_questions["billing"].instructions == instructions
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_jev_adapter.py -v -k "question_mapping or noul_criteria_none or unknown_question_type or structured_state"`
Expected: 4 FAILED. `test_question_mapping`, `test_noul_criteria_none` and `test_structured_state_and_instructions_pass_through` fail on `assert isinstance(..., typesafe_sdk.Noul)` because our `NoulQuestion` is still passed through unmapped. `test_unknown_question_type_raises_before_call` fails with `Failed: DID NOT RAISE <class 'TypeError'>`.

- [ ] **Step 3: Implement the question mapping**

In `py_ai_toolkit/adapters/jev_adapter.py`, replace the import block:

```python
from typesafe_sdk import AsyncTypeSafeClient, SystemOneResponse

from py_ai_toolkit.core.domain.classifier import (
    Answer,
    ChoiceAnswer,
    ClassifierResponse,
    ClassifierUsage,
    NoulAnswer,
    Question,
    ScoreAnswer,
)
```

with:

```python
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score, SystemOneResponse

from py_ai_toolkit.core.domain.classifier import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    ClassifierResponse,
    ClassifierUsage,
    NoulAnswer,
    NoulCriteria,
    NoulQuestion,
    Question,
    ScoreAnswer,
    ScoreQuestion,
)
```

Then insert these functions directly above `def _to_classifier_response(`:

```python
def _noul_criteria(criteria: NoulCriteria | None) -> dict[str, Any] | None:
    if criteria is None:
        return None
    mapped: dict[str, Any] = {}
    if criteria.true is not None:
        mapped["true"] = criteria.true
    if criteria.false is not None:
        mapped["false"] = criteria.false
    return mapped


def _to_noul(question: NoulQuestion) -> Noul:
    return Noul(
        instructions=question.instructions,
        criteria=_noul_criteria(question.criteria),
    )


def _to_choice(question: ChoiceQuestion) -> Choice:
    return Choice(
        instructions=question.instructions,
        criteria=dict(question.criteria),
    )


def _to_score(question: ScoreQuestion) -> Score:
    return Score(
        instructions=question.instructions,
        criteria=list(question.criteria),
    )


def _to_sdk_question(question: Question) -> Noul | Choice | Score:
    if isinstance(question, NoulQuestion):
        return _to_noul(question)
    if isinstance(question, ChoiceQuestion):
        return _to_choice(question)
    if isinstance(question, ScoreQuestion):
        return _to_score(question)
    raise TypeError(
        f"Unsupported question type for JevAdapter: {type(question).__name__}"
    )
```

Finally, replace the body of `JevAdapter.classify`:

```python
        response = await self._client.system_one(state, questions)
        return _to_classifier_response(response)
```

with:

```python
        sdk_questions = {
            name: _to_sdk_question(question) for name, question in questions.items()
        }
        response = await self._client.system_one(state, sdk_questions)
        return _to_classifier_response(response)
```

The comprehension finishes before the `await`, so an unknown type raises `TypeError` with no SDK call made.

- [ ] **Step 4: Run the whole adapter test file to verify it passes**

Run: `uv run pytest tests/unit/test_jev_adapter.py -v`
Expected: 10 passed.

- [ ] **Step 5: Lint the two files**

Run: `ruff check --select E,F py_ai_toolkit/adapters/jev_adapter.py tests/unit/test_jev_adapter.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add py_ai_toolkit/adapters/jev_adapter.py tests/unit/test_jev_adapter.py
git commit -m "feat: map classifier questions to typesafe SDK Noul/Choice/Score in JevAdapter"
```

---

### Task 3: Full verification

**Files:** none (verification only).

**Interfaces:**
- Consumes: everything from Tasks 1 and 2.
- Produces: a green suite and a clean lint over the files changed since `main`.

- [ ] **Step 1: Confirm the scope fence held**

Run: `git diff --name-only m-classifier/task-2-1-chore-jev-optional-e6f3dce5...HEAD`
Expected: exactly `py_ai_toolkit/adapters/jev_adapter.py` and `tests/unit/test_jev_adapter.py`. If Task 0 needed a merge, the 1.1 and 1.2 files may also appear, and that is fine. `py_ai_toolkit/adapters/__init__.py` and `pyproject.toml` must not be listed.

- [ ] **Step 2: Run the full suite**

Run: `uv run pytest tests/ --ignore=tests/test_run_task.py`
Expected: all tests pass, and the 10 tests in `tests/unit/test_jev_adapter.py` show as passed, not skipped. If they show as skipped, re-run Task 0 Step 2 and repeat.

- [ ] **Step 3: Run the lint gate**

Run: `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F`
Expected: `All checks passed!`

- [ ] **Step 4: Commit (only if a fix was needed in Steps 2-3)**

```bash
git add py_ai_toolkit/adapters/jev_adapter.py tests/unit/test_jev_adapter.py
git commit -m "fix: address verification findings in JevAdapter"
```
If Steps 2 and 3 passed without changes, there is nothing to commit.
