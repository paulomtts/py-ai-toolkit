import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

typesafe_sdk = pytest.importorskip("typesafe_sdk")

from py_ai_toolkit.adapters.jev_adapter import JevAdapter  # noqa: E402
from py_ai_toolkit.core.domain.classifier import (  # noqa: E402
    ChoiceAnswer,
    ChoiceQuestion,
    ClassifierResponse,
    ClassifierUsage,
    NoulAnswer,
    NoulCriteria,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE = "I was charged twice. Please help."


def _questions():
    return {
        "billing": NoulQuestion(
            instructions="Is this about billing?",
            criteria=NoulCriteria(
                true="mentions a charge",
                false="no charge mentioned",
            ),
        ),
        "tone": ChoiceQuestion(
            instructions="What is the tone?",
            criteria={"calm": "measured wording", "angry": None},
        ),
        "urgency": ScoreQuestion(
            instructions="How urgent is it?",
            criteria=["low", "medium", "high"],
        ),
    }


def _sdk_response(input_tokens=12, output_tokens=3):
    return typesafe_sdk.SystemOneResponse(
        model="jev-2026-09",
        usage=typesafe_sdk.Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        answers={
            "billing": typesafe_sdk.NoulAnswer(noul=0.87),
            "tone": typesafe_sdk.ChoiceAnswer(
                choice="angry",
                probabilities={"calm": 0.2, "angry": 0.8},
                confidence=0.6,
            ),
            "urgency": typesafe_sdk.ScoreAnswer(
                score=1.4,
                probabilities={0: 0.1, 1: 0.4, 2: 0.5},
                confidence=0.7,
                legend={0: "low", 1: "medium", 2: "high"},
            ),
        },
    )


def _adapter_returning(response):
    adapter = JevAdapter(api_key="test-key")
    adapter._client = SimpleNamespace(system_one=AsyncMock(return_value=response))
    return adapter


def test_init_keeps_model():
    assert JevAdapter(api_key="test-key")._model == "jev-latest"

    adapter = JevAdapter(
        api_key="test-key",
        model="jev-2026-09",
        base_url="https://example.invalid",
    )
    assert adapter._model == "jev-2026-09"
    assert isinstance(adapter._client, typesafe_sdk.AsyncTypeSafeClient)


@pytest.mark.asyncio
async def test_answer_mapping():
    adapter = _adapter_returning(_sdk_response())

    result = await adapter.classify(STATE, _questions())

    assert isinstance(result, ClassifierResponse)
    assert result.model == "jev-2026-09"
    assert result.usage == ClassifierUsage(input_tokens=12, output_tokens=3)
    assert set(result.answers) == {"billing", "tone", "urgency"}
    assert result.nouls == {"billing": NoulAnswer(noul=0.87)}
    assert result.choices == {
        "tone": ChoiceAnswer(
            choice="angry",
            probabilities={"calm": 0.2, "angry": 0.8},
            confidence=0.6,
        )
    }
    assert result.scores == {
        "urgency": ScoreAnswer(
            score=1.4,
            probabilities={0: 0.1, 1: 0.4, 2: 0.5},
            confidence=0.7,
            legend={0: "low", 1: "medium", 2: "high"},
        )
    }


@pytest.mark.asyncio
async def test_score_keys_coerced_to_int():
    response = SimpleNamespace(
        model="jev-2026-09",
        usage=SimpleNamespace(input_tokens=1, output_tokens=2),
        nouls={},
        choices={},
        scores={
            "urgency": SimpleNamespace(
                score=1.75,
                probabilities={"1": 0.25, "2": 0.75},
                confidence=0.5,
                legend={"1": "medium", "2": "high"},
            )
        },
    )
    adapter = _adapter_returning(response)

    result = await adapter.classify(
        STATE, {"urgency": ScoreQuestion(criteria=["low", "medium", "high"])}
    )

    score = result.scores["urgency"]
    assert score.probabilities == {1: 0.25, 2: 0.75}
    assert score.legend == {1: "medium", 2: "high"}
    assert all(type(key) is int for key in [*score.probabilities, *score.legend])


@pytest.mark.asyncio
async def test_usage_none_passthrough():
    adapter = _adapter_returning(_sdk_response(input_tokens=None, output_tokens=None))

    result = await adapter.classify(STATE, _questions())

    assert result.usage.input_tokens is None
    assert result.usage.output_tokens is None


@pytest.mark.asyncio
async def test_empty_answers():
    response = typesafe_sdk.SystemOneResponse(
        model="jev-2026-09",
        usage=typesafe_sdk.Usage(input_tokens=5, output_tokens=0),
        answers={},
    )
    adapter = _adapter_returning(response)

    result = await adapter.classify(STATE, _questions())

    assert result.answers == {}
    assert result.model == "jev-2026-09"
    assert result.usage == ClassifierUsage(input_tokens=5, output_tokens=0)


def test_adapters_package_does_not_import_sdk():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, py_ai_toolkit.adapters; "
            "assert 'typesafe_sdk' not in sys.modules",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
async def test_question_mapping():
    adapter = _adapter_returning(_sdk_response())

    await adapter.classify(STATE, _questions())

    system_one = adapter._client.system_one
    system_one.assert_awaited_once()
    args, kwargs = system_one.await_args
    assert kwargs == {}
    state, sdk_questions = args
    assert state == STATE
    assert set(sdk_questions) == {"billing", "tone", "urgency"}

    billing = sdk_questions["billing"]
    assert isinstance(billing, typesafe_sdk.Noul)
    assert billing.instructions == "Is this about billing?"
    assert billing.criteria == {
        "true": "mentions a charge",
        "false": "no charge mentioned",
    }

    tone = sdk_questions["tone"]
    assert isinstance(tone, typesafe_sdk.Choice)
    assert tone.instructions == "What is the tone?"
    assert dict(tone.criteria) == {"calm": "measured wording", "angry": None}

    urgency = sdk_questions["urgency"]
    assert isinstance(urgency, typesafe_sdk.Score)
    assert urgency.instructions == "How urgent is it?"
    assert list(urgency.criteria) == ["low", "medium", "high"]


@pytest.mark.asyncio
async def test_noul_criteria_none():
    adapter = _adapter_returning(_sdk_response())

    await adapter.classify(
        STATE,
        {
            "no_criteria": NoulQuestion(instructions="Is this spam?"),
            "only_true": NoulQuestion(criteria=NoulCriteria(true="asks for a refund")),
            "only_false": NoulQuestion(criteria=NoulCriteria(false="no refund asked")),
            "empty": NoulQuestion(criteria=NoulCriteria()),
        },
    )

    _, sdk_questions = adapter._client.system_one.await_args.args
    assert all(isinstance(q, typesafe_sdk.Noul) for q in sdk_questions.values())
    assert sdk_questions["no_criteria"].criteria is None
    assert sdk_questions["only_true"].criteria == {"true": "asks for a refund"}
    assert sdk_questions["only_false"].criteria == {"false": "no refund asked"}
    assert sdk_questions["empty"].criteria == {}


@pytest.mark.asyncio
async def test_unknown_question_type_raises_before_call():
    adapter = _adapter_returning(_sdk_response())

    with pytest.raises(TypeError):
        await adapter.classify(STATE, {"raw": {"type": "noul"}})

    adapter._client.system_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_structured_state_and_instructions_pass_through():
    adapter = _adapter_returning(_sdk_response())
    state = {"message": "I was charged twice.", "attachments": ["receipt.pdf"]}
    instructions = {"question": "Is this about billing?", "scope": ["charges"]}

    await adapter.classify(
        state, {"billing": NoulQuestion(instructions=instructions)}
    )

    sent_state, sdk_questions = adapter._client.system_one.await_args.args
    assert sent_state == state
    assert isinstance(sdk_questions["billing"], typesafe_sdk.Noul)
    assert sdk_questions["billing"].instructions == instructions
