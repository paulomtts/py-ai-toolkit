<!-- task-pipeline: validated -->
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

---

# Classifier Domain Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `py_ai_toolkit/core/domain/classifier.py` with the pure pydantic v2 question, answer, response and config types for the Jev classifier, plus their unit tests in `tests/unit/test_classifier.py`.

**Architecture:** One new domain module under `py_ai_toolkit/core/domain/`, alongside `errors.py`, `models.py` and `schemas.py`. It imports only `collections.abc`, `typing` and `pydantic`. Count bounds use `Field(min_length=..., max_length=...)`, which pydantic v2 enforces on both dicts and lists. A private `_check_names` helper is shared by the public `validate_question_names` (raises `ValueError`) and a `field_validator` on `ClassifierResponse.answers`; pydantic turns that `ValueError` into a `ValidationError`. Nothing is exported from the package root.

**Tech Stack:** Python >=3.11, pydantic >=2.12.4, pytest, ruff.

**Spec:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-1-1-feat-classifier-dc5d79a4/docs/superpowers/specs/task-1-1-feat-classifier-dc5d79a4-design.md` (reproduced above). Milestone authority: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md`, sections "Types", "Config" and "Testing".

All commands run from the worktree root: `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-1-1-feat-classifier-dc5d79a4`. The branch is `m-classifier/task-1-1-feat-classifier-dc5d79a4`, cut fresh from `origin/main`. No code from cards 1.2 or 1.3 exists on it.

## Global Constraints

- `py_ai_toolkit/core/domain/classifier.py` has no `typesafe_sdk` import, no network access and no `os.getenv` (no `import os` at all).
- `ClassifierConfig` fields `api_key`, `model`, `base_url` are all `str | None = None`. No env defaults on the class.
- Raw values only: no normalization, no derived or default confidence, no range checks on probabilities, scores or confidence.
- Keep the public term "Noul" (`NoulCriteria`, `NoulQuestion`, `NoulAnswer`, `.nouls`).
- `ChoiceQuestion.criteria` has 1..255 entries; `ScoreQuestion.criteria` has 2..10 entries; violations raise `ValidationError`.
- Question names are non-empty `str`, checked as given (no strip, no normalize).
- Accessors are plain `@property`, never `cached_property`.
- Do not edit `py_ai_toolkit/__init__.py`, `core/domain/errors.py`, `core/domain/schemas.py`, `core/ports/*`, `core/hooks.py`, `tests/unit/test_hooks.py`, `toolkit.py`, `factories.py`, adapters, `pyproject.toml` or docs.
- All tests live in `tests/unit/test_classifier.py` (flat unit tier, plain `test_*` functions, `pytest.raises`, no mocks, no async).
- Verification: `pytest tests/ --ignore=tests/test_run_task.py`, `ruff format .`, `ruff check .`. No typecheck.

## Review Focus

- A question or answer dict without a `type` key, parsed through the `Question`/`Answer` union, must raise `ValidationError` rather than guess a type (the class default only applies to direct construction). Pinned in Task 1 (`test_question_without_type_tag_is_rejected`) and Task 2 (`test_answer_without_type_tag_is_rejected`).
- A `ScoreQuestion` level given as `None` must be rejected, because `criteria: list[JSONContent]` excludes None, unlike choice options. Pinned in Task 1 (`test_score_level_none_is_rejected`).
- Question names are checked as given: a whitespace-only name `" "` is accepted, a non-`str` key (e.g. `1`) is rejected, and an empty mapping passes the helper (the empty-questions check belongs to the later facade). Pinned in Task 1 (`test_validate_question_names_accepts_whitespace_name_as_given`, `test_validate_question_names_rejects_non_str_key`, `test_validate_question_names_accepts_empty_mapping`).
- `ScoreAnswer` parsed from JSON-shaped data arrives with string level keys (`"1"`); they must coerce to `int` so `probabilities[1]` works. Pinned in Task 2 (`test_score_answer_coerces_string_level_keys_to_int`).
- Raw values are stored unchanged even when outside 0..1 (no clamping, no derived confidence). Pinned in Task 2 (`test_answers_store_raw_values_without_range_checks`).

---

### Task 1: Questions, criteria, bounds and the question-name helper

**Files:**
- Create: `py_ai_toolkit/core/domain/classifier.py`
- Test: `tests/unit/test_classifier.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces (in `py_ai_toolkit.core.domain.classifier`):
  - `JSONContent = str | dict[str, Any] | list[Any]`
  - `class NoulCriteria(BaseModel)`: `true: JSONContent | None = None`, `false: JSONContent | None = None`
  - `class NoulQuestion(BaseModel)`: `type: Literal["noul"] = "noul"`, `instructions: JSONContent | None = None`, `criteria: NoulCriteria | None = None`
  - `class ChoiceQuestion(BaseModel)`: `type: Literal["choice"] = "choice"`, `instructions: JSONContent | None = None`, `criteria: dict[str, JSONContent | None]` (1..255)
  - `class ScoreQuestion(BaseModel)`: `type: Literal["score"] = "score"`, `instructions: JSONContent | None = None`, `criteria: list[JSONContent]` (2..10)
  - `Question = Annotated[NoulQuestion | ChoiceQuestion | ScoreQuestion, Field(discriminator="type")]`
  - `def _check_names(names: Iterable[object]) -> None` (private, raises `ValueError`; Task 2 reuses it)
  - `def validate_question_names(questions: Mapping[str, Question]) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_classifier.py` with exactly this content:

```python
import pytest
from pydantic import TypeAdapter, ValidationError

from py_ai_toolkit.core.domain.classifier import (
    ChoiceQuestion,
    NoulCriteria,
    NoulQuestion,
    Question,
    ScoreQuestion,
    validate_question_names,
)

JSON_FORMS = ["plain text", {"rule": "is spam", "examples": [1, 2]}, ["a", "b"], None]


# Question discriminator


def test_question_adapter_parses_each_type_tag():
    adapter = TypeAdapter(Question)

    noul = adapter.validate_python({"type": "noul"})
    choice = adapter.validate_python({"type": "choice", "criteria": {"yes": None}})
    score = adapter.validate_python({"type": "score", "criteria": ["low", "high"]})

    assert isinstance(noul, NoulQuestion)
    assert isinstance(choice, ChoiceQuestion)
    assert isinstance(score, ScoreQuestion)


def test_question_adapter_rejects_unknown_type():
    with pytest.raises(ValidationError):
        TypeAdapter(Question).validate_python({"type": "rank", "criteria": ["a"]})


def test_question_without_type_tag_is_rejected():
    with pytest.raises(ValidationError):
        TypeAdapter(Question).validate_python({"criteria": {"yes": None}})


def test_bare_noul_question_defaults():
    question = NoulQuestion()

    assert question.type == "noul"
    assert question.instructions is None
    assert question.criteria is None


# Choice bounds


@pytest.mark.parametrize("count", [1, 255])
def test_choice_criteria_within_bounds_is_accepted(count):
    criteria = {f"option{i}": None for i in range(count)}

    question = ChoiceQuestion(criteria=criteria)

    assert len(question.criteria) == count


@pytest.mark.parametrize("count", [0, 256])
def test_choice_criteria_outside_bounds_is_rejected(count):
    criteria = {f"option{i}": None for i in range(count)}

    with pytest.raises(ValidationError):
        ChoiceQuestion(criteria=criteria)


# Score bounds


@pytest.mark.parametrize("count", [2, 10])
def test_score_criteria_within_bounds_is_accepted(count):
    criteria = [f"level {i}" for i in range(count)]

    question = ScoreQuestion(criteria=criteria)

    assert len(question.criteria) == count


@pytest.mark.parametrize("count", [1, 11])
def test_score_criteria_outside_bounds_is_rejected(count):
    criteria = [f"level {i}" for i in range(count)]

    with pytest.raises(ValidationError):
        ScoreQuestion(criteria=criteria)


def test_score_level_none_is_rejected():
    with pytest.raises(ValidationError):
        ScoreQuestion(criteria=["low", None])


# JSON-form criteria and instructions


@pytest.mark.parametrize("value", JSON_FORMS)
def test_noul_criteria_accepts_json_forms(value):
    payload = {
        "type": "noul",
        "instructions": None,
        "criteria": {"true": value, "false": value},
    }

    question = NoulQuestion.model_validate(payload)

    assert isinstance(question.criteria, NoulCriteria)
    assert question.model_dump() == payload


@pytest.mark.parametrize("value", JSON_FORMS)
def test_choice_criteria_values_accept_json_forms(value):
    payload = {"type": "choice", "instructions": None, "criteria": {"opt": value}}

    question = ChoiceQuestion.model_validate(payload)

    assert question.model_dump() == payload


@pytest.mark.parametrize("value", JSON_FORMS[:3])
def test_score_levels_accept_json_forms(value):
    payload = {"type": "score", "instructions": None, "criteria": [value, value]}

    question = ScoreQuestion.model_validate(payload)

    assert question.model_dump() == payload


@pytest.mark.parametrize("value", JSON_FORMS)
def test_instructions_accept_json_forms(value):
    payload = {"type": "noul", "instructions": value, "criteria": None}

    question = NoulQuestion.model_validate(payload)

    assert question.model_dump() == payload


# Question names


def test_validate_question_names_accepts_non_empty_names():
    validate_question_names({"q": NoulQuestion()})


def test_validate_question_names_rejects_empty_name():
    with pytest.raises(ValueError):
        validate_question_names({"": NoulQuestion()})


def test_validate_question_names_rejects_non_str_key():
    with pytest.raises(ValueError):
        validate_question_names({1: NoulQuestion()})


def test_validate_question_names_accepts_whitespace_name_as_given():
    validate_question_names({" ": NoulQuestion()})


def test_validate_question_names_accepts_empty_mapping():
    validate_question_names({})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/test_classifier.py -v`
Expected: collection ERROR with `ModuleNotFoundError: No module named 'py_ai_toolkit.core.domain.classifier'`.

- [ ] **Step 3: Write the minimal implementation**

Create `py_ai_toolkit/core/domain/classifier.py` with exactly this content:

```python
"""Classifier domain types: questions, answers, response and config.

Pure pydantic: no SDK import, no network access, no environment reads.
Values are stored raw; nothing is normalized or derived.
"""

from collections.abc import Iterable, Mapping
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

JSONContent = str | dict[str, Any] | list[Any]


class NoulCriteria(BaseModel):
    true: JSONContent | None = None
    false: JSONContent | None = None


class NoulQuestion(BaseModel):
    type: Literal["noul"] = "noul"
    instructions: JSONContent | None = None
    criteria: NoulCriteria | None = None


class ChoiceQuestion(BaseModel):
    type: Literal["choice"] = "choice"
    instructions: JSONContent | None = None
    criteria: dict[str, JSONContent | None] = Field(min_length=1, max_length=255)


class ScoreQuestion(BaseModel):
    type: Literal["score"] = "score"
    instructions: JSONContent | None = None
    criteria: list[JSONContent] = Field(min_length=2, max_length=10)


Question = Annotated[
    NoulQuestion | ChoiceQuestion | ScoreQuestion, Field(discriminator="type")
]


def _check_names(names: Iterable[object]) -> None:
    for name in names:
        if not isinstance(name, str) or name == "":
            raise ValueError(
                f"Question names must be non-empty strings; got {name!r}."
            )


def validate_question_names(questions: Mapping[str, Question]) -> None:
    """Raise ValueError unless every question name is a non-empty str."""
    _check_names(questions)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_classifier.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add py_ai_toolkit/core/domain/classifier.py tests/unit/test_classifier.py
git commit -m "feat: add classifier question types with criteria bounds"
```

---

### Task 2: Answers, usage, response, accessors and answer-name validation

**Files:**
- Modify: `py_ai_toolkit/core/domain/classifier.py` (pydantic import line; append after `validate_question_names`)
- Test: `tests/unit/test_classifier.py` (replace import block; append tests)

**Interfaces:**
- Consumes: `JSONContent`, `_check_names(names: Iterable[object]) -> None` from Task 1.
- Produces (in `py_ai_toolkit.core.domain.classifier`):
  - `class NoulAnswer(BaseModel)`: `type: Literal["noul"] = "noul"`, `noul: float`
  - `class ChoiceAnswer(BaseModel)`: `type: Literal["choice"] = "choice"`, `choice: str`, `probabilities: dict[str, float]`, `confidence: float`
  - `class ScoreAnswer(BaseModel)`: `type: Literal["score"] = "score"`, `score: float`, `probabilities: dict[int, float]`, `confidence: float`, `legend: dict[int, JSONContent]`
  - `Answer = Annotated[NoulAnswer | ChoiceAnswer | ScoreAnswer, Field(discriminator="type")]`
  - `class ClassifierUsage(BaseModel)`: `input_tokens: int | None = None`, `output_tokens: int | None = None`
  - `class ClassifierResponse(BaseModel)`: `model: str`, `answers: dict[str, Answer]`, `usage: ClassifierUsage`; properties `nouls -> dict[str, NoulAnswer]`, `choices -> dict[str, ChoiceAnswer]`, `scores -> dict[str, ScoreAnswer]`

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_classifier.py`, replace the import block at the top of the file (everything from `import pytest` through the closing `)` of the `py_ai_toolkit.core.domain.classifier` import) with:

```python
import pytest
from pydantic import TypeAdapter, ValidationError

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
    validate_question_names,
)
```

Then append to the end of the file:

```python
# Answer discriminator

NOUL_ANSWER = {"type": "noul", "noul": 0.82}
CHOICE_ANSWER = {
    "type": "choice",
    "choice": "billing",
    "probabilities": {"billing": 0.7, "support": 0.3},
    "confidence": 0.64,
}
SCORE_ANSWER = {
    "type": "score",
    "score": 2.4,
    "probabilities": {1: 0.1, 2: 0.4, 3: 0.5},
    "confidence": 0.5,
    "legend": {1: "low", 2: {"label": "mid"}, 3: ["high"]},
}


def test_answer_adapter_parses_each_type_tag():
    adapter = TypeAdapter(Answer)

    noul = adapter.validate_python(NOUL_ANSWER)
    choice = adapter.validate_python(CHOICE_ANSWER)
    score = adapter.validate_python(SCORE_ANSWER)

    assert isinstance(noul, NoulAnswer)
    assert noul.noul == 0.82
    assert isinstance(choice, ChoiceAnswer)
    assert choice.choice == "billing"
    assert choice.probabilities == {"billing": 0.7, "support": 0.3}
    assert choice.confidence == 0.64
    assert isinstance(score, ScoreAnswer)
    assert score.score == 2.4
    assert score.probabilities == {1: 0.1, 2: 0.4, 3: 0.5}
    assert score.legend == {1: "low", 2: {"label": "mid"}, 3: ["high"]}


def test_answer_without_type_tag_is_rejected():
    with pytest.raises(ValidationError):
        TypeAdapter(Answer).validate_python({"noul": 0.5})


def test_noul_answer_has_no_confidence():
    answer = NoulAnswer.model_validate({"noul": 0.4, "confidence": 0.9})

    assert "confidence" not in NoulAnswer.model_fields
    assert not hasattr(answer, "confidence")


def test_score_answer_coerces_string_level_keys_to_int():
    answer = ScoreAnswer.model_validate(
        {
            "score": 1.5,
            "probabilities": {"1": 0.5, "2": 0.5},
            "confidence": 0.5,
            "legend": {"1": "low", "2": "high"},
        }
    )

    assert answer.probabilities == {1: 0.5, 2: 0.5}
    assert answer.legend == {1: "low", 2: "high"}


def test_answers_store_raw_values_without_range_checks():
    noul = NoulAnswer(noul=1.7)
    choice = ChoiceAnswer(
        choice="a", probabilities={"a": 0.9, "b": 0.9}, confidence=-0.2
    )

    assert noul.noul == 1.7
    assert choice.probabilities == {"a": 0.9, "b": 0.9}
    assert choice.confidence == -0.2


# Response parsing and accessors


def test_response_accessors_filter_answers_by_type():
    response = ClassifierResponse.model_validate(
        {
            "model": "jev-latest",
            "answers": {
                "is_spam": NOUL_ANSWER,
                "topic": CHOICE_ANSWER,
                "urgency": SCORE_ANSWER,
                "is_question": {"type": "noul", "noul": 0.1},
            },
            "usage": {"input_tokens": 120, "output_tokens": 4},
        }
    )

    assert response.model == "jev-latest"
    assert set(response.nouls) == {"is_spam", "is_question"}
    assert all(isinstance(a, NoulAnswer) for a in response.nouls.values())
    assert response.nouls["is_spam"].noul == 0.82
    assert set(response.choices) == {"topic"}
    assert isinstance(response.choices["topic"], ChoiceAnswer)
    assert set(response.scores) == {"urgency"}
    assert isinstance(response.scores["urgency"], ScoreAnswer)
    assert response.usage == ClassifierUsage(input_tokens=120, output_tokens=4)


def test_response_with_no_answers_has_empty_accessors():
    response = ClassifierResponse(model="jev-latest", answers={}, usage={})

    assert response.nouls == {}
    assert response.choices == {}
    assert response.scores == {}


def test_usage_accepts_none_token_counts():
    usage = ClassifierUsage(input_tokens=None, output_tokens=None)

    assert usage.input_tokens is None
    assert usage.output_tokens is None
    assert ClassifierUsage() == usage


def test_response_rejects_empty_answer_name():
    with pytest.raises(ValidationError):
        ClassifierResponse(
            model="jev-latest", answers={"": NOUL_ANSWER}, usage=ClassifierUsage()
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/test_classifier.py -v`
Expected: collection ERROR with `ImportError: cannot import name 'Answer' from 'py_ai_toolkit.core.domain.classifier'`.

- [ ] **Step 3: Write the minimal implementation**

In `py_ai_toolkit/core/domain/classifier.py`, replace the line:

```python
from pydantic import BaseModel, Field
```

with:

```python
from pydantic import BaseModel, Field, field_validator
```

Then append to the end of the file:

```python


class NoulAnswer(BaseModel):
    type: Literal["noul"] = "noul"
    noul: float


class ChoiceAnswer(BaseModel):
    type: Literal["choice"] = "choice"
    choice: str
    probabilities: dict[str, float]
    confidence: float


class ScoreAnswer(BaseModel):
    type: Literal["score"] = "score"
    score: float
    probabilities: dict[int, float]
    confidence: float
    legend: dict[int, JSONContent]


Answer = Annotated[NoulAnswer | ChoiceAnswer | ScoreAnswer, Field(discriminator="type")]


class ClassifierUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None


class ClassifierResponse(BaseModel):
    model: str
    answers: dict[str, Answer]
    usage: ClassifierUsage

    @field_validator("answers")
    @classmethod
    def check_answer_names(cls, answers: dict[str, Answer]) -> dict[str, Answer]:
        _check_names(answers)
        return answers

    @property
    def nouls(self) -> dict[str, NoulAnswer]:
        return {
            name: answer
            for name, answer in self.answers.items()
            if isinstance(answer, NoulAnswer)
        }

    @property
    def choices(self) -> dict[str, ChoiceAnswer]:
        return {
            name: answer
            for name, answer in self.answers.items()
            if isinstance(answer, ChoiceAnswer)
        }

    @property
    def scores(self) -> dict[str, ScoreAnswer]:
        return {
            name: answer
            for name, answer in self.answers.items()
            if isinstance(answer, ScoreAnswer)
        }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_classifier.py -v`
Expected: all tests PASS (Task 1 tests included).

- [ ] **Step 5: Commit**

```bash
git add py_ai_toolkit/core/domain/classifier.py tests/unit/test_classifier.py
git commit -m "feat: add classifier answer and response types with accessors"
```

---

### Task 3: ClassifierConfig with no env reads

**Files:**
- Modify: `py_ai_toolkit/core/domain/classifier.py` (append at end)
- Test: `tests/unit/test_classifier.py` (replace import block; append tests)

**Interfaces:**
- Consumes: nothing from earlier tasks beyond the module itself.
- Produces: `class ClassifierConfig(BaseModel)`: `api_key: str | None = None`, `model: str | None = None`, `base_url: str | None = None`. The later facade card resolves env vars (`CLASSIFIER_API_KEY`, `CLASSIFIER_MODEL`, `CLASSIFIER_BASE_URL`) at init; this class never reads them.

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_classifier.py`, replace the import block at the top of the file (everything from `import pytest` through the closing `)` of the `py_ai_toolkit.core.domain.classifier` import) with:

```python
import pytest
from pydantic import TypeAdapter, ValidationError

from py_ai_toolkit.core.domain.classifier import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    ClassifierConfig,
    ClassifierResponse,
    ClassifierUsage,
    NoulAnswer,
    NoulCriteria,
    NoulQuestion,
    Question,
    ScoreAnswer,
    ScoreQuestion,
    validate_question_names,
)
```

Then append to the end of the file:

```python
# Config


def test_classifier_config_ignores_env_vars(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    monkeypatch.setenv("CLASSIFIER_MODEL", "env-model")
    monkeypatch.setenv("CLASSIFIER_BASE_URL", "https://env.example")

    config = ClassifierConfig()

    assert config.api_key is None
    assert config.model is None
    assert config.base_url is None


def test_classifier_config_stores_explicit_values():
    config = ClassifierConfig(
        api_key="key", model="jev-2026-09", base_url="https://jev.example"
    )

    assert config.api_key == "key"
    assert config.model == "jev-2026-09"
    assert config.base_url == "https://jev.example"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/test_classifier.py -v`
Expected: collection ERROR with `ImportError: cannot import name 'ClassifierConfig' from 'py_ai_toolkit.core.domain.classifier'`.

- [ ] **Step 3: Write the minimal implementation**

Append to the end of `py_ai_toolkit/core/domain/classifier.py`:

```python


class ClassifierConfig(BaseModel):
    """Classifier settings. Env vars are resolved by the facade, never here."""

    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_classifier.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add py_ai_toolkit/core/domain/classifier.py tests/unit/test_classifier.py
git commit -m "feat: add ClassifierConfig without env defaults"
```

---

### Task 4: Full verification and scope check

**Files:**
- No new edits expected. Only `ruff format .` output may touch the two files from Tasks 1-3.

**Interfaces:**
- Consumes: everything from Tasks 1-3.
- Produces: a verified branch.

- [ ] **Step 1: Run the full suite**

Run: `pytest tests/ --ignore=tests/test_run_task.py`
Expected: all tests PASS, including `tests/unit/test_hooks.py` and `tests/unit/test_tools.py` unchanged.

- [ ] **Step 2: Format**

Run: `ruff format .`
Expected: no changes, or changes only to `py_ai_toolkit/core/domain/classifier.py` and `tests/unit/test_classifier.py`. If it reformats any other file, restore that file with `git checkout -- <path>` because it is out of scope for this card, and mention it in the hand-off.

- [ ] **Step 3: Lint**

Run: `ruff check .`
Expected: `All checks passed!`. Fix any finding in the two card files only.

- [ ] **Step 4: Confirm the domain module stays pure and scope held**

Run: `grep -nE "typesafe_sdk|getenv|import os|cached_property" py_ai_toolkit/core/domain/classifier.py`
Expected: no output.

Run: `git diff --stat origin/main -- py_ai_toolkit tests`
Expected: only `py_ai_toolkit/core/domain/classifier.py` and `tests/unit/test_classifier.py` listed. `py_ai_toolkit/__init__.py`, `core/domain/errors.py`, `core/ports/*` and `core/hooks.py` do not appear.

- [ ] **Step 5: Re-run the suite if format changed anything, then commit**

If Step 2 changed either card file, run `pytest tests/ --ignore=tests/test_run_task.py` again (expected: PASS), then:

```bash
git add py_ai_toolkit/core/domain/classifier.py tests/unit/test_classifier.py
git commit -m "style: ruff format classifier domain types"
```

If nothing changed, skip the commit.
