import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

typesafe_sdk = pytest.importorskip("typesafe_sdk")

import httpx2

from py_ai_toolkit.adapters.jev_adapter import JevAdapter
from py_ai_toolkit.core.domain.classifier import (
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
from py_ai_toolkit.core.domain.errors import ClassifierAdapterError

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


def _adapter_raising(exc):
    adapter = JevAdapter(api_key="test-key")
    adapter._client = SimpleNamespace(system_one=AsyncMock(side_effect=exc))
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


def test_init_builds_client_with_only_key_model_and_base_url(monkeypatch):
    calls = []

    def fake_client(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(
        "py_ai_toolkit.adapters.jev_adapter.AsyncTypeSafeClient", fake_client
    )

    JevAdapter(
        api_key="test-key",
        model="jev-2026-09",
        base_url="https://example.invalid",
    )
    JevAdapter(api_key="other-key")

    assert calls == [
        {
            "api_key": "test-key",
            "model": "jev-2026-09",
            "base_url": "https://example.invalid",
        },
        {"api_key": "other-key", "model": "jev-latest", "base_url": None},
    ]


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
            ("import sys, py_ai_toolkit.adapters; "
            "assert 'typesafe_sdk' not in sys.modules"),
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

    await adapter.classify(state, {"billing": NoulQuestion(instructions=instructions)})

    sent_state, sdk_questions = adapter._client.system_one.await_args.args
    assert sent_state == state
    assert isinstance(sdk_questions["billing"], typesafe_sdk.Noul)
    assert sdk_questions["billing"].instructions == instructions


def _headers(**values):
    return httpx2.Headers(values)


ERROR_CASES = [
    pytest.param(
        typesafe_sdk.TypeSafeAuthenticationError(
            401, {"detail": "bad key"}, _headers()
        ),
        lambda exc: ["invalid or missing jev api key"],
        id="auth-401",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeUnprocessableEntityError(
            422, {"detail": "criteria must not be empty"}, _headers()
        ),
        lambda exc: ["rejected the request as invalid", str(exc.body)],
        id="unprocessable-422",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeUnprocessableEntityError(422, None, _headers()),
        lambda exc: ["rejected the request as invalid", "None"],
        id="unprocessable-422-no-body",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeRateLimitError(
            429, {"detail": "slow down"}, _headers(**{"retry-after": "2"})
        ),
        lambda exc: ["rate limited", "retry_after_ms=2000.0"],
        id="rate-limit-429",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeRateLimitError(429, {"detail": "slow down"}, _headers()),
        lambda exc: ["rate limited", "retry_after_ms=None"],
        id="rate-limit-no-retry-after",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeInternalServerError(
            503, {"detail": "overloaded"}, _headers()
        ),
        lambda exc: ["unavailable or overloaded"],
        id="internal-server-5xx",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeAPITimeoutError(5.0),
        lambda exc: ["network failure or timeout", str(exc)],
        id="timeout",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeAPIConnectionError("connection refused"),
        lambda exc: ["network failure or timeout", "connection refused"],
        id="connection",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeAPIResponseValidationError(
            200, {"answers": {}}, _headers(), "answers.tone.confidence"
        ),
        lambda exc: ["malformed response from jev", "answers.tone.confidence"],
        id="response-validation",
    ),
    pytest.param(
        typesafe_sdk.TypeSafePermissionDeniedError(
            403, {"detail": "model not enabled"}, _headers()
        ),
        lambda exc: ["jev request failed", str(exc)],
        id="permission-403-generic",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeBadRequestError(
            400, {"detail": "state too long"}, _headers()
        ),
        lambda exc: ["jev request failed", str(exc)],
        id="bad-request-400-generic",
    ),
    pytest.param(
        typesafe_sdk.TypeSafeError("client misconfigured"),
        lambda exc: ["jev request failed", "client misconfigured"],
        id="base-typesafe-error-generic",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("original", "expected_fragments"), ERROR_CASES)
async def test_sdk_error_mapped_to_classifier_adapter_error(
    original, expected_fragments
):
    adapter = _adapter_raising(original)

    with pytest.raises(ClassifierAdapterError) as excinfo:
        await adapter.classify(STATE, _questions())

    raised = excinfo.value
    assert raised.__cause__ is original
    assert raised.message == str(raised)
    for fragment in expected_fragments(original):
        assert fragment.lower() in raised.message.lower()


def test_timeout_case_is_both_timeout_and_connection_error():
    exc = typesafe_sdk.TypeSafeAPITimeoutError(5.0)
    assert isinstance(exc, typesafe_sdk.TypeSafeAPIConnectionError)
    assert isinstance(exc, TimeoutError)


@pytest.mark.asyncio
async def test_non_sdk_error_propagates_unchanged():
    original = RuntimeError("stub client exploded")
    adapter = _adapter_raising(original)

    with pytest.raises(RuntimeError) as excinfo:
        await adapter.classify(STATE, _questions())

    assert excinfo.value is original
    assert not isinstance(excinfo.value, ClassifierAdapterError)


@pytest.mark.asyncio
async def test_response_mapping_error_propagates_unchanged():
    adapter = _adapter_returning(SimpleNamespace(model="jev-2026-09"))

    with pytest.raises(AttributeError) as excinfo:
        await adapter.classify(STATE, _questions())

    assert not isinstance(excinfo.value, ClassifierAdapterError)
    assert excinfo.value.__cause__ is None


@pytest.mark.asyncio
async def test_aclose_closes_sdk_client():
    adapter = JevAdapter(api_key="test-key")
    client_aclose = AsyncMock()
    adapter._client = SimpleNamespace(aclose=client_aclose)

    await adapter.aclose()

    client_aclose.assert_awaited_once()
