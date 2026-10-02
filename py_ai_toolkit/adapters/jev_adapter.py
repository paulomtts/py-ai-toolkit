"""Jev classifier adapter over the TypeSafe AI SDK.

This is the only module in py_ai_toolkit that imports typesafe_sdk. It is
deliberately not re-exported from py_ai_toolkit.adapters, so the SDK stays
an optional dependency (the `jev` extra).
"""

from collections.abc import Mapping
from typing import Any

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
)
from py_ai_toolkit.core.domain.errors import ClassifierAdapterError
from py_ai_toolkit.core.ports import ClassifierPort


def _noul_criteria(criteria: NoulCriteria | None) -> dict[str, Any] | None:
    if criteria is None:
        return None
    mapped: dict[str, Any] = {}
    if criteria.true is not None:
        mapped["true"] = criteria.true
    if criteria.false is not None:
        mapped["false"] = criteria.false
    return mapped


def _to_noul(question: NoulQuestion) -> Noul:
    return Noul(
        instructions=question.instructions,
        criteria=_noul_criteria(question.criteria),
    )


def _to_choice(question: ChoiceQuestion) -> Choice:
    return Choice(
        instructions=question.instructions,
        criteria=dict(question.criteria),
    )


def _to_score(question: ScoreQuestion) -> Score:
    return Score(
        instructions=question.instructions,
        criteria=list(question.criteria),
    )


def _to_sdk_question(question: Question) -> Noul | Choice | Score:
    if isinstance(question, NoulQuestion):
        return _to_noul(question)
    if isinstance(question, ChoiceQuestion):
        return _to_choice(question)
    if isinstance(question, ScoreQuestion):
        return _to_score(question)
    raise TypeError(
        f"Unsupported question type for JevAdapter: {type(question).__name__}"
    )


def _to_classifier_response(response: SystemOneResponse) -> ClassifierResponse:
    answers: dict[str, Answer] = {}
    for name, noul in response.nouls.items():
        answers[name] = NoulAnswer(noul=noul.noul)
    for name, choice in response.choices.items():
        answers[name] = ChoiceAnswer(
            choice=choice.choice,
            probabilities=dict(choice.probabilities),
            confidence=choice.confidence,
        )
    for name, score in response.scores.items():
        # Level keys may arrive as JSON strings; ScoreAnswer coerces them to int.
        answers[name] = ScoreAnswer(
            score=score.score,
            probabilities=dict(score.probabilities),
            confidence=score.confidence,
            legend=dict(score.legend),
        )
    return ClassifierResponse(
        model=response.model,
        answers=answers,
        usage=ClassifierUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        ),
    )


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


class JevAdapter(ClassifierPort):
    """
    TypeSafe AI (Jev) implementation of the classifier port.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "jev-latest",
        base_url: str | None = None,
    ):
        self._model = model
        self._client = AsyncTypeSafeClient(
            api_key=api_key,
            model=model,
            base_url=base_url,
        )

    async def classify(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: Mapping[str, Question],
    ) -> ClassifierResponse:
        sdk_questions = {
            name: _to_sdk_question(question) for name, question in questions.items()
        }
        try:
            response = await self._client.system_one(state, sdk_questions)
        except TypeSafeError as exc:
            raise _to_adapter_error(exc) from exc
        return _to_classifier_response(response)

    async def aclose(self) -> None:
        await self._client.aclose()
