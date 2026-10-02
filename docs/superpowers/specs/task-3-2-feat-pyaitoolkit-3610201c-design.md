# Task 3.2: PyAIToolkit classifier construction and config resolution (card 3610201c)

Parent: Story 3 "facade and factory" (42134774), milestone e3bd09dc. Authority: `docs/superpowers/specs/2026-10-01-classifier-port-design.md` (present in the main checkout at `/home/mtts/Code/libs/py-ai-toolkit`, not tracked in this worktree), sections "Config" and "Constructor and behavior", plus Decision A (env resolved at init) and Decision B (activate on a passed config OR a non-empty `CLASSIFIER_API_KEY`). This card narrows that design; it does not change it.

## Base

Build on top of the 3.1 work (branch `m-classifier/task-3-1-feat-create-01df4db2`, commit fa48f8c), which this worktree already contains: `ClassifierConfig` in `py_ai_toolkit/core/domain/classifier.py` (all fields `str | None = None`, no env defaults), `ClassifierPort` exported from `py_ai_toolkit/core/ports`, and `create_classifier(api_key, model="jev-latest", base_url=None)` in `py_ai_toolkit/factories.py`, which lazily imports `JevAdapter` and raises the `[jev]` install-hint `ImportError` when the SDK is missing.

## Scope

Files: `py_ai_toolkit/core/toolkit.py` and `tests/unit/test_classifier.py` only.

- `PyAIToolkit.__init__` gains one last, optional keyword: `classifier_config: ClassifierConfig | None = None`. Existing parameters and their order are unchanged.
- New attribute `self.classifier: ClassifierPort | None`.
- Imports: `create_classifier` added to the existing `from py_ai_toolkit.factories import (...)` block; `ClassifierConfig` from `py_ai_toolkit.core.domain.classifier`; `ClassifierPort` from `py_ai_toolkit.core.ports`. `core/` must not import `jev_adapter` or `typesafe_sdk`.
- `LLMConfig` and the existing LLM client, prompt formatter, model handler and alternative-client construction are untouched.

## Observable behavior

Resolution happens inside `__init__` (never at import time). With `cfg` being `classifier_config`, or a value with all fields `None` when it is `None`:

- `api_key = cfg.api_key or os.getenv("CLASSIFIER_API_KEY")`
- `model = cfg.model or os.getenv("CLASSIFIER_MODEL") or "jev-latest"`
- `base_url = cfg.base_url or os.getenv("CLASSIFIER_BASE_URL")`

Activation:

- If `classifier_config is not None` or the resolved `api_key` is non-empty, `self.classifier = create_classifier(api_key, model, base_url)`.
- Otherwise `self.classifier = None` and construction behaves exactly as it does today.

Because resolution is at init, env vars set after `py_ai_toolkit` is imported are honored.

## Error paths

- `classifier_config` passed but no key resolvable (config key empty/None and `CLASSIFIER_API_KEY` unset or empty): raise `ValueError("ClassifierConfig requires an api_key or CLASSIFIER_API_KEY.")` before calling the factory.
- Key resolved but the `jev` extra is missing: `create_classifier`'s `ImportError` (install hint, chained) propagates out of `__init__` unchanged (fail fast, no wrapping, no fallback to `None`).
- Any other exception from `create_classifier` propagates unchanged.

## Out of scope

Sibling 3.3 (dd20073d): `classify()`, `aclose()`, firing `before_classify`/`after_classify` hooks, the unconfigured-call `ClassifierAdapterError` guard, the empty-questions `ValueError`, and exports in `py_ai_toolkit/__init__.py`. Already-done work: hook contexts (1.3), the adapter (2.x), the factory (3.1). Story-wide exclusions: LLM-backed or fallback adapter, chat/stream/embed on the classifier, normalization or derived confidence, streaming, sync client, own retry logic, ori integration.

## Tests

Placement rule: the classifier spec's "Testing" section (no standalone testing standard exists in this repo) puts facade, config-resolution and factory tests in `tests/unit/test_classifier.py`, using a fake `ClassifierPort` or a patched factory and no network. Every test below is therefore **unit tier, appended to the existing `tests/unit/test_classifier.py`** (do not recreate or duplicate the file; no integration or live tests). Style: plain pytest functions with `monkeypatch`/`unittest.mock`. Each test constructs the toolkit with an `LLMConfig(api_key=..., model=...)` (or sets `LLM_*` env) so the existing LLM client builds, and clears or sets `CLASSIFIER_API_KEY`, `CLASSIFIER_MODEL` and `CLASSIFIER_BASE_URL` via `monkeypatch` so ambient env cannot leak in. Unless stated, the factory is patched where toolkit looks it up, `monkeypatch.setattr("py_ai_toolkit.core.toolkit.create_classifier", fake)`, with `fake` recording its args and returning a `ClassifierPort` fake.

1. No config, classifier env cleared: `toolkit.classifier is None`, the fake factory is not called, and `llm_client`, `prompt_formatter`, `model_handler` are still built. (unit, `tests/unit/test_classifier.py`)
2. No config, `CLASSIFIER_API_KEY` (and model/base URL) set via `monkeypatch.setenv` after import: the factory receives the env values and `toolkit.classifier` is the object it returned. (unit, `tests/unit/test_classifier.py`)
3. Explicit `ClassifierConfig(api_key, model, base_url)` with all three env vars also set to different values: the factory receives the config values for each field. (unit, `tests/unit/test_classifier.py`)
4. Model fallback: config/key present without a model and `CLASSIFIER_MODEL` set gives the env model; with `CLASSIFIER_MODEL` cleared gives `"jev-latest"`. Base URL with nothing set is passed as `None`. (unit, `tests/unit/test_classifier.py`)
5. `ClassifierConfig()` with no key and classifier env cleared raises `ValueError` with the exact message `"ClassifierConfig requires an api_key or CLASSIFIER_API_KEY."`, and the factory is not called. (unit, `tests/unit/test_classifier.py`)
6. Empty `CLASSIFIER_API_KEY=""` with no config: `toolkit.classifier is None` (empty key does not activate). (unit, `tests/unit/test_classifier.py`)
7. Missing extra: real factory (not patched), a non-empty key (config or env), `monkeypatch.delitem(sys.modules, "py_ai_toolkit.adapters.jev_adapter", raising=False)` and `monkeypatch.setitem(sys.modules, "typesafe_sdk", None)` as in the existing `test_create_classifier_without_sdk_raises_install_hint`: `PyAIToolkit(...)` raises `ImportError` whose message is the install hint. (unit, `tests/unit/test_classifier.py`)

Use `pytest.importorskip("typesafe_sdk")` only if a test needs the real SDK; none of the above should.
