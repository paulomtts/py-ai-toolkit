from typing import Generic, TypeVar

from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


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
