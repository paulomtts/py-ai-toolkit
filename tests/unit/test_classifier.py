import importlib.util

import pytest
from pydantic import TypeAdapter, ValidationError

from py_ai_toolkit.core.domain import classifier as classifier_module
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
from py_ai_toolkit.core.domain.errors import ClassifierAdapterError, LLMAdapterError

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


@pytest.mark.parametrize("question_type", [ChoiceQuestion, ScoreQuestion])
def test_choice_and_score_criteria_are_required(question_type):
    with pytest.raises(ValidationError):
        question_type()


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


# Config


def test_classifier_config_ignores_env_vars(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    monkeypatch.setenv("CLASSIFIER_MODEL", "env-model")
    monkeypatch.setenv("CLASSIFIER_BASE_URL", "https://env.example")

    config = ClassifierConfig()

    assert config.api_key is None
    assert config.model is None
    assert config.base_url is None


def test_classifier_config_has_no_env_defaults_at_import(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    monkeypatch.setenv("CLASSIFIER_MODEL", "env-model")
    monkeypatch.setenv("CLASSIFIER_BASE_URL", "https://env.example")
    # A class-body os.getenv default runs at import, so execute a fresh copy
    # of the module with the env already set.
    spec = importlib.util.spec_from_file_location(
        "_fresh_classifier", classifier_module.__file__
    )
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)

    config = fresh.ClassifierConfig()

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


# --- ClassifierAdapterError ---


def test_classifier_adapter_error_carries_message():
    err = ClassifierAdapterError("boom")

    assert err.message == "boom"
    assert str(err) == "boom"
    assert ClassifierAdapterError().message == ""
    assert isinstance(err, Exception)
    assert not isinstance(err, LLMAdapterError)
    with pytest.raises(Exception) as caught:
        raise ClassifierAdapterError("raised")
    assert caught.value.message == "raised"


def test_classifier_adapter_error_keeps_cause_and_escapes_llm_handler():
    cause = RuntimeError("sdk failure")

    with pytest.raises(ClassifierAdapterError) as caught:
        try:
            try:
                raise cause
            except RuntimeError as exc:
                raise ClassifierAdapterError("Jev request failed") from exc
        except LLMAdapterError:
            pytest.fail("ClassifierAdapterError must not be caught as LLMAdapterError")

    assert caught.value.__cause__ is cause
    assert caught.value.message == "Jev request failed"
