import os
from typing import Generic, TypeVar

from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import BaseModel, field_validator

S = TypeVar("T", bound=BaseModel)


class LLMConfig(BaseModel):
    """
    Data model for LLM configuration.
    """

    model: str | None = os.getenv("LLM_MODEL", "")
    embedding_model: str | None = os.getenv("EMBEDDING_MODEL", "")
    api_key: str | None = os.getenv("LLM_API_KEY", "")
    base_url: str | None = os.getenv("LLM_BASE_URL", "")
    reasoning_effort: str | None = os.getenv("LLM_REASONING_EFFORT", "")


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


class EmbeddingUsage(BaseModel):
    """Token usage data from an embedding request."""

    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    """Data model for embedding response."""

    embedding: list[float]
    usage: EmbeddingUsage


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
