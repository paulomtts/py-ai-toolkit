<!-- task-pipeline: validated -->
# Task 2.3 — JevAdapter error mapping and aclose (card 1ada6fbf)

Parent: Story 2 "Jev adapter and jev extra" (e01d0be7), milestone e3bd09dc. Narrows the milestone design `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md` (section "Errors", decisions C/D) to one subtask.

## Base

This worktree must be based on branch `m-classifier/task-2-2-feat-jevadapter-2385ae93` (2.2's classify mapping is not on `main`). The base already contains `py_ai_toolkit/adapters/jev_adapter.py` with `JevAdapter.classify` (lines 118-127) and `tests/unit/test_jev_adapter.py` with `_questions()` and `_adapter_returning(response)`.

## Scope

Files touched: `py_ai_toolkit/adapters/jev_adapter.py`, `tests/unit/test_jev_adapter.py`. Nothing else.

1. In `JevAdapter.classify`, wrap only the `await self._client.system_one(state, sdk_questions)` call in `try/except` for TypeSafe SDK errors, and raise `ClassifierAdapterError(message) from exc` (from `py_ai_toolkit/core/domain/errors.py`) so the original exception stays on `__cause__`. Question mapping (`_to_sdk_question`) stays outside the try block. Response mapping (`_to_classifier_response`) also stays outside it.
2. Add `async def aclose(self) -> None: await self._client.aclose()`. This overrides the default no-op `ClassifierPort.aclose` (`core/ports/classifier_port.py:30`).

## Error mapping (observable behavior)

Import exception classes from `typesafe_sdk`. If a name is not re-exported at the top level, import it from `typesafe_sdk._core.errors`. Match the most specific class first and the generic fallback last:

| SDK exception | `ClassifierAdapterError` message must convey |
|---|---|
| `TypeSafeAuthenticationError` (401) | invalid or missing Jev API key |
| `TypeSafeUnprocessableEntityError` (422) | request rejected as invalid; includes `exc.body` |
| `TypeSafeRateLimitError` (429) | rate limited; includes `exc.retry_after_ms` (may be `None`) |
| `TypeSafeInternalServerError` (5xx) | Jev unavailable or overloaded |
| `TypeSafeAPITimeoutError`, `TypeSafeAPIConnectionError` | network failure or timeout |
| `TypeSafeAPIResponseValidationError` | malformed response from Jev; includes `exc.field_path` |
| any other `TypeSafeError` (e.g. 400/403/404 `TypeSafeAPIError`) | generic wrapper including `str(exc)` |

Hierarchy constraints:
- `TypeSafeAPITimeoutError` subclasses `TypeSafeAPIConnectionError`, so the two share one branch.
- The response-validation, rate-limit, auth, unprocessable and internal-server errors all subclass `TypeSafeAPIError`. No branch may catch `TypeSafeAPIError` before those specific branches.
- `TypeSafeError` is the last branch.

## Error paths that must not change

- Never catch `Exception` or `BaseException`.
- Some exceptions are not `TypeSafeError` subclasses, for example the `TypeError` from `_to_sdk_question` for an unsupported question type, a pydantic `ValidationError`, or a plain `RuntimeError` raised by the client. These must propagate unchanged: same type, same object, and no wrapping.
- No retries of our own and no `retry=` override. The SDK's built-in retry is the only retry.

## Out of scope

- No change to `adapters/__init__.py` (it must not import `JevAdapter`).
- No error hook or `after_classify` on failure.
- No changes to the facade, toolkit, factory, hooks or docs (`PyAIToolkit.aclose` and `create_classifier` belong to other stories).
- No `pyproject.toml` or extra changes (2.1 is done).
- No changes to the classify mapping (2.2 is done).
- No normalization, streaming, sync client, LLM fallback adapter, ori integration or live tests.

## Tests

Test-placement rule: the repo has no formal tier doc. The milestone spec's file table (lines 65-68) places canned-SDK-response and stubbed-client adapter tests in `tests/unit/test_jev_adapter.py`, with no network and skipped via `importorskip` if the SDK is absent. `tests/live/` is reserved for the single keyed live test and is not touched by this card. So all tests below go in the **unit tier**, in `tests/unit/test_jev_adapter.py`. They use real SDK exception classes raised from a stubbed client (`SimpleNamespace(system_one=AsyncMock(side_effect=exc))`), and each async test has an explicit `@pytest.mark.asyncio`. Parametrization is allowed.

Build each exception with its real constructor and `httpx2.Headers`:
- `TypeSafeAPIError`-family errors: `(status, body, headers, message=None, endpoint=None)`.
- `TypeSafeRateLimitError`: set a `Retry-After` header so `retry_after_ms` is populated.
- `TypeSafeAPITimeoutError(timeout)`.
- `TypeSafeAPIResponseValidationError(status, body, headers, field_path, endpoint=None)`.
- `TypeSafeAPIConnectionError`: the plain message argument.

1. (unit) Auth error → raises `ClassifierAdapterError` with a message mentioning the API key.
2. (unit) Unprocessable entity → the message contains `exc.body`.
3. (unit) Rate limit → the message contains `exc.retry_after_ms`. Also cover the case without a `Retry-After` header, where the value is `None` and is still rendered without error.
4. (unit) Internal server error → the message says Jev is unavailable or overloaded.
5. (unit) Timeout and connection error, both → the network failure/timeout message.
6. (unit) Response validation error → the message contains `exc.field_path`.
7. (unit) An unmapped `TypeSafeAPIError` (e.g. 403) → generic wrapper whose message contains `str(exc)`.
8. (unit) For every mapped case, `raised.__cause__ is original_exc`. This can be folded into the parametrized tests above.
9. (unit) A non-TypeSafe exception (e.g. `RuntimeError`) from `system_one` propagates unchanged: same type and same object, not a `ClassifierAdapterError`.
10. (unit) `aclose()` awaits the client's `aclose` exactly once, using a stub client `SimpleNamespace(aclose=AsyncMock())` and `assert_awaited_once()`.

## Verification

- Full suite: `uv run --extra dev --extra jev pytest tests/ --ignore=tests/test_run_task.py`. A plain `uv run` does not install the `jev` extra (verified: `typesafe_sdk` is not importable in a fresh worktree `.venv`), so every Jev test would be silently skipped by `importorskip`.
- Lint: `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F`.
- No typecheck.
- `typesafe_sdk` must be importable in the worktree's environment (use the `--extra jev` command above). Confirm the new tests are reported as passed, not skipped by `importorskip`.

---

# JevAdapter Error Mapping and aclose Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `JevAdapter.classify` translate TypeSafe SDK failures into `ClassifierAdapterError` with actionable messages (original kept on `__cause__`), and make `JevAdapter.aclose()` close the underlying SDK client.

**Architecture:** One module-level helper `_to_adapter_error(exc: TypeSafeError) -> ClassifierAdapterError` in `py_ai_toolkit/adapters/jev_adapter.py` dispatches with ordered `isinstance` checks (specific classes first, generic fallback last). `classify` wraps only the `system_one` await in `try/except TypeSafeError` and re-raises `_to_adapter_error(exc) from exc`; question mapping stays before the `try`, response mapping after it. `aclose` overrides the port's no-op and awaits `self._client.aclose()`.

**Tech Stack:** Python 3.13, `typesafe_sdk` (jev extra, uses `httpx2`), pytest + pytest-asyncio (explicit `@pytest.mark.asyncio`), `unittest.mock.AsyncMock`, uv, ruff.

**Spec:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf/docs/superpowers/specs/task-2-3-feat-jevadapter-1ada6fbf-design.md` (prepended verbatim above).

## Global Constraints

- Work in worktree `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf` on branch `m-classifier/task-2-3-feat-jevadapter-1ada6fbf`, cut from `m-classifier/task-2-2-feat-jevadapter-2385ae93`. Assume nothing beyond 2.2's code exists.
- Files touched: `py_ai_toolkit/adapters/jev_adapter.py`, `tests/unit/test_jev_adapter.py`. Nothing else.
- Never catch `Exception` or `BaseException`. Non-`TypeSafeError` exceptions propagate unchanged (same object).
- Raise `ClassifierAdapterError(message) from exc` — the original stays on `__cause__`.
- `TypeSafeError` is the last branch; no branch catches `TypeSafeAPIError` before the specific subclasses.
- No retries of our own, no `retry=` override, no error hook, no change to `py_ai_toolkit/adapters/__init__.py`, no pyproject/facade/factory/docs changes, no classify-mapping changes, no live tests.
- All tests go in the unit tier: `tests/unit/test_jev_adapter.py` (the existing file from 2.2; it is guarded by `typesafe_sdk = pytest.importorskip("typesafe_sdk")` and every import after it carries `# noqa: E402`).
- Every test run uses `uv run --extra dev --extra jev ...`. This is the repo's verification command `uv run pytest tests/ --ignore=tests/test_run_task.py` with the extras added: without `--extra jev`, `typesafe_sdk` is not importable and the whole file is skipped, which would make RED and GREEN meaningless. A run that reports the file as `SKIPPED` is a failed step, not a pass.

## Review Focus

- A `TypeSafeAPITimeoutError` must land in the network branch, not the generic one, even though it is also a `TimeoutError` — pinned by the `timeout` case in Task 1's parametrized test.
- A 400 `TypeSafeBadRequestError` must hit the generic branch and must not be mistaken for the 422 "invalid request" branch — pinned by the `bad-request-400-generic` case in Task 1.
- A 422 with an empty body (`body=None`) must still produce a message without raising inside the mapper — pinned by the `unprocessable-422-no-body` case in Task 1.
- A 429 with no `Retry-After` header (`retry_after_ms is None`) must still render — pinned by the `rate-limit-no-retry-after` case in Task 1.
- A bug in response mapping (e.g. a malformed response object raising `AttributeError` in `_to_classifier_response`) must propagate unchanged, not be dressed up as a Jev error — pinned by `test_response_mapping_error_propagates_unchanged` in Task 1.

---

### Task 1: Map TypeSafe SDK errors to ClassifierAdapterError in classify

**Files:**
- Modify: `py_ai_toolkit/adapters/jev_adapter.py:8-26` (imports), add helper after `_to_classifier_response` (after line 97), modify `classify` at lines 118-127
- Test: `tests/unit/test_jev_adapter.py` (imports at lines 1-22, new helper after `_adapter_returning` at lines 72-75, new tests appended at end of file)

**Interfaces:**
- Consumes: `ClassifierAdapterError(message: str = "")` from `py_ai_toolkit.core.domain.errors` (has `.message`); SDK classes re-exported at `typesafe_sdk` top level: `TypeSafeError`, `TypeSafeAPIError`, `TypeSafeAuthenticationError`, `TypeSafeUnprocessableEntityError`, `TypeSafeRateLimitError`, `TypeSafeInternalServerError`, `TypeSafeAPIConnectionError`, `TypeSafeAPITimeoutError`, `TypeSafeAPIResponseValidationError`, `TypeSafeBadRequestError`, `TypeSafePermissionDeniedError`, `TypeSafeNotFoundError`. Constructors (verified in the installed SDK `typesafe_sdk/_core/errors.py`): `TypeSafeAPIError(status, body, headers: httpx2.Headers, message=None, endpoint=None)`; `TypeSafeRateLimitError` same signature, sets `retry_after_ms` from the `retry-after` header in seconds × 1000 (so `"2"` → `2000.0`) or `None`; `TypeSafeAPITimeoutError(timeout)`, `str()` = `"Request timed out (timeout=5.0)."`; `TypeSafeAPIResponseValidationError(status, body, headers, field_path, endpoint=None)`; `TypeSafeAPIConnectionError("msg")` plain `Exception` ctor; `TypeSafeAPIError.__str__` = `"{status} {message}"` where message falls back to the body's `detail`/`message`/`error` string.
- Produces: `_to_adapter_error(exc: TypeSafeError) -> ClassifierAdapterError` (module-private in `jev_adapter.py`); `JevAdapter.classify` now raises `ClassifierAdapterError` (with `__cause__` = SDK exception) for any `TypeSafeError` from `system_one`. Test helper `_adapter_raising(exc: BaseException) -> JevAdapter` in the test module.

- [ ] **Step 1: Add test imports and the raising-adapter helper**

In `tests/unit/test_jev_adapter.py`, replace the import block (lines 11-22):

```python
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
```

with:

```python
import httpx2  # noqa: E402

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
from py_ai_toolkit.core.domain.errors import ClassifierAdapterError  # noqa: E402
```

Then, directly after `_adapter_returning` (after line 75), add:

```python
def _adapter_raising(exc):
    adapter = JevAdapter(api_key="test-key")
    adapter._client = SimpleNamespace(system_one=AsyncMock(side_effect=exc))
    return adapter
```

- [ ] **Step 2: Write the failing error-mapping tests**

Append to the end of `tests/unit/test_jev_adapter.py`:

```python
def _headers(**values):
    return httpx2.Headers(values)


ERROR_CASES = [
    pytest.param(
        typesafe_sdk.TypeSafeAuthenticationError(
            401, {"detail": "bad key"}, _headers()
        ),
        lambda exc: ["invalid or missing jev api key"],
        id="auth-401",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeUnprocessableEntityError(
            422, {"detail": "criteria must not be empty"}, _headers()
        ),
        lambda exc: ["rejected the request as invalid", str(exc.body)],
        id="unprocessable-422",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeUnprocessableEntityError(422, None, _headers()),
        lambda exc: ["rejected the request as invalid", "None"],
        id="unprocessable-422-no-body",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeRateLimitError(
            429, {"detail": "slow down"}, _headers(**{"retry-after": "2"})
        ),
        lambda exc: ["rate limited", "retry_after_ms=2000.0"],
        id="rate-limit-429",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeRateLimitError(429, {"detail": "slow down"}, _headers()),
        lambda exc: ["rate limited", "retry_after_ms=None"],
        id="rate-limit-no-retry-after",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeInternalServerError(
            503, {"detail": "overloaded"}, _headers()
        ),
        lambda exc: ["unavailable or overloaded"],
        id="internal-server-5xx",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeAPITimeoutError(5.0),
        lambda exc: ["network failure or timeout", str(exc)],
        id="timeout",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeAPIConnectionError("connection refused"),
        lambda exc: ["network failure or timeout", "connection refused"],
        id="connection",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeAPIResponseValidationError(
            200, {"answers": {}}, _headers(), "answers.tone.confidence"
        ),
        lambda exc: ["malformed response from jev", "answers.tone.confidence"],
        id="response-validation",
    ),
    pytest.param(
        typesafe_sdk.TypeSafePermissionDeniedError(
            403, {"detail": "model not enabled"}, _headers()
        ),
        lambda exc: ["jev request failed", str(exc)],
        id="permission-403-generic",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeBadRequestError(
            400, {"detail": "state too long"}, _headers()
        ),
        lambda exc: ["jev request failed", str(exc)],
        id="bad-request-400-generic",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeError("client misconfigured"),
        lambda exc: ["jev request failed", "client misconfigured"],
        id="base-typesafe-error-generic",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("original", "expected_fragments"), ERROR_CASES)
async def test_sdk_error_mapped_to_classifier_adapter_error(
    original, expected_fragments
):
    adapter = _adapter_raising(original)

    with pytest.raises(ClassifierAdapterError) as excinfo:
        await adapter.classify(STATE, _questions())

    raised = excinfo.value
    assert raised.__cause__ is original
    assert raised.message == str(raised)
    for fragment in expected_fragments(original):
        assert fragment.lower() in raised.message.lower()


def test_timeout_case_is_both_timeout_and_connection_error():
    exc = typesafe_sdk.TypeSafeAPITimeoutError(5.0)
    assert isinstance(exc, typesafe_sdk.TypeSafeAPIConnectionError)
    assert isinstance(exc, TimeoutError)
```

Note on `test_timeout_case_is_both_timeout_and_connection_error`: it documents the hierarchy trap the mapper's ordering depends on; it passes before and after implementation and is a guard against a future SDK changing the hierarchy, not a RED test.

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf && uv run --extra dev --extra jev pytest tests/unit/test_jev_adapter.py -k "sdk_error_mapped" -v`
Expected: 12 tests FAIL (none SKIPPED). Each fails because the raw SDK exception escapes `pytest.raises(ClassifierAdapterError)`, e.g. `typesafe_sdk._core.errors.TypeSafeAuthenticationError: 401 bad key`. If the output says the module was skipped (`could not import 'typesafe_sdk'`), stop: the extras are not installed; rerun with `uv sync --extra dev --extra jev` first.

- [ ] **Step 4: Write the propagation guard tests**

Append to the end of `tests/unit/test_jev_adapter.py`:

```python
@pytest.mark.asyncio
async def test_non_sdk_error_propagates_unchanged():
    original = RuntimeError("stub client exploded")
    adapter = _adapter_raising(original)

    with pytest.raises(RuntimeError) as excinfo:
        await adapter.classify(STATE, _questions())

    assert excinfo.value is original
    assert not isinstance(excinfo.value, ClassifierAdapterError)


@pytest.mark.asyncio
async def test_response_mapping_error_propagates_unchanged():
    adapter = _adapter_returning(SimpleNamespace(model="jev-2026-09"))

    with pytest.raises(AttributeError) as excinfo:
        await adapter.classify(STATE, _questions())

    assert not isinstance(excinfo.value, ClassifierAdapterError)
    assert excinfo.value.__cause__ is None
```

These pin behaviour that already holds on the 2.2 base (nothing is caught yet); they exist so the implementation in Step 6 cannot widen the `except` or pull `_to_classifier_response` into the `try`. The `TypeError` from `_to_sdk_question` is already pinned by the existing `test_unknown_question_type_raises_before_call` (`pytest.raises(TypeError)` plus `system_one.assert_not_awaited()`).

- [ ] **Step 5: Run the guard tests to confirm they pass on the base**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf && uv run --extra dev --extra jev pytest tests/unit/test_jev_adapter.py -k "propagates_unchanged or timeout_case" -v`
Expected: 3 PASSED, 0 SKIPPED.

- [ ] **Step 6: Implement the mapping**

In `py_ai_toolkit/adapters/jev_adapter.py`, replace line 11:

```python
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score, SystemOneResponse
```

with:

```python
from typesafe_sdk import (
    AsyncTypeSafeClient,
    Choice,
    Noul,
    Score,
    SystemOneResponse,
    TypeSafeAPIConnectionError,
    TypeSafeAPIResponseValidationError,
    TypeSafeAuthenticationError,
    TypeSafeError,
    TypeSafeInternalServerError,
    TypeSafeRateLimitError,
    TypeSafeUnprocessableEntityError,
)
```

Replace line 26:

```python
from py_ai_toolkit.core.ports import ClassifierPort
```

with:

```python
from py_ai_toolkit.core.domain.errors import ClassifierAdapterError
from py_ai_toolkit.core.ports import ClassifierPort
```

Insert this function between `_to_classifier_response` and `class JevAdapter` (after the `return ClassifierResponse(...)` block ending at original line 97):

```python
def _to_adapter_error(exc: TypeSafeError) -> ClassifierAdapterError:
    # Order matters: every specific class below except the connection pair
    # subclasses TypeSafeAPIError, and TypeSafeAPITimeoutError subclasses
    # TypeSafeAPIConnectionError. The generic TypeSafeError branch is last.
    if isinstance(exc, TypeSafeAuthenticationError):
        return ClassifierAdapterError(
            f"Jev authentication failed: invalid or missing Jev API key ({exc})"
        )
    if isinstance(exc, TypeSafeUnprocessableEntityError):
        return ClassifierAdapterError(
            f"Jev rejected the request as invalid: {exc.body}"
        )
    if isinstance(exc, TypeSafeRateLimitError):
        return ClassifierAdapterError(
            f"Jev rate limited the request (retry_after_ms={exc.retry_after_ms})"
        )
    if isinstance(exc, TypeSafeInternalServerError):
        return ClassifierAdapterError(f"Jev is unavailable or overloaded: {exc}")
    if isinstance(exc, TypeSafeAPIConnectionError):
        return ClassifierAdapterError(
            f"Network failure or timeout while calling Jev: {exc}"
        )
    if isinstance(exc, TypeSafeAPIResponseValidationError):
        return ClassifierAdapterError(
            f"Malformed response from Jev at field {exc.field_path!r}"
        )
    return ClassifierAdapterError(f"Jev request failed: {exc}")
```

Replace the body of `classify` (original lines 123-127):

```python
        sdk_questions = {
            name: _to_sdk_question(question) for name, question in questions.items()
        }
        response = await self._client.system_one(state, sdk_questions)
        return _to_classifier_response(response)
```

with:

```python
        sdk_questions = {
            name: _to_sdk_question(question) for name, question in questions.items()
        }
        try:
            response = await self._client.system_one(state, sdk_questions)
        except TypeSafeError as exc:
            raise _to_adapter_error(exc) from exc
        return _to_classifier_response(response)
```

- [ ] **Step 7: Run the whole test file to verify everything passes**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf && uv run --extra dev --extra jev pytest tests/unit/test_jev_adapter.py -v`
Expected: all tests PASSED (the 12 `test_sdk_error_mapped_to_classifier_adapter_error[...]` cases, the 3 guard tests, and every pre-existing 2.2 test including `test_adapters_package_does_not_import_sdk` and `test_unknown_question_type_raises_before_call`), 0 SKIPPED, 0 FAILED.

- [ ] **Step 8: Commit**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf
git add py_ai_toolkit/adapters/jev_adapter.py tests/unit/test_jev_adapter.py
git commit -m "feat: map TypeSafe SDK errors to ClassifierAdapterError in JevAdapter"
```

---

### Task 2: JevAdapter.aclose closes the SDK client

**Files:**
- Modify: `py_ai_toolkit/adapters/jev_adapter.py` (add method at the end of `class JevAdapter`, after `classify`)
- Test: `tests/unit/test_jev_adapter.py` (append at end of file)

**Interfaces:**
- Consumes: `ClassifierPort.aclose(self) -> None` (default no-op at `py_ai_toolkit/core/ports/classifier_port.py:30`); `self._client` set in `JevAdapter.__init__`.
- Produces: `JevAdapter.aclose(self) -> None` (async) awaiting `self._client.aclose()` once. Later stories' `PyAIToolkit.aclose` will call this; not part of this card.

- [ ] **Step 1: Write the failing test**

Append to the end of `tests/unit/test_jev_adapter.py`:

```python
@pytest.mark.asyncio
async def test_aclose_closes_sdk_client():
    adapter = JevAdapter(api_key="test-key")
    client_aclose = AsyncMock()
    adapter._client = SimpleNamespace(aclose=client_aclose)

    await adapter.aclose()

    client_aclose.assert_awaited_once()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf && uv run --extra dev --extra jev pytest tests/unit/test_jev_adapter.py::test_aclose_closes_sdk_client -v`
Expected: FAIL with `AssertionError: Expected mock to have been awaited once. Awaited 0 times.` (the inherited `ClassifierPort.aclose` is a no-op). Not SKIPPED.

- [ ] **Step 3: Implement aclose**

In `py_ai_toolkit/adapters/jev_adapter.py`, append inside `class JevAdapter`, after the `classify` method (after `return _to_classifier_response(response)`):

```python

    async def aclose(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf && uv run --extra dev --extra jev pytest tests/unit/test_jev_adapter.py::test_aclose_closes_sdk_client -v`
Expected: PASSED.

- [ ] **Step 5: Commit**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf
git add py_ai_toolkit/adapters/jev_adapter.py tests/unit/test_jev_adapter.py
git commit -m "feat: close the TypeSafe client in JevAdapter.aclose"
```

---

### Task 3: Full verification

**Files:** none modified (fix-forward only if a check fails, in the two files owned by this card).

**Interfaces:**
- Consumes: Tasks 1-2.
- Produces: verified branch.

- [ ] **Step 1: Run the full suite with the jev extra**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf && uv run --extra dev --extra jev pytest tests/ --ignore=tests/test_run_task.py -rs`
Expected: 0 failed. In the `-rs` skip summary, `tests/unit/test_jev_adapter.py` must NOT appear (any skip there means `typesafe_sdk` was not importable and the card is not verified). Skips elsewhere (e.g. `tests/live/` without a key) are acceptable.

- [ ] **Step 2: Run the repo's verification command as given**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf && uv run pytest tests/ --ignore=tests/test_run_task.py`
Expected: 0 failed. (If the default environment lacks the jev extra, `tests/unit/test_jev_adapter.py` will show as skipped here; Step 1 is the run that proves the new tests execute.)

- [ ] **Step 3: Lint the changed Python files**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf && git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F`
Expected: `All checks passed!` (the `import httpx2` and `ClassifierAdapterError` imports in the test module carry `# noqa: E402` because they follow `pytest.importorskip`).

- [ ] **Step 4: Confirm scope**

Run: `cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-3-feat-jevadapter-1ada6fbf && git diff --name-only m-classifier/task-2-2-feat-jevadapter-2385ae93...HEAD`
Expected: exactly `py_ai_toolkit/adapters/jev_adapter.py` and `tests/unit/test_jev_adapter.py` (plus this card's spec/plan files under `docs/superpowers/` if they are committed). `py_ai_toolkit/adapters/__init__.py` and `pyproject.toml` must not appear.
