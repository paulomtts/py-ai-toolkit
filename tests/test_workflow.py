from typing import Literal

import pytest
from grafo._internal import AwaitableCallback
from pydantic import BaseModel

from py_ai_toolkit import BaseWorkflow, Node, PyAIToolkit, TreeExecutor
from py_ai_toolkit.core.domain.errors import BaseError
from py_ai_toolkit.core.domain.interfaces import LLMConfig
from py_ai_toolkit.core.domain.models import BaseValidation, ValidationTest


class FruitPurchase(BaseModel):
    product: Literal["apple", "banana", "orange"]
    quantity: int


class ValidationResult(BaseModel):
    is_valid: bool
    reason: str
    humanized_failure: str | None = None


class MockWorkflowError(BaseError):
    pass


async def fruit_purchase(**_) -> FruitPurchase:
    return FruitPurchase(product="apple", quantity=5)


async def fruit_validation_success(**_) -> BaseValidation:
    return BaseValidation(
        validations=[
            ValidationTest(
                is_valid=True,
                reasoning="The identified purchase matches the user's request.",
            )
        ]
    )


async def fruit_validation_failure(**_) -> BaseValidation:
    return BaseValidation(
        validations=[
            ValidationTest(
                is_valid=False,
                reasoning="The identified purchase does not match the user's request.",
            )
        ]
    )


class MockWorkflow(BaseWorkflow):
    def __init__(self, ait: PyAIToolkit, validation_coroutine: AwaitableCallback):
        self.validation_coroutine = validation_coroutine
        super().__init__(ait, MockWorkflowError)

    async def run(self, message: str) -> FruitPurchase:
        purchase_node = Node[FruitPurchase](
            uuid="purchase_node",
            coroutine=fruit_purchase,
            kwargs=dict(
                prompt="{{ message }}",
                response_model=FruitPurchase,
                message=message,
            ),
        )

        validation_node = self.create_validation_nodes(
            coroutine=self.validation_coroutine,
            input=message,
            issues=["The identified purchase matches the user's request."],
            source_node=purchase_node,
        )

        await purchase_node.connect(validation_node)
        executor = TreeExecutor(uuid="Test Workflow", roots=[purchase_node])
        await executor.run()

        if not purchase_node.output or not validation_node.output:
            raise ValueError("Purchase validation failed")

        if not validation_node.output.valid:
            raise self.ErrorClass(
                status_code=400,
                message=f"Max retries reached. Validation node output: {validation_node.output.model_dump_json(indent=4)}",
            )

        print(purchase_node.output.model_dump_json(indent=4))
        print(validation_node.output.model_dump_json(indent=4))

        return purchase_node.output


@pytest.mark.asyncio
async def test_workflow_success():
    ait = PyAIToolkit(LLMConfig(model="qwen3:8b"))
    workflow = MockWorkflow(ait, fruit_validation_success)
    result = await workflow.run("I want to buy 5 apples")
    assert isinstance(result, FruitPurchase)
    assert result.product == "apple"
    assert result.quantity == 5


@pytest.mark.asyncio
async def test_workflow_failure():
    ait = PyAIToolkit(LLMConfig(model="qwen3:8b"))
    workflow = MockWorkflow(ait, fruit_validation_failure)
    with pytest.raises(MockWorkflowError):
        await workflow.run("I want to buy 5 bananas")


if __name__ == "__main__":
    pytest.main([__file__])
