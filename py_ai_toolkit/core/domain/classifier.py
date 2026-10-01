"""Classifier domain types: questions, answers, response and config.

Pure pydantic: no SDK import, no network access, no environment reads.
Values are stored raw; nothing is normalized or derived.
"""

from collections.abc import Iterable, Mapping
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator

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


class ClassifierConfig(BaseModel):
    """Classifier settings. Env vars are resolved by the facade, never here."""

    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
