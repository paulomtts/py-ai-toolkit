"""Jev classifier adapter over the TypeSafe AI SDK.

This is the only module in py_ai_toolkit that imports typesafe_sdk. It is
deliberately not re-exported from py_ai_toolkit.adapters, so the SDK stays
an optional dependency (the `jev` extra).
"""

from collections.abc import Mapping
from typing import Any

from typesafe_sdk import AsyncTypeSafeClient, SystemOneResponse

from py_ai_toolkit.core.domain.classifier import (
    Answer,
    ChoiceAnswer,
    ClassifierResponse,
    ClassifierUsage,
    NoulAnswer,
    Question,
    ScoreAnswer,
)
from py_ai_toolkit.core.ports import ClassifierPort


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
        answers[name] = ScoreAnswer(
            score=score.score,
            probabilities={int(k): v for k, v in score.probabilities.items()},
            confidence=score.confidence,
            legend={int(k): v for k, v in score.legend.items()},
        )
    return ClassifierResponse(
        model=response.model,
        answers=answers,
        usage=ClassifierUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        ),
    )


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
        response = await self._client.system_one(state, questions)
        return _to_classifier_response(response)
