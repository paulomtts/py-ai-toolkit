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
