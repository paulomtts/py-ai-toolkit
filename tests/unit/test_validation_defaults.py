import asyncio
import inspect

import pytest
from pydantic import BaseModel

from py_ai_toolkit.core import base as base_module
from py_ai_toolkit.core.base import BaseWorkflow
from py_ai_toolkit.core.domain.errors import WorkflowError
from py_ai_toolkit.core.domain.schemas import LLMConfig
from py_ai_toolkit.core.toolkit import PyAIToolkit


class Answer(BaseModel):
    text: str


def _workflow(monkeypatch) -> BaseWorkflow:
    monkeypatch.delenv("CLASSIFIER_API_KEY", raising=False)
    toolkit = PyAIToolkit(main_model_config=LLMConfig(api_key="k", model="m"))
    return BaseWorkflow(ai_toolkit=toolkit, error_class=WorkflowError, echo=False)


@pytest.mark.parametrize(
    "method",
    [
        BaseWorkflow.create_task_tree,
        BaseWorkflow.build_task_node,
        PyAIToolkit.run_task,
    ],
)
def test_validation_config_defaults_to_none_not_a_shared_instance(method):
    assert inspect.signature(method).parameters["config"].default is None


def test_each_call_builds_its_own_default_validation_config(monkeypatch):
    created = []
    real = base_module.SingleShotValidationConfig

    class Spy(real):
        def __init__(self, **data):
            super().__init__(**data)
            created.append(self)

    monkeypatch.setattr(base_module, "SingleShotValidationConfig", Spy)
    workflow = _workflow(monkeypatch)

    async def build_twice():
        await workflow.create_task_tree(template="t", response_model=Answer, kwargs={})
        await workflow.create_task_tree(template="t", response_model=Answer, kwargs={})
        await workflow.build_task_node(
            uuid="n", template="t", response_model=Answer, kwargs={}
        )

    asyncio.run(build_twice())

    assert len(created) == 3
    assert len({id(config) for config in created}) == 3


def test_default_config_adds_no_validation_node(monkeypatch):
    workflow = _workflow(monkeypatch)

    executor = asyncio.run(
        workflow.create_task_tree(template="t", response_model=Answer, kwargs={})
    )

    assert len(executor.roots) == 1
    assert executor.roots[0].children == []
