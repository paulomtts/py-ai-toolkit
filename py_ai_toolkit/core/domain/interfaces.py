import os
from typing import Generic, TypeVar

from grafo import TreeExecutor
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import BaseModel, field_validator

from py_ai_toolkit.core.domain.models import BaseIssue
from py_ai_toolkit.core.utils import logger

S = TypeVar("T", bound=BaseModel)
V = TypeVar("V", bound=BaseIssue)


class LLMConfig(BaseModel):
    """
    Data model for LLM configuration.
    """

    model: str | None = os.getenv("LLM_MODEL", "")
    embedding_model: str | None = os.getenv("EMBEDDING_MODEL", "")
    api_key: str | None = os.getenv("LLM_API_KEY", "")
    base_url: str | None = os.getenv("LLM_BASE_URL", "")


class CompletionResponse(BaseModel, Generic[S]):
    """
    Data model for completion response.
    """

    completion: ChatCompletion | ChatCompletionChunk
    content: str | S

    @property
    def response_model(self) -> S:
        """
        Returns the instance of the response model of the completion response.
        """
        if isinstance(self.content, str) or isinstance(self.content, list):
            raise ValueError("Content is not structured.")
        return self.content


class BaseValidationConfig(BaseModel):
    count: int = 1
    issues: list[str] = []
    max_retries: int = 0

    @field_validator("count")
    def validate_count(cls, v: int) -> int:
        """
        Validates the count.
        """
        if v < 1:
            raise ValueError("Count must be at least 1.")
        if v % 2 == 0:
            raise ValueError("Count must be odd.")
        return v

    @field_validator("required_ahead", check_fields=False)
    def validate_required_ahead(cls, v: int) -> int:
        """
        Validates the required ahead.
        """
        if v < 1:
            raise ValueError("Required ahead must be at least 1.")
        return v


class SingleShotValidationConfig(BaseValidationConfig):
    count: int = 1
    required_ahead: int = 1
    max_retries: int = 3

    @field_validator("count")
    def validate_count(cls, v: int) -> int:
        """
        Validates the count.
        """
        if v != 1:
            raise ValueError("Count must be 1.")
        return v


class ThresholdVotingValidationConfig(BaseValidationConfig):
    count: int = 3
    required_ahead: int = 1


class KAheadVotingValidationConfig(BaseValidationConfig):
    count: int = 5
    required_ahead: int = 3


ValidationConfig = (
    SingleShotValidationConfig
    | ThresholdVotingValidationConfig
    | KAheadVotingValidationConfig
)


class IssueTreeExecutor(TreeExecutor[V]):
    def __init__(self, config: ValidationConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.successes: int = 0
        self.failures: int = 0
        self.failure_reasonings: list[str] = []
        self.round_number: int = 0

    async def run_validation_round(
        self,
        echo: bool = False,
    ) -> bool | None:
        """
        Executes a round of issue validation for all leaf nodes in the tree.

        This method runs the tree executor to evaluate all issue nodes corresponding to a
        validation round. It aggregates the number of successes and failures by inspecting
        each leaf node's output (expecting an "is_valid" attribute). The function also
        collects failure reasonings for reporting or further decision making.

        Returns:
            bool | None:
                - True if the number of additional successes over failures meets or exceeds
                  the `required_ahead` threshold.
                - False if the number of additional failures over successes meets or exceeds
                  the `required_ahead` threshold.
                - None if neither threshold has been met, indicating that further rounds
                  are needed or a decision cannot be made yet.
        """
        self.round_number += 1
        nodes = await self.run()
        self.successes += sum(int(node.output.is_valid) for node in nodes)
        self.failures += sum(int(not node.output.is_valid) for node in nodes)
        self.failure_reasonings.extend(
            [node.output.reasoning for node in nodes if not node.output.is_valid]
        )
        if self.successes - self.failures >= self.config.required_ahead:
            if echo:
                logger.debug(
                    f"Round {self.round_number} Succeeded, successes: {self.successes}, failures: {self.failures}"
                )
            return True
        elif self.failures - self.successes >= self.config.required_ahead:
            if echo:
                logger.debug(
                    f"Round {self.round_number} Failed, successes: {self.successes}, failures: {self.failures}"
                )
            return False
        else:
            return None
