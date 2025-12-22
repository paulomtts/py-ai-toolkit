from typing import Literal

import pytest
from pydantic import BaseModel

from py_ai_toolkit import AITools, BaseWorkflow, Node, TreeExecutor
from py_ai_toolkit.core.domain.errors import BaseError


class FruitPurchase(BaseModel):
    product: Literal["apple", "banana", "orange"]
    quantity: int


class ValidationResult(BaseModel):
    is_valid: bool
    reason: str
    humanized_failure: str | None = None


class MockWorkflowError(BaseError):
    pass


class MockWorkflow(BaseWorkflow):
    def __init__(self, ait: AITools):
        super().__init__(ait, MockWorkflowError)

    async def fruit_purchase(self, **_) -> FruitPurchase:
        return FruitPurchase(product="apple", quantity=5)

    async def fruit_validation(self, **_) -> ValidationResult:
        return ValidationResult(
            is_valid=True,
            reason="The identified purchase matches the user's request.",
            humanized_failure=None,
        )

    async def run(self, message: str) -> FruitPurchase:
        purchase_node = Node[FruitPurchase](
            uuid="purchase_node",
            coroutine=self.fruit_purchase,
            kwargs=dict(
                path="./tests/purchase.md",
                response_model=FruitPurchase,
                message=message,
            ),
        )

        validation_node = Node[ValidationResult](
            uuid="validation_node",
            coroutine=self.fruit_validation,
            kwargs=dict(
                path="./tests/validation.md",
                response_model=ValidationResult,
                message=message,
                purchase=lambda: purchase_node.output,
            ),
        )

        await purchase_node.connect(validation_node)
        executor = TreeExecutor(uuid="Test Workflow", roots=[purchase_node])
        await executor.run()

        if (
            not purchase_node.output
            or not validation_node.output
            or not validation_node.output.is_valid
        ):
            raise ValueError("Purchase validation failed")

        print(purchase_node.output.model_dump_json(indent=4))
        print(validation_node.output.model_dump_json(indent=4))

        return purchase_node.output


@pytest.mark.asyncio
async def test_mock_workflow():
    ait = AITools("qwen3:8b")
    workflow = MockWorkflow(ait)
    result = await workflow.run("I want to buy 5 apples")
    assert isinstance(result, FruitPurchase)
    assert result.product == "apple"
    assert result.quantity == 5


if __name__ == "__main__":
    pytest.main([__file__])
