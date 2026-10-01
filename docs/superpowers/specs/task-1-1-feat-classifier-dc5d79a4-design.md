# Task 1.1 — feat: classifier domain types (card dc5d79a4)

Parent: Story 1 "classifier core types and port" (eaac0cc9), milestone e3bd09dc. Authority: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md`, sections "Types", "Config" and "Testing". Read it by absolute path because it is gitignored and absent from worktrees. This card narrows that design to the pure domain types. It adds nothing new.

## Scope

Create `py_ai_toolkit/core/domain/classifier.py`, a pydantic v2 module. It must have no SDK import (`typesafe_sdk` must never appear in `core/`), no network access and no `os.getenv`. Its contents follow the milestone spec's "Types" code exactly:

- `JSONContent = str | dict[str, Any] | list[Any]`
- `NoulCriteria(true: JSONContent | None = None, false: JSONContent | None = None)`
- `NoulQuestion` / `ChoiceQuestion` / `ScoreQuestion`. Each has `type: Literal["noul"|"choice"|"score"]` defaulting to its own tag, plus `instructions: JSONContent | None = None`. Criteria differ by type:
  - `NoulQuestion.criteria: NoulCriteria | None = None`
  - `ChoiceQuestion.criteria: dict[str, JSONContent | None]` (required)
  - `ScoreQuestion.criteria: list[JSONContent]` (required)
- `Question = Annotated[NoulQuestion | ChoiceQuestion | ScoreQuestion, Field(discriminator="type")]`
- `NoulAnswer(type="noul", noul: float)`. It has no confidence.
- `ChoiceAnswer(type="choice", choice: str, probabilities: dict[str, float], confidence: float)`
- `ScoreAnswer(type="score", score: float, probabilities: dict[int, float], confidence: float, legend: dict[int, JSONContent])`
- `Answer = Annotated[NoulAnswer | ChoiceAnswer | ScoreAnswer, Field(discriminator="type")]`
- `ClassifierUsage(input_tokens: int | None = None, output_tokens: int | None = None)`
- `ClassifierResponse(model: str, answers: dict[str, Answer], usage: ClassifierUsage)`. It has plain `@property` accessors `nouls -> dict[str, NoulAnswer]`, `choices -> dict[str, ChoiceAnswer]` and `scores -> dict[str, ScoreAnswer]`. Each one filters `answers` by `type` and keeps the original names as keys. Do not use `cached_property`.
- `ClassifierConfig(api_key, model, base_url)`. All three are `str | None = None`. There are NO env defaults on the class. Env resolution belongs to the later facade card. Do not copy `LLMConfig`'s class-body `os.getenv` from `core/domain/schemas.py:10-19`.

Keep the public term "Noul". Store raw values only: no normalization, no derived or default confidence, and no range checks on probabilities, scores or confidence.

## Validation (fail before any network call)

- `ChoiceQuestion.criteria` must have 1..255 entries.
- `ScoreQuestion.criteria` must have 2..10 entries.
- Any count outside these ranges raises pydantic `ValidationError` when the model is built or parsed.
- Question names must be non-empty strings. A question-name check lives in this module as a public helper, `validate_question_names(questions: Mapping[str, Question]) -> None`. It raises `ValueError` if any key is not a `str` or is `""`. Later cards call it before they reach the network.
- The same non-empty-name rule applies to `ClassifierResponse.answers` keys through a field validator. Breaking it raises `ValidationError`.
- Names are checked as given. Do not strip or normalize them.

## Out of scope

- Do not export anything from `py_ai_toolkit/__init__.py`.
- Do not touch `core/domain/errors.py` or `core/ports/*`. `ClassifierAdapterError` and `ClassifierPort` belong to card 1.2.
- Do not touch `core/hooks.py` or `tests/unit/test_hooks.py`. Those belong to card 1.3.
- Do not touch `schemas.py`, `toolkit.py`, `factories.py`, the adapters, packaging or docs.
- Milestone-wide exclusions also apply: no LLM or fallback adapter, no chat/stream/embed on the classifier, no streaming, no sync client, no retry logic and no ori integration.

## Tests

Every test goes in the flat unit tier, in the new file `tests/unit/test_classifier.py`. The milestone spec's Testing section is the only placement rule this repo has, and it puts pure-pydantic domain-type tests there. The tests use plain `test_*` functions and `pytest.raises`, in the style of `tests/unit/test_hooks.py`. They need no mocks, no network, no facade and no async.

1. **Question discriminator.** A `TypeAdapter(Question)` parses dicts tagged `"noul"`, `"choice"` and `"score"` into the matching class. An unknown `type` raises `ValidationError`. A bare `NoulQuestion()` builds with type `"noul"` and all fields set to None.
2. **Answer discriminator.** A `TypeAdapter(Answer)` parses all three answer shapes. `ScoreAnswer` accepts int keys for `probabilities` and `legend`. `NoulAnswer` has no `confidence` field.
3. **Response parsing and accessors.** `ClassifierResponse.model_validate` reads a dict whose `answers` mix all three types, then:
   - `.nouls`, `.choices` and `.scores` each return only their own type, keyed by the original names.
   - An empty `answers` dict gives three empty accessor results.
   - `usage` accepts None token counts.
4. **Choice bounds.** `criteria` with 0 entries is rejected, 1 is accepted, 255 is accepted and 256 is rejected.
5. **Score bounds.** `criteria` with 1 entry is rejected, 2 is accepted, 10 is accepted and 11 is rejected.
6. **JSON-form criteria.** Each of these is accepted and round-trips unchanged:
   - `NoulCriteria` true/false values given as str, dict, list and None.
   - `ChoiceQuestion` criteria values given as str, dict, list and None.
   - `ScoreQuestion` levels given as str, dict and list.
   - `instructions` given as str, dict, list and None.
7. **Question names.**
   - `validate_question_names` accepts `{"q": NoulQuestion()}`.
   - It raises `ValueError` for an `""` key.
   - `ClassifierResponse` with an `""` answers key raises `ValidationError`.
8. **Config.**
   - `ClassifierConfig()` sets all three fields to None, even when `CLASSIFIER_API_KEY`, `CLASSIFIER_MODEL` and `CLASSIFIER_BASE_URL` are set through `monkeypatch.setenv`. This proves there is no env read on the class.
   - Explicit values are stored as given.

## Verification

- Full suite: `pytest tests/ --ignore=tests/test_run_task.py`
- Lint: `ruff format .` then `ruff check .`
- There is no typecheck step.
