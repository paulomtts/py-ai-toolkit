# Task 4.2 (e4860d92): docs for the classifier guide, hooks, API and nav

Parent: Story 4 "live test and docs" (de7e2839). Milestone: "ClassifierPort with Jev adapter" (e3bd09dc). Blocked by 4.1 (d00457fd), which is done.

## Base

This worktree (`task-4-2-docs-classifier-e4860d92`) already contains the classifier code from stories 1 to 3 (`py_ai_toolkit/core/domain/classifier.py`, `core/hooks.py`, `core/toolkit.py`, `adapters/jev_adapter.py`, `factories.py`). No rebase is needed. All documentation must describe that code as built, not the milestone design doc.

## Scope

This card changes docs only. The owned files are:

- `docs/guide/classifier.md` (new)
- `docs/guide/hooks.md`
- `docs/api/tools.md`
- `mkdocs.yml`

Out of scope: source edits, `tests/` (including `tests/live/`), `pyproject.toml`, and the version bump (it stays at 0.7.0 and is left to bump2version). Also out of scope: the `.claude/commands/py-ai-toolkit.md` skill doc and any build output under `site/`. The docs may name the following only as non-features: an LLM-backed or fallback adapter, chat/stream/embed on the classifier, normalization or derived confidence, streaming, a sync client, the toolkit's own retry logic, and consumer integration. Use no emojis and match the existing `docs/guide` and `docs/api` style.

## 1. `docs/guide/classifier.md` (new)

The guide must state each of these facts and stay consistent with the code:

- **What Jev is.** Jev is TypeSafe AI's classifier. It answers structured questions about a `state` (a str, dict or list) and cannot generate text.
- **Install.** `pip install 'py-ai-toolkit[jev]'`. The extra pulls in `typesafe-sdk>=0.6.0`.
- **Config.** `ClassifierConfig(api_key, model, base_url)`, all `str | None`. The matching env vars are `CLASSIFIER_API_KEY`, `CLASSIFIER_MODEL` (falls back to `"jev-latest"`) and `CLASSIFIER_BASE_URL`. The env is read in `PyAIToolkit.__init__`, and an explicit config value beats the env, field by field.
- **Activation** (`toolkit.py:76-94`):
  - A classifier is built only if `classifier_config` is passed or `CLASSIFIER_API_KEY` is set. Otherwise `toolkit.classifier is None`.
  - If a `classifier_config` is passed and neither it nor the env provides a key, the constructor raises `ValueError("ClassifierConfig requires an api_key or CLASSIFIER_API_KEY.")`.
  - If the extra is missing, the constructor raises `ImportError` (from `create_classifier`).
- **Examples.** Give one example each for `NoulQuestion`, `ChoiceQuestion` and `ScoreQuestion`. Read the results through `response.nouls`, `.choices` and `.scores`, using the answer fields: `noul`; `choice` with `probabilities` and `confidence`; `score` with `probabilities` (int keys), `confidence` and `legend` (int keys).
  - `NoulCriteria` is not exported at the top level. Import it from `py_ai_toolkit.core.domain.classifier`.
  - All other types import from `py_ai_toolkit`.
- **Raw values.**
  - `NoulAnswer` has no confidence.
  - `confidence` on a choice and on a score are not comparable with each other.
  - The toolkit does not normalize anything. Do not present `max(p, 1-p)` or any derived figure as a confidence.
- **Patterns.**
  - Choices are single-select and cannot abstain, so recommend adding a "none" option to the criteria.
  - Threshold `noul` directly.
  - Always set `instructions`. This is a recommendation, not enforced.
- **Validation.** Pydantic `ValidationError` is raised at question construction: choice `criteria` needs 1 to 255 entries, and score `criteria` needs 2 to 10. Do not claim that `classify()` rejects empty question names: `validate_question_names` exists but nothing calls it. Only answer names on `ClassifierResponse` are validated.
- **Errors at call time.**
  - `ClassifierAdapterError` when the classifier is unconfigured, using the exact message from `toolkit.py:249-250`.
  - `ValueError("questions must not be empty.")` for empty questions.
  - `ClassifierAdapterError` for every SDK or API failure, with the original exception on `__cause__`. The failures are: authentication, unprocessable entity (the message includes the body), rate limit (includes `retry_after_ms`), internal server error, connection or timeout, response validation (includes `field_path`), and generic `TypeSafeError`.
  - The SDK retries by default (2 retries within a 30 s budget). The toolkit adds no retries of its own.
- **Hooks.** Mention `before_classify` and `after_classify` briefly and link to the hooks guide.
- **Lifecycle.** Call `await toolkit.aclose()`. It is a no-op when no classifier is configured.
- **Limitations.** Jev is weak at arithmetic and dates, and with noisy context and adversarial content. Its context window is bounded. Its Portuguese support is undocumented.
- **Data privacy.** The `state` is sent to TypeSafe AI (api.typesafe.ai), a third-party processor, so consumers must list it in their sub-processor documentation.
- **Status.** Jev has been pre-GA early access since 2026-09-15.

## 2. `docs/guide/hooks.md`

- **Available Hooks table (lines 28-38).** Add `before_classify` -> `BeforeClassifyContext` (fires before the classifier call) and `after_classify` -> `AfterClassifyContext` (fires after a successful classifier response). Fix the count in the "fires hooks at seven points" sentence to match the rows. The table already omits `after_embed` and `after_embed_batch`, which are real `Hooks` fields, so add rows for them too. That makes eleven, which matches the `Hooks` dataclass. Context type names for the embed rows come from `core/hooks.py` (`AfterEmbedContext`, `AfterEmbedBatchContext`).
- **Method table (line 42).** Add a "Classify hooks" column. The `classify()` row is `--` in every other column and `before_classify`, `after_classify` in the new one. Every existing row gets `--` in the new column.
- **Context sections.** Add `### BeforeClassifyContext` (`state`, `questions`, `model`) and `### AfterClassifyContext` (`response`, `model`, `elapsed_ms`, `usage: ClassifierUsage`) after `OnRetryContext`, in the existing field-table format.
- **Behaviour notes.**
  - `before_classify` fires only after the guards pass, so it does not fire when the classifier is unconfigured or `questions` is empty.
  - `after_classify` fires on success only.
  - Hooks only observe; they do not change the call.
- **All Imports.** Add both contexts to the import block, from `py_ai_toolkit.core.hooks`.

## 3. `docs/api/tools.md`

- **Constructor (lines 5-35).** Document the `classifier_config: ClassifierConfig | None = None` kwarg, its env fallback and its activation rule.
- **Methods.** After `embed_batch()` and before `run_task()` (line 186), add `### classify()` and `### aclose()` in the existing format: signature, Parameters, Returns, Example and a `---` separator.
  - The `classify` signature is `async def classify(state: str | dict | list, questions: Mapping[str, Question], *, hooks: Hooks | None = None) -> ClassifierResponse`. Its Raises entries are the same as in the guide.
  - The `aclose` signature is `async def aclose() -> None`.
- **Supporting Classes (line 292 onward).** Add `ClassifierConfig`, `ClassifierResponse` (`model`, `answers`, `usage`, and the properties `nouls`, `choices` and `scores`), `NoulQuestion`, `ChoiceQuestion`, `ScoreQuestion`, `NoulCriteria` (with its import path), `NoulAnswer`, `ChoiceAnswer`, `ScoreAnswer`, the `Question` and `Answer` discriminated unions, `ClassifierUsage` (`input_tokens`, `output_tokens`, both `int | None`) and `ClassifierAdapterError`. Field types must match `classifier.py` exactly.

## 4. `mkdocs.yml`

Under `nav` -> Guide, add `- Classifier: guide/classifier.md` right after `- Hooks: guide/hooks.md` (line 50).

## Verification

- `uv run mkdocs build --strict` passes, with no broken links or missing nav targets.
- `site/` changes are not committed.
- Every import line in the docs resolves against this worktree: top-level names come from `py_ai_toolkit.__all__`, `NoulCriteria` from `core.domain.classifier`, and the hook contexts from `core.hooks`.
- `git diff --name-only` lists only the four owned files.

## Tests

None. This card changes docs only, and the repo has no testing standards doc. By the conventional layout (see the milestone design's Testing section), any later behaviour test would go in `tests/unit/` (plain pytest), and key-gated live tests stay in `tests/live/test_jev_live.py`, which belongs to 4.1 and is not touched here.

## Notes

- The exploration summary was cut off at the start of its VERIFICATION field, which shows the upstream stage over-ran its brief. The verification above comes from the card's deliverable 5 and its constraints, not from the missing text.
- The code differs from the findings in two places, and the docs must follow the code:
  - An explicit config with no key raises `ValueError` at construction.
  - Empty question names are not rejected by `classify()`.
