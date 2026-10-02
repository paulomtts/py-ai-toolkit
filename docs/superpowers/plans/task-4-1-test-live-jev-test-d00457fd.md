<!-- task-pipeline: validated -->
# 4.1 test: live Jev test (card d00457fd)

Parent: Story 4 "live test and docs" (de7e2839), milestone "ClassifierPort with Jev adapter" (e3bd09dc). Milestone design: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md` (gitignored, read by absolute path). This card narrows that design's Testing-table row for the live test; it adds no new behavior to the library.

## Scope

Create exactly one new file: `tests/live/test_jev_live.py` (the `tests/live/` directory is new; no `__init__.py` needed, matching `tests/unit/`).

Do not touch:
- any file under `py_ai_toolkit/`;
- `pyproject.toml` (no `live` marker registration, no `[tool.pytest]` section; there is no `--strict-markers`, so none is needed);
- `docs/guide/classifier.md`, `docs/guide/hooks.md`, `docs/api/tools.md`, `mkdocs.yml` (owned by sibling 4.2, e4860d92);
- `.github/workflows/test.yml`, the version string, or anything else.

Base: this worktree already contains Stories 1 to 3 (`PyAIToolkit.classify`, `aclose`, the classifier types exported from `py_ai_toolkit`, and `py_ai_toolkit/adapters/jev_adapter.py`). Main (v0.7.0) does not, so the work must stay on this branch.

## Observable behavior

Gating (both evaluated at collection time, at module level):
- `pytestmark = pytest.mark.skipif(not os.getenv("CLASSIFIER_API_KEY"), reason=...)`, so the whole module is skipped when the key is unset.
- `pytest.importorskip("typesafe_sdk")`, so a key without the `jev` extra still skips cleanly. `typesafe_sdk` is the import name used by `py_ai_toolkit/adapters/jev_adapter.py` and by the existing `tests/unit/test_jev_adapter.py`.
- CI runs `pytest tests/ --ignore=tests/test_run_task.py`, which collects `tests/live`. Without a key the module reports as skipped and the run stays green.

Construction: `PyAIToolkit()` with no arguments. With `CLASSIFIER_API_KEY` set, `__init__` builds the classifier (model from `CLASSIFIER_MODEL` or `"jev-latest"`, base URL from `CLASSIFIER_BASE_URL`). The LLM client it also builds does not fail without `LLM_*` vars: `InstructorAdapter` passes `api_key=""` to `AsyncOpenAI`, which only rejects `None`, and makes no network call at construction. No `LLMConfig` or `ClassifierConfig` is needed. `await toolkit.aclose()` must run in a `finally` block (or fixture teardown) so the SDK client is released even when an assertion fails.

The call: exactly one `await toolkit.classify(state, questions)` with a short English text `state` and a `dict` of three named questions:
- a `NoulQuestion` (with `NoulCriteria(true=..., false=...)`);
- a `ChoiceQuestion` whose `criteria` dict includes a `"none"` key plus at least one other option;
- a `ScoreQuestion` with N ordered level descriptions (2 <= N <= 10; use 3 to 5).

Assertions, shapes and ranges only, never specific values:
- Response: `isinstance(response, ClassifierResponse)`; `response.nouls`, `.choices`, `.scores` each have exactly the one question name submitted for that type.
- Noul: `0 <= noul.noul <= 1`. No confidence is asserted, since noul has none.
- Choice: `choice.choice in criteria`; `set(choice.probabilities) == set(criteria)`; `sum(probabilities.values()) == pytest.approx(1)`; `0 <= choice.confidence <= 1`.
- Score: `sum(probabilities.values()) == pytest.approx(1)`; `0 <= score.confidence <= 1`; `set(score.legend) == set(score.probabilities)`; `len(score.legend) == N`; legend keys are all `int` and form N consecutive integers; `min(legend) <= score.score <= max(legend)` (score is the probability-weighted average of the levels).
- Level indexing: the findings expected 1..N, but the code does not guarantee a base. `jev_adapter.py` copies the SDK keys unchanged apart from an `int(k)` coercion. The SDK's `ScoreAnswer.legend` is typed only as "keyed by integer score". The unit fixtures use 0-based (`test_jev_adapter.py`) and 1-based (`test_classifier.py`) keys. So assert "N consecutive ints" and not a hard-coded `range(1, N + 1)`. Tightening to 1..N is allowed only if a real keyed run shows it.
- Do not compare confidences across types, and do not derive or normalize anything.

## Error paths

- Key unset: the module is skipped (not failed, not errored).
- `typesafe_sdk` not installed: the module is skipped through `importorskip`.
- Key set but invalid, or the service is down: `classify` raises `ClassifierAdapterError` (mapped in `jev_adapter._to_adapter_error`). The test lets it propagate as a failure, with no catch, retry or skip. `aclose` still runs because of the `finally`.

## Async mechanics

Neither `pyproject.toml` nor a `conftest.py` sets `asyncio_mode`, so decorate the test with `@pytest.mark.asyncio` (pytest-asyncio >= 1.1.0 is in the dev extra). Plain pytest style, as in `tests/unit/`.

## Test list

Tier rule: the only placement convention is the milestone spec's Testing table. Network-free tests go in `tests/unit/`. The single real-service test goes in `tests/live/test_jev_live.py`, key-gated, and never runs in CI without a key. Network-hitting tests must not go in `tests/unit/`.

| Test | Tier | What it proves |
|---|---|---|
| `test_classify_live_one_question_of_each_type` | live (`tests/live/test_jev_live.py`) | One real `classify` call with a noul, a choice (with `"none"`), and a score question returns a `ClassifierResponse` whose answers satisfy every shape/range assertion above; `aclose` runs in `finally`. |

No unit-tier tests are added: the skip gating is pytest's own behavior, and the mapping/facade logic is already covered by Stories 1 to 3's unit tests.

## Verification

- Without `CLASSIFIER_API_KEY`: `pytest tests/ --ignore=tests/test_run_task.py` passes, and `tests/live/test_jev_live.py` is reported as skipped.
- With a valid key and the `jev` extra installed: `pytest tests/live -v` passes.

## Out of scope

LLM-backed or fallback adapter; chat/stream/embed on the classifier; normalization or derived confidence; streaming; a sync client; own retry logic; ori integration; the 0.7.0 to 0.8.0 version bump (left to bump2version); any docs or nav (card 4.2); registering a pytest marker.

---

# Live Jev Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one key-gated live test, `tests/live/test_jev_live.py`, that makes a single real `PyAIToolkit.classify` call with one noul, one choice (with `"none"`) and one score question, and asserts only shapes and ranges.

**Architecture:** Test-only card. The new module gates itself at collection time with a module-level `pytestmark` skipif on `CLASSIFIER_API_KEY` and a module-level `pytest.importorskip("typesafe_sdk")`. The single async test builds a bare `PyAIToolkit()` (which constructs the `JevAdapter` from `CLASSIFIER_*` env vars, see `py_ai_toolkit/core/toolkit.py:76-94`), calls `classify` once, and calls `aclose()` in a `finally`. No library code changes.

**Tech Stack:** Python 3.11, pytest >= 8.4.1, pytest-asyncio >= 1.1.0 (explicit `@pytest.mark.asyncio`, no `asyncio_mode`), `typesafe-sdk` via the `jev` extra, uv.

**Spec:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-1-test-live-jev-test-d00457fd/docs/superpowers/specs/task-4-1-test-live-jev-test-d00457fd-design.md` (prepended verbatim above). Milestone design: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md`.

All paths below are relative to the worktree root `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-1-test-live-jev-test-d00457fd`, on branch `m-classifier/task-4-1-test-live-jev-test-d00457fd` (cut from `m-classifier/task-3-3-feat-pyaitoolkit-dd20073d`). Run every command from that root.

## Global Constraints

- Exactly one new file: `tests/live/test_jev_live.py`. No `tests/live/__init__.py` (matches `tests/unit/`, which has none).
- Do not modify anything under `py_ai_toolkit/`, `pyproject.toml`, `.github/workflows/test.yml`, `docs/guide/classifier.md`, `docs/guide/hooks.md`, `docs/api/tools.md`, `mkdocs.yml`, or the version string.
- Gate: `pytestmark = pytest.mark.skipif(not os.getenv("CLASSIFIER_API_KEY"), reason=...)` and `pytest.importorskip("typesafe_sdk")`, both at module level.
- No pytest marker registration; no `[tool.pytest]` section.
- `@pytest.mark.asyncio` on the test, explicitly.
- Shapes and ranges only, never specific values. Noul has no confidence. Do not compare confidences across types; do not derive or normalize anything.
- Score legend: assert N consecutive ints, not a hard-coded `range(1, N + 1)`.
- `ClassifierAdapterError` from `classify` propagates as a failure: no catch, no retry, no skip.
- `await toolkit.aclose()` in a `finally`.
- Verification commands: `uv run pytest tests/ --ignore=tests/test_run_task.py` and `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F --ignore E501`.

## Review Focus

- `CLASSIFIER_API_KEY` exported as an empty string (`CLASSIFIER_API_KEY=`): a reasonable person expects a skip, not a failed call with an empty key. `not os.getenv(...)` treats `""` as unset; pinned by Task 1 Step 6.
- Key set but invalid (or service unreachable): expected a plain test failure whose message names `ClassifierAdapterError`, not a skip and not a hang, with `aclose` still run. Pinned by Task 1 Step 5 (wiring check with a bogus key).
- No key at all in CI, with the `jev` extra installed (CI installs `.[dev,jev]`): expected the module to be reported as skipped and the full suite green. Pinned by Task 1 Steps 4 and 7.
- Score levels coming back 0-based instead of 1-based: expected the test to pass either way, since the adapter only `int()`-coerces SDK keys. Pinned by the consecutive-ints assertion in the Task 1 test body.
- Choice probabilities covering only some criteria keys (e.g. omitting `"none"`): expected a failure, since the shape contract is one probability per option. Pinned by the `set(choice.probabilities) == set(CHOICE_CRITERIA)` assertion in the Task 1 test body.

---

### Task 1: Key-gated live classify test

**Files:**
- Create: `tests/live/test_jev_live.py`
- Test: `tests/live/test_jev_live.py` (live tier, per the milestone spec's Testing table)

**Interfaces:**
- Consumes (from Stories 1 to 3, already on this branch):
  - `py_ai_toolkit.PyAIToolkit()`; `async PyAIToolkit.classify(self, state: str | dict | list, questions: Mapping[str, Question], *, hooks: Hooks | None = None) -> ClassifierResponse` (`py_ai_toolkit/core/toolkit.py:229`); `async PyAIToolkit.aclose(self) -> None` (`py_ai_toolkit/core/toolkit.py:282`).
  - From `py_ai_toolkit` root: `ClassifierResponse`, `NoulQuestion`, `ChoiceQuestion`, `ScoreQuestion`.
  - From `py_ai_toolkit.core.domain.classifier` (not exported at the root): `NoulCriteria(true: JSONContent | None, false: JSONContent | None)`.
  - `ClassifierResponse.nouls -> dict[str, NoulAnswer]`, `.choices -> dict[str, ChoiceAnswer]`, `.scores -> dict[str, ScoreAnswer]`; `NoulAnswer.noul: float`; `ChoiceAnswer.choice: str`, `.probabilities: dict[str, float]`, `.confidence: float`; `ScoreAnswer.score: float`, `.probabilities: dict[int, float]`, `.confidence: float`, `.legend: dict[int, JSONContent]`.
- Produces: `tests/live/test_jev_live.py::test_classify_live_one_question_of_each_type`. Nothing else depends on it.

- [ ] **Step 1: Confirm the base has the classifier code**

Run: `git log --oneline -1 && grep -n "async def classify\|async def aclose" py_ai_toolkit/core/toolkit.py`
Expected: two matches (`async def classify(` near line 229, `async def aclose(` near line 282). If there are no matches, stop: the branch was not cut from `m-classifier/task-3-3-feat-pyaitoolkit-dd20073d`.

- [ ] **Step 2: Run the not-yet-existing live test to verify it fails (RED)**

Run: `CLASSIFIER_API_KEY=invalid-wiring-check uv run pytest tests/live/test_jev_live.py -v`
Expected: FAIL. pytest reports `ERROR: file or directory not found: tests/live/test_jev_live.py` and exits with code 4.

- [ ] **Step 3: Write the live test**

Create `tests/live/test_jev_live.py` with exactly this content:

```python
"""Live test against the real Jev service.

Skipped unless CLASSIFIER_API_KEY is set and the `jev` extra
(typesafe-sdk) is installed. Asserts shapes and ranges only.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("CLASSIFIER_API_KEY"),
    reason="CLASSIFIER_API_KEY not set; live Jev test skipped.",
)

pytest.importorskip("typesafe_sdk")

from py_ai_toolkit import (  # noqa: E402
    ChoiceQuestion,
    ClassifierResponse,
    NoulQuestion,
    PyAIToolkit,
    ScoreQuestion,
)
from py_ai_toolkit.core.domain.classifier import NoulCriteria  # noqa: E402

STATE = (
    "Hi, I was charged twice for my subscription this month. "
    "Please refund the duplicate charge as soon as possible."
)

NOUL_NAME = "billing"
CHOICE_NAME = "department"
SCORE_NAME = "urgency"

CHOICE_CRITERIA = {
    "billing": "Payments, charges, refunds or invoices.",
    "technical": "Bugs, errors or problems using the product.",
    "none": "None of the other departments apply.",
}

SCORE_LEVELS = [
    "Not urgent at all.",
    "Somewhat urgent.",
    "Urgent.",
    "Extremely urgent.",
]


def _questions():
    return {
        NOUL_NAME: NoulQuestion(
            instructions="Is this message about billing?",
            criteria=NoulCriteria(
                true="The message mentions a charge, payment or refund.",
                false="The message does not mention money at all.",
            ),
        ),
        CHOICE_NAME: ChoiceQuestion(
            instructions="Which department should handle this message?",
            criteria=CHOICE_CRITERIA,
        ),
        SCORE_NAME: ScoreQuestion(
            instructions="How urgent is this message?",
            criteria=SCORE_LEVELS,
        ),
    }


@pytest.mark.asyncio
async def test_classify_live_one_question_of_each_type():
    toolkit = PyAIToolkit()
    try:
        response = await toolkit.classify(STATE, _questions())
    finally:
        await toolkit.aclose()

    assert isinstance(response, ClassifierResponse)
    assert set(response.nouls) == {NOUL_NAME}
    assert set(response.choices) == {CHOICE_NAME}
    assert set(response.scores) == {SCORE_NAME}

    noul = response.nouls[NOUL_NAME]
    assert 0 <= noul.noul <= 1

    choice = response.choices[CHOICE_NAME]
    assert choice.choice in CHOICE_CRITERIA
    assert set(choice.probabilities) == set(CHOICE_CRITERIA)
    assert sum(choice.probabilities.values()) == pytest.approx(1)
    assert 0 <= choice.confidence <= 1

    score = response.scores[SCORE_NAME]
    n_levels = len(SCORE_LEVELS)
    assert sum(score.probabilities.values()) == pytest.approx(1)
    assert 0 <= score.confidence <= 1
    assert set(score.legend) == set(score.probabilities)
    assert len(score.legend) == n_levels
    assert all(isinstance(level, int) for level in score.legend)
    lowest = min(score.legend)
    assert sorted(score.legend) == list(range(lowest, lowest + n_levels))
    assert min(score.legend) <= score.score <= max(score.legend)
```

Notes for the implementer:
- `aclose()` sits in the `finally` around the single `classify` call, so the SDK client is released whether `classify` succeeds or raises; the assertions run after the client is closed because they touch only the returned pydantic objects.
- `ClassifierAdapterError` is deliberately not imported or caught: a bad key or a service outage must surface as a test failure.
- `NoulCriteria` is imported from `py_ai_toolkit.core.domain.classifier` because `py_ai_toolkit/__init__.py` does not export it (the existing `tests/unit/test_jev_adapter.py` imports it from the same place).
- The `# noqa: E402` comments match `tests/unit/test_jev_adapter.py`, where imports follow `importorskip`.

- [ ] **Step 4: Run without a key to verify the module is skipped**

Prerequisite: the `jev` extra must be installed or the skip reason will be the `importorskip` message instead (verified): run `uv sync --extra dev --extra jev` first.

Run: `env -u CLASSIFIER_API_KEY uv run pytest tests/live/test_jev_live.py -v -rs`
Expected: `1 skipped`, with the skip reason `CLASSIFIER_API_KEY not set; live Jev test skipped.` Exit code 0. No errors at collection.

- [ ] **Step 5: Run with a bogus key to verify the test is wired to the real call (not vacuous)**

Run: `CLASSIFIER_API_KEY=invalid-wiring-check uv run pytest tests/live/test_jev_live.py -v`
Expected: `1 failed`. The traceback ends in `py_ai_toolkit.core.domain.errors.ClassifierAdapterError` raised from `toolkit.classify` (message starting `Jev authentication failed` with network access, or `Network failure or timeout while calling Jev` without it). It must be reported as FAILED, not SKIPPED and not ERROR. If it is SKIPPED, the `jev` extra is missing locally: run `uv sync --extra dev --extra jev` and repeat.

- [ ] **Step 6: Run with an empty key to verify it still skips**

Run: `CLASSIFIER_API_KEY= uv run pytest tests/live/test_jev_live.py -v -rs`
Expected: `1 skipped` with the same reason as Step 4. Exit code 0.

- [ ] **Step 7: Run the full suite without a key (CI parity)**

Run: `env -u CLASSIFIER_API_KEY uv run pytest tests/ --ignore=tests/test_run_task.py -rs`
Expected: all tests pass; the summary includes `tests/live/test_jev_live.py` as skipped; exit code 0.

- [ ] **Step 8: (Only if a real key is available) Run against the live service (GREEN)**

Run: `uv run pytest tests/live -v` with a valid `CLASSIFIER_API_KEY` exported in the shell (and optionally `CLASSIFIER_MODEL` / `CLASSIFIER_BASE_URL`).
Expected: `1 passed`. If no real key is available, record in the card that the live run was not performed; Steps 4 to 7 remain the gate. Do not tighten the legend assertion to `range(1, n_levels + 1)` unless this run shows 1-based keys and the change is made deliberately.

- [ ] **Step 9: Lint the changed Python files**

Run: `git add tests/live/test_jev_live.py && git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F --ignore E501; ruff check --select E,F --ignore E501 tests/live/test_jev_live.py`
Expected: `All checks passed!` (the second command covers the new file before it is committed, since `main...HEAD` only sees committed changes).

- [ ] **Step 10: Confirm nothing else changed**

Run: `git status --porcelain`
Expected: only `A  tests/live/test_jev_live.py` (plus the untracked `docs/superpowers/` spec and plan files, which are not committed by this task unless the pipeline commits them separately). No changes under `py_ai_toolkit/`, `pyproject.toml`, `docs/guide/`, `docs/api/`, `mkdocs.yml` or `.github/`.

- [ ] **Step 11: Commit**

```bash
git add tests/live/test_jev_live.py
git commit -m "test: add key-gated live Jev classify test"
```

- [ ] **Step 12: Re-run both verification commands on the committed branch**

Run: `env -u CLASSIFIER_API_KEY uv run pytest tests/ --ignore=tests/test_run_task.py && git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F --ignore E501`
Expected: pytest exits 0 with the live module skipped; ruff prints `All checks passed!` for every `.py` file changed on the branch relative to `main` (that includes Stories 1 to 3 files, which are already lint-clean on their branches).
