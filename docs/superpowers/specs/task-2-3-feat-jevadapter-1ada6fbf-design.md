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
