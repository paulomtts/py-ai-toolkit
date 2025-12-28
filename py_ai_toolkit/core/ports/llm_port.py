from abc import ABC, abstractmethod
from typing import AsyncGenerator, Type, TypeVar

from pydantic import BaseModel

from py_ai_toolkit.core.domain.interfaces import CompletionResponse

T = TypeVar("T", bound=BaseModel)


class LLMPort(ABC):
    """
    Abstract base class for LLM ports.
    """

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """
        Embeds text into a vector space.
        """
        pass

    @abstractmethod
    async def chat(self, messages: list[dict[str, str]]) -> CompletionResponse:
        """
        Sends a message to the LLM and returns a text response.

        Args:
            messages (list[dict[str, str]]): The messages to generate a response to

        Returns:
            CompletionResponse: The response from the LLM
        """
        pass

    @abstractmethod
    async def stream(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[CompletionResponse, None]:
        """
        Sends a message to the LLM and streams the text response.

        Args:
            messages (list[dict[str, str]]): The messages to generate a response to

        Returns:
            AsyncGenerator[CompletionResponse, None]: The response from the LLM
        """
        yield  # type: ignore

    @abstractmethod
    async def asend(
        self,
        messages: list[dict[str, str]],
        response_model: Type[T],
    ) -> CompletionResponse[T]:
        """
        Sends a message to the LLM asynchronously and returns an instance of the response model.

        Args:
            messages (list[dict[str, str]]): The messages to generate a response to
            response_model (Type[T]): The model to return the response as

        Returns:
            CompletionResponse[T]: The response from the LLM
        """
        pass
