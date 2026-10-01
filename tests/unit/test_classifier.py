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
