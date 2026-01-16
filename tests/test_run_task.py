import logging

import pytest
from dotenv import load_dotenv
from pydantic import BaseModel

from py_ai_toolkit import PyAIToolkit
from py_ai_toolkit.core.domain.interfaces import (
    KAheadVotingValidationConfig,
    LLMConfig,
    SingleShotValidationConfig,
    ThresholdVotingValidationConfig,
)

logger = logging.getLogger("grafo")
logger.setLevel(logging.INFO)
load_dotenv()


class FruitPurchase(BaseModel):
    product: str
    quantity: int


@pytest.mark.asyncio
async def test_run_task_no_validations():
    ai_toolkit = PyAIToolkit(main_model_config=LLMConfig())

    result = await ai_toolkit.run_task(
        template="""
            You will extract a purchase from the follwing message:
            {{ message }}
        """.strip(),
        response_model=FruitPurchase,
        kwargs=dict(message="I want to buy 5 apples."),
        echo=True,
    )

    assert isinstance(result, FruitPurchase)


@pytest.mark.asyncio
async def test_run_task_with_single_validations():
    ai_toolkit = PyAIToolkit(main_model_config=LLMConfig())

    result = await ai_toolkit.run_task(
        template="""
            You will extract a purchase from the follwing message:
            {{ message }}
        """.strip(),
        response_model=FruitPurchase,
        kwargs=dict(message="I want to buy 5 apples."),
        config=SingleShotValidationConfig(
            issues=["The identified purchase matches the user's request."],
        ),
        echo=True,
    )

    assert isinstance(result, FruitPurchase)


@pytest.mark.asyncio
async def test_run_task_with_threshold_validations():
    ai_toolkit = PyAIToolkit(main_model_config=LLMConfig())

    result = await ai_toolkit.run_task(
        template="""
            You will extract a purchase from the follwing message:
            {{ message }}
        """.strip(),
        response_model=FruitPurchase,
        kwargs=dict(message="I want to buy 5 apples."),
        config=ThresholdVotingValidationConfig(
            issues=["The identified purchase matches the user's request."],
        ),
        echo=True,
    )

    assert isinstance(result, FruitPurchase)


@pytest.mark.asyncio
async def test_run_task_with_kahead_validations():
    ai_toolkit = PyAIToolkit(main_model_config=LLMConfig())

    result = await ai_toolkit.run_task(
        template="""
            You will extract a purchase from the follwing message:
            {{ message }}
        """.strip(),
        response_model=FruitPurchase,
        kwargs=dict(message="I want to buy 5 apples."),
        config=KAheadVotingValidationConfig(
            issues=["The identified purchase matches the user's request."],
        ),
        echo=True,
    )

    assert isinstance(result, FruitPurchase)
