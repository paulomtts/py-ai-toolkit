import asyncio
import importlib.util
import inspect
import subprocess
import sys
import typing
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from py_ai_toolkit import factories
from py_ai_toolkit.core import ports as ports_package
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
from py_ai_toolkit.core.domain.schemas import LLMConfig
from py_ai_toolkit.core.hooks import AfterClassifyContext, BeforeClassifyContext, Hooks
from py_ai_toolkit.core.ports.classifier_port import ClassifierPort
from py_ai_toolkit.core.ports.llm_port import LLMPort
from py_ai_toolkit.core.toolkit import PyAIToolkit

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


# --- ClassifierPort ---


def run(coro):
    # asyncio.run() unsets the thread's current event loop on exit, which breaks
    # test_hooks.py's get_event_loop() calls; use a private loop instead.
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


FIXED_RESPONSE = ClassifierResponse(
    model="fake-classifier",
    answers={"q": NoulAnswer(noul=0.5)},
    usage=ClassifierUsage(input_tokens=3, output_tokens=1),
)


class MinimalClassifier(ClassifierPort):
    async def classify(self, state, questions):
        return FIXED_RESPONSE


def test_classifier_port_cannot_be_instantiated_without_classify():
    class EmptyClassifier(ClassifierPort):
        pass

    with pytest.raises(TypeError):
        ClassifierPort()
    with pytest.raises(TypeError):
        EmptyClassifier()


def test_classifier_port_minimal_subclass_classifies():
    classifier = MinimalClassifier()

    result = run(classifier.classify("state", {"q": NoulQuestion()}))

    assert result is FIXED_RESPONSE


def test_classifier_port_classify_signature_is_pinned():
    hints = typing.get_type_hints(ClassifierPort.classify, include_extras=True)
    params = list(inspect.signature(ClassifierPort.classify).parameters)

    assert params == ["self", "state", "questions"]
    assert hints["state"] == str | dict[str, Any] | list[Any]
    assert hints["questions"] == Mapping[str, Question]
    assert hints["return"] is ClassifierResponse
    assert inspect.iscoroutinefunction(ClassifierPort.classify)
    assert inspect.iscoroutinefunction(ClassifierPort.aclose)


def test_classifier_port_aclose_default_is_noop():
    classifier = MinimalClassifier()

    assert run(classifier.aclose()) is None


def test_classifier_port_is_separate_from_llm_port():
    assert ClassifierPort.__abstractmethods__ == frozenset({"classify"})
    assert not issubclass(ClassifierPort, LLMPort)
    for name in ("chat", "stream", "embed", "embed_batch", "asend"):
        assert not hasattr(ClassifierPort, name)


def test_classifier_port_exported_from_ports_package():
    assert ports_package.ClassifierPort is ClassifierPort
    assert "ClassifierPort" in ports_package.__all__


# create_classifier factory

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_HINT = (
    "The Jev classifier requires the 'jev' extra: pip install 'py-ai-toolkit[jev]'."
)


def _capture_sdk_client(monkeypatch):
    import py_ai_toolkit.adapters.jev_adapter as jev_adapter_module

    calls = []

    def fake_client(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(jev_adapter_module, "AsyncTypeSafeClient", fake_client)
    return jev_adapter_module, calls


def test_create_classifier_returns_classifier_port_with_defaults(monkeypatch):
    pytest.importorskip("typesafe_sdk")
    jev_adapter_module, calls = _capture_sdk_client(monkeypatch)

    classifier = factories.create_classifier("test-key")

    assert isinstance(classifier, ClassifierPort)
    assert isinstance(classifier, jev_adapter_module.JevAdapter)
    assert classifier._model == "jev-latest"
    assert calls == [
        {"api_key": "test-key", "model": "jev-latest", "base_url": None},
    ]


def test_create_classifier_passes_model_and_base_url_through(monkeypatch):
    pytest.importorskip("typesafe_sdk")
    _, calls = _capture_sdk_client(monkeypatch)

    classifier = factories.create_classifier(
        "other-key",
        model="jev-2026-09",
        base_url="https://example.invalid",
    )

    assert isinstance(classifier, ClassifierPort)
    assert classifier._model == "jev-2026-09"
    assert calls == [
        {
            "api_key": "other-key",
            "model": "jev-2026-09",
            "base_url": "https://example.invalid",
        },
    ]


def test_create_classifier_does_not_relabel_construction_errors(monkeypatch):
    pytest.importorskip("typesafe_sdk")
    import py_ai_toolkit.adapters.jev_adapter as jev_adapter_module

    inner = ImportError("raised while building the SDK client")

    def failing_client(**kwargs):
        raise inner

    monkeypatch.setattr(jev_adapter_module, "AsyncTypeSafeClient", failing_client)

    with pytest.raises(ImportError) as exc_info:
        factories.create_classifier("test-key")

    assert exc_info.value is inner


def test_create_classifier_without_sdk_raises_install_hint(monkeypatch):
    monkeypatch.delitem(
        sys.modules, "py_ai_toolkit.adapters.jev_adapter", raising=False
    )
    monkeypatch.setitem(sys.modules, "typesafe_sdk", None)

    for _ in range(2):
        with pytest.raises(ImportError) as exc_info:
            factories.create_classifier("test-key")

        assert str(exc_info.value) == INSTALL_HINT
        assert "py-ai-toolkit[jev]" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ImportError)


def test_package_imports_survive_missing_sdk():
    script = (
        "import sys; "
        "sys.modules['typesafe_sdk'] = None; "
        "import py_ai_toolkit.adapters, py_ai_toolkit.factories; "
        "assert callable(py_ai_toolkit.factories.create_classifier); "
        "assert 'py_ai_toolkit.adapters.jev_adapter' not in sys.modules"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


# PyAIToolkit classifier construction

CLASSIFIER_ENV = ("CLASSIFIER_API_KEY", "CLASSIFIER_MODEL", "CLASSIFIER_BASE_URL")
LLM_CONFIG = LLMConfig(api_key="test-llm-key", model="test-llm-model")


def _clear_classifier_env(monkeypatch):
    for name in CLASSIFIER_ENV:
        monkeypatch.delenv(name, raising=False)


class RecordingFactory:
    def __init__(self):
        self.calls = []
        self.returned = MinimalClassifier()

    def __call__(self, api_key, model="jev-latest", base_url=None):
        self.calls.append((api_key, model, base_url))
        return self.returned


def _patch_factory(monkeypatch):
    factory = RecordingFactory()
    monkeypatch.setattr("py_ai_toolkit.core.toolkit.create_classifier", factory)
    return factory


def test_toolkit_without_classifier_config_or_env_has_no_classifier(monkeypatch):
    _clear_classifier_env(monkeypatch)
    factory = _patch_factory(monkeypatch)

    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)

    assert toolkit.classifier is None
    assert factory.calls == []
    assert isinstance(toolkit.llm_client, LLMPort)
    assert toolkit.llm_client._model == "test-llm-model"
    assert toolkit.prompt_formatter is not None
    assert toolkit.model_handler is not None


def test_toolkit_env_key_set_after_import_activates_classifier(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    monkeypatch.setenv("CLASSIFIER_MODEL", "env-model")
    monkeypatch.setenv("CLASSIFIER_BASE_URL", "https://env.invalid")
    factory = _patch_factory(monkeypatch)

    toolkit = PyAIToolkit(
        main_model_config=LLM_CONFIG,
        alternative_models_configs=[
            LLMConfig(api_key="alt-key", model="alt-model", embedding_model="")
        ],
    )

    assert factory.calls == [("env-key", "env-model", "https://env.invalid")]
    assert toolkit.classifier is factory.returned
    assert toolkit.llm_client._model == "test-llm-model"
    assert len(toolkit.alternative_llm_clients) == 1


def test_toolkit_empty_env_key_does_not_activate_classifier(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.setenv("CLASSIFIER_API_KEY", "")
    factory = _patch_factory(monkeypatch)

    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)

    assert toolkit.classifier is None
    assert factory.calls == []


def test_toolkit_env_key_without_jev_extra_raises_install_hint(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    monkeypatch.delitem(
        sys.modules, "py_ai_toolkit.adapters.jev_adapter", raising=False
    )
    monkeypatch.setitem(sys.modules, "typesafe_sdk", None)

    with pytest.raises(ImportError) as exc_info:
        PyAIToolkit(main_model_config=LLM_CONFIG)

    assert str(exc_info.value) == INSTALL_HINT
    assert isinstance(exc_info.value.__cause__, ImportError)


MISSING_KEY_MESSAGE = "ClassifierConfig requires an api_key or CLASSIFIER_API_KEY."


def test_toolkit_explicit_config_beats_env_for_every_field(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    monkeypatch.setenv("CLASSIFIER_MODEL", "env-model")
    monkeypatch.setenv("CLASSIFIER_BASE_URL", "https://env.invalid")
    factory = _patch_factory(monkeypatch)

    toolkit = PyAIToolkit(
        main_model_config=LLM_CONFIG,
        classifier_config=ClassifierConfig(
            api_key="cfg-key",
            model="cfg-model",
            base_url="https://cfg.invalid",
        ),
    )

    assert factory.calls == [("cfg-key", "cfg-model", "https://cfg.invalid")]
    assert toolkit.classifier is factory.returned


def test_toolkit_model_falls_back_to_env_model(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.setenv("CLASSIFIER_MODEL", "env-model")
    factory = _patch_factory(monkeypatch)

    PyAIToolkit(
        main_model_config=LLM_CONFIG,
        classifier_config=ClassifierConfig(api_key="cfg-key"),
    )

    assert factory.calls == [("cfg-key", "env-model", None)]


def test_toolkit_model_falls_back_to_jev_latest_and_base_url_to_none(monkeypatch):
    _clear_classifier_env(monkeypatch)
    factory = _patch_factory(monkeypatch)

    PyAIToolkit(
        main_model_config=LLM_CONFIG,
        classifier_config=ClassifierConfig(api_key="cfg-key"),
    )

    assert factory.calls == [("cfg-key", "jev-latest", None)]


def test_toolkit_empty_config_fields_fall_back_to_env(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    monkeypatch.setenv("CLASSIFIER_MODEL", "env-model")
    monkeypatch.setenv("CLASSIFIER_BASE_URL", "https://env.invalid")
    factory = _patch_factory(monkeypatch)

    PyAIToolkit(
        main_model_config=LLM_CONFIG,
        classifier_config=ClassifierConfig(api_key="", model="", base_url=""),
    )

    assert factory.calls == [("env-key", "env-model", "https://env.invalid")]


def test_toolkit_config_without_key_raises_value_error(monkeypatch):
    _clear_classifier_env(monkeypatch)
    factory = _patch_factory(monkeypatch)

    with pytest.raises(ValueError) as exc_info:
        PyAIToolkit(main_model_config=LLM_CONFIG, classifier_config=ClassifierConfig())

    assert str(exc_info.value) == MISSING_KEY_MESSAGE
    assert factory.calls == []


def test_toolkit_config_with_empty_env_key_raises_value_error(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.setenv("CLASSIFIER_API_KEY", "")
    factory = _patch_factory(monkeypatch)

    with pytest.raises(ValueError) as exc_info:
        PyAIToolkit(
            main_model_config=LLM_CONFIG,
            classifier_config=ClassifierConfig(model="cfg-model"),
        )

    assert str(exc_info.value) == MISSING_KEY_MESSAGE
    assert factory.calls == []


def test_toolkit_propagates_factory_errors_unchanged(monkeypatch):
    _clear_classifier_env(monkeypatch)
    inner = RuntimeError("SDK client construction failed")

    def failing_factory(api_key, model="jev-latest", base_url=None):
        raise inner

    monkeypatch.setattr("py_ai_toolkit.core.toolkit.create_classifier", failing_factory)

    with pytest.raises(RuntimeError) as exc_info:
        PyAIToolkit(
            main_model_config=LLM_CONFIG,
            classifier_config=ClassifierConfig(api_key="cfg-key"),
        )

    assert exc_info.value is inner


def test_toolkit_config_key_without_jev_extra_raises_install_hint(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.delitem(
        sys.modules, "py_ai_toolkit.adapters.jev_adapter", raising=False
    )
    monkeypatch.setitem(sys.modules, "typesafe_sdk", None)

    with pytest.raises(ImportError) as exc_info:
        PyAIToolkit(
            main_model_config=LLM_CONFIG,
            classifier_config=ClassifierConfig(api_key="cfg-key"),
        )

    assert str(exc_info.value) == INSTALL_HINT
    assert isinstance(exc_info.value.__cause__, ImportError)


# PyAIToolkit.classify

UNCONFIGURED_MESSAGE = (
    "Classifier not configured: pass ClassifierConfig (or set CLASSIFIER_API_KEY) "
    "and install `py-ai-toolkit[jev]`."
)
QUESTIONS = {"q": NoulQuestion()}


class FakeClassifier(ClassifierPort):
    def __init__(self, response=FIXED_RESPONSE, error=None, model="fake-model"):
        self._model = model
        self.response = response
        self.error = error
        self.calls = []
        self.aclose_calls = 0

    async def classify(self, state, questions):
        self.calls.append((state, questions))
        if self.error is not None:
            raise self.error
        return self.response

    async def aclose(self):
        self.aclose_calls += 1


def _toolkit_with(monkeypatch, classifier):
    _clear_classifier_env(monkeypatch)
    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)
    toolkit.classifier = classifier
    return toolkit


def _recording_hooks():
    events = []

    async def before(ctx):
        events.append(("before", ctx))

    async def after(ctx):
        events.append(("after", ctx))

    return Hooks(before_classify=before, after_classify=after), events


@pytest.mark.parametrize("state", ["plain text", {"text": "hi"}, ["a", "b"]])
def test_classify_returns_port_response_and_passes_args(monkeypatch, state):
    fake = FakeClassifier()
    toolkit = _toolkit_with(monkeypatch, fake)

    result = run(toolkit.classify(state, QUESTIONS))

    assert result is FIXED_RESPONSE
    assert len(fake.calls) == 1
    assert fake.calls[0][0] is state
    assert fake.calls[0][1] is QUESTIONS


def test_classify_fires_before_then_after_with_contexts(monkeypatch):
    fake = FakeClassifier(model="jev-test")
    toolkit = _toolkit_with(monkeypatch, fake)
    hooks, events = _recording_hooks()
    state = {"text": "hi"}

    result = run(toolkit.classify(state, QUESTIONS, hooks=hooks))

    assert [name for name, _ in events] == ["before", "after"]
    before_ctx = events[0][1]
    after_ctx = events[1][1]
    assert isinstance(before_ctx, BeforeClassifyContext)
    assert before_ctx.state is state
    assert before_ctx.questions is QUESTIONS
    assert before_ctx.model == "jev-test"
    assert isinstance(after_ctx, AfterClassifyContext)
    assert after_ctx.response is result
    assert after_ctx.usage is FIXED_RESPONSE.usage
    assert after_ctx.model == "jev-test"


def test_classify_reports_non_negative_elapsed_ms(monkeypatch):
    toolkit = _toolkit_with(monkeypatch, FakeClassifier())
    hooks, events = _recording_hooks()

    run(toolkit.classify("text", QUESTIONS, hooks=hooks))

    after_ctx = events[-1][1]
    assert isinstance(after_ctx.elapsed_ms, float)
    assert after_ctx.elapsed_ms >= 0


def test_classify_elapsed_ms_measures_the_classifier_call(monkeypatch):
    import py_ai_toolkit.core.toolkit as toolkit_module

    clock = {"now": 10.0}
    monkeypatch.setattr(toolkit_module.time, "perf_counter", lambda: clock["now"])

    class SlowClassifier(FakeClassifier):
        async def classify(self, state, questions):
            clock["now"] += 0.25
            return await super().classify(state, questions)

    toolkit = _toolkit_with(monkeypatch, SlowClassifier())
    hooks, events = _recording_hooks()

    run(toolkit.classify("text", QUESTIONS, hooks=hooks))

    assert events[-1][1].elapsed_ms == pytest.approx(250.0)


def test_classify_without_hooks_returns_response(monkeypatch):
    fake = FakeClassifier()
    toolkit = _toolkit_with(monkeypatch, fake)

    result = run(toolkit.classify("text", QUESTIONS))

    assert result is FIXED_RESPONSE
    assert len(fake.calls) == 1


def test_classify_without_hooks_does_not_need_model_attribute(monkeypatch):
    _clear_classifier_env(monkeypatch)
    monkeypatch.setenv("CLASSIFIER_API_KEY", "env-key")
    factory = _patch_factory(monkeypatch)
    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)
    assert not hasattr(factory.returned, "_model")

    result = run(toolkit.classify("text", QUESTIONS))

    assert result is FIXED_RESPONSE


def test_classify_with_only_after_hook_fires_it(monkeypatch):
    toolkit = _toolkit_with(monkeypatch, FakeClassifier())
    seen = []

    async def after(ctx):
        seen.append(ctx)

    run(toolkit.classify("text", QUESTIONS, hooks=Hooks(after_classify=after)))

    assert len(seen) == 1
    assert seen[0].response is FIXED_RESPONSE


def test_classify_error_propagates_and_skips_after_hook(monkeypatch):
    error = ClassifierAdapterError("Jev request failed")
    toolkit = _toolkit_with(monkeypatch, FakeClassifier(error=error))
    hooks, events = _recording_hooks()

    with pytest.raises(ClassifierAdapterError) as exc_info:
        run(toolkit.classify("text", QUESTIONS, hooks=hooks))

    assert exc_info.value is error
    assert [name for name, _ in events] == ["before"]


def test_classify_before_hook_error_skips_classifier(monkeypatch):
    fake = FakeClassifier()
    toolkit = _toolkit_with(monkeypatch, fake)
    error = RuntimeError("hook failed")

    async def before(ctx):
        raise error

    with pytest.raises(RuntimeError) as exc_info:
        run(toolkit.classify("text", QUESTIONS, hooks=Hooks(before_classify=before)))

    assert exc_info.value is error
    assert fake.calls == []


def test_classify_unconfigured_raises_without_firing_hooks(monkeypatch):
    _clear_classifier_env(monkeypatch)
    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)
    assert toolkit.classifier is None
    hooks, events = _recording_hooks()

    with pytest.raises(ClassifierAdapterError) as exc_info:
        run(toolkit.classify("text", QUESTIONS, hooks=hooks))

    assert exc_info.value.message == UNCONFIGURED_MESSAGE
    assert str(exc_info.value) == UNCONFIGURED_MESSAGE
    assert events == []


def test_classify_unconfigured_guard_runs_before_empty_check(monkeypatch):
    _clear_classifier_env(monkeypatch)
    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)

    with pytest.raises(ClassifierAdapterError) as exc_info:
        run(toolkit.classify("text", {}))

    assert exc_info.value.message == UNCONFIGURED_MESSAGE


def test_classify_empty_questions_raises_without_firing_hooks(monkeypatch):
    fake = FakeClassifier()
    toolkit = _toolkit_with(monkeypatch, fake)
    hooks, events = _recording_hooks()

    with pytest.raises(ValueError) as exc_info:
        run(toolkit.classify("text", {}, hooks=hooks))

    assert str(exc_info.value) == "questions must not be empty."
    assert events == []
    assert fake.calls == []


def test_classify_rejects_empty_non_dict_mapping(monkeypatch):
    fake = FakeClassifier()
    toolkit = _toolkit_with(monkeypatch, fake)

    with pytest.raises(ValueError) as exc_info:
        run(toolkit.classify("text", MappingProxyType({})))

    assert str(exc_info.value) == "questions must not be empty."
    assert fake.calls == []


# PyAIToolkit.aclose


def test_aclose_delegates_to_classifier(monkeypatch):
    fake = FakeClassifier()
    toolkit = _toolkit_with(monkeypatch, fake)

    result = run(toolkit.aclose())

    assert result is None
    assert fake.aclose_calls == 1


def test_aclose_without_classifier_is_noop(monkeypatch):
    _clear_classifier_env(monkeypatch)
    toolkit = PyAIToolkit(main_model_config=LLM_CONFIG)
    assert toolkit.classifier is None

    assert run(toolkit.aclose()) is None


# Public exports

CLASSIFIER_EXPORTS = {
    "ClassifierConfig": ClassifierConfig,
    "ClassifierResponse": ClassifierResponse,
    "ClassifierUsage": ClassifierUsage,
    "NoulQuestion": NoulQuestion,
    "ChoiceQuestion": ChoiceQuestion,
    "ScoreQuestion": ScoreQuestion,
    "NoulAnswer": NoulAnswer,
    "ChoiceAnswer": ChoiceAnswer,
    "ScoreAnswer": ScoreAnswer,
    "Question": Question,
    "Answer": Answer,
    "ClassifierAdapterError": ClassifierAdapterError,
}


@pytest.mark.parametrize("name", sorted(CLASSIFIER_EXPORTS))
def test_classifier_names_exported_from_package(name):
    import py_ai_toolkit

    assert name in py_ai_toolkit.__all__
    assert getattr(py_ai_toolkit, name) is CLASSIFIER_EXPORTS[name]


def test_package_version_unchanged():
    import py_ai_toolkit

    assert py_ai_toolkit.__version__ == "0.7.0"
