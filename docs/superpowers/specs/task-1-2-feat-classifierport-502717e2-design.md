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
