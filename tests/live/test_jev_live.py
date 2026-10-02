"""Live test against the real Jev service.

Skipped unless CLASSIFIER_API_KEY is set and the `jev` extra
(typesafe-sdk) is installed. Asserts shapes and ranges only.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("CLASSIFIER_API_KEY"),
    reason="CLASSIFIER_API_KEY not set; live Jev test skipped.",
)

pytest.importorskip("typesafe_sdk")

from py_ai_toolkit import (  # noqa: E402
    ChoiceQuestion,
    ClassifierResponse,
    NoulQuestion,
    PyAIToolkit,
    ScoreQuestion,
)
from py_ai_toolkit.core.domain.classifier import NoulCriteria  # noqa: E402

STATE = (
    "Hi, I was charged twice for my subscription this month. "
    "Please refund the duplicate charge as soon as possible."
)

NOUL_NAME = "billing"
CHOICE_NAME = "department"
SCORE_NAME = "urgency"

CHOICE_CRITERIA = {
    "billing": "Payments, charges, refunds or invoices.",
    "technical": "Bugs, errors or problems using the product.",
    "none": "None of the other departments apply.",
}

SCORE_LEVELS = [
    "Not urgent at all.",
    "Somewhat urgent.",
    "Urgent.",
    "Extremely urgent.",
]


def _questions():
    return {
        NOUL_NAME: NoulQuestion(
            instructions="Is this message about billing?",
            criteria=NoulCriteria(
                true="The message mentions a charge, payment or refund.",
                false="The message does not mention money at all.",
            ),
        ),
        CHOICE_NAME: ChoiceQuestion(
            instructions="Which department should handle this message?",
            criteria=CHOICE_CRITERIA,
        ),
        SCORE_NAME: ScoreQuestion(
            instructions="How urgent is this message?",
            criteria=SCORE_LEVELS,
        ),
    }


@pytest.mark.asyncio
async def test_classify_live_one_question_of_each_type():
    toolkit = PyAIToolkit()
    try:
        response = await toolkit.classify(STATE, _questions())
    finally:
        await toolkit.aclose()

    assert isinstance(response, ClassifierResponse)
    assert set(response.nouls) == {NOUL_NAME}
    assert set(response.choices) == {CHOICE_NAME}
    assert set(response.scores) == {SCORE_NAME}

    noul = response.nouls[NOUL_NAME]
    assert 0 <= noul.noul <= 1

    choice = response.choices[CHOICE_NAME]
    assert choice.choice in CHOICE_CRITERIA
    assert set(choice.probabilities) == set(CHOICE_CRITERIA)
    assert sum(choice.probabilities.values()) == pytest.approx(1)
    assert 0 <= choice.confidence <= 1

    score = response.scores[SCORE_NAME]
    n_levels = len(SCORE_LEVELS)
    assert sum(score.probabilities.values()) == pytest.approx(1)
    assert 0 <= score.confidence <= 1
    assert set(score.legend) == set(score.probabilities)
    assert len(score.legend) == n_levels
    assert all(isinstance(level, int) for level in score.legend)
    lowest = min(score.legend)
    assert sorted(score.legend) == list(range(lowest, lowest + n_levels))
    assert min(score.legend) <= score.score <= max(score.legend)
