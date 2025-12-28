import os
from typing import Generic, TypeVar

from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMConfig(BaseModel):
    """
    Data model for LLM configuration.
    """

    model: str | None = os.getenv("LLM_MODEL", "")
    embedding_model: str | None = os.getenv("EMBEDDING_MODEL", "")
    api_key: str | None = os.getenv("LLM_API_KEY", "")
    base_url: str | None = os.getenv("LLM_BASE_URL", "")


class CompletionResponse(BaseModel, Generic[T]):
    """
    Data model for completion response.
    """

    completion: ChatCompletion | ChatCompletionChunk
    content: str | T

    @property
    def response_model(self) -> T:
        """
        Returns the instance of the response model of the completion response.
        """
        if isinstance(self.content, str) or isinstance(self.content, list):
            raise ValueError("Content is not structured.")
        return self.content
