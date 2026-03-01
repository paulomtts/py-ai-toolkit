from http import HTTPStatus
from typing import AsyncGenerator, Type

import instructor
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from py_ai_toolkit.core.domain.errors import LLMAdapterError
from py_ai_toolkit.core.domain.schemas import CompletionResponse, S
from py_ai_toolkit.core.ports import LLMPort


class InstructorAdapter(LLMPort):
    """
    Instructor implementation of the LLM port.
    """

    def __init__(
        self,
        model: str,
        embedding_model: str,
        api_key: str,
        base_url: str | None = None,
        reasoning_effort: str | None = None,
    ):
        self._model = model
        self._embedding_model = embedding_model

        client_kwargs = dict(
            api_key=api_key,
            base_url=base_url,
        )
        if not base_url:
            client_kwargs["base_url"] = "http://localhost:11434/v1"
        self.openai_client = AsyncOpenAI(**client_kwargs)  # type: ignore
        instructor_kwargs = dict(
            client=self.openai_client,
            mode=instructor.Mode.JSON,
        )
        if reasoning_effort:
            instructor_kwargs["reasoning_effort"] = reasoning_effort
        self.client = instructor.from_openai(**instructor_kwargs)

    async def embed(self, text: str) -> list[float]:
        """
        Embeds text into a vector space.
        """
        response = await self.openai_client.embeddings.create(
            model=self._embedding_model,
            input=[text],
        )
        return response.data[0].embedding

    async def chat(self, messages: list[dict[str, str]]) -> CompletionResponse:
        """
        Sends a message to the LLM and returns a structured response.

        Args:
            messages (list[dict[str, str]]): The messages to generate a response to

        Returns:
            str: The response from the LLM
        """
        output: ChatCompletion = await self.openai_client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore
            stream=False,
        )
        response = output.choices[0].message.content
        if not response:
            raise LLMAdapterError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE.value,
                message="No response from the model",
            )
        return CompletionResponse(
            completion=output,
            content=response,
        )

    async def stream(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[CompletionResponse, None]:
        """
        Streams text outputs from the model.

        Args:
            messages (list[dict[str, str]]): The messages to generate a response to

        Returns:
            AsyncGenerator[str, None]: The response from the LLM
        """
        output: AsyncGenerator[
            ChatCompletionChunk, None
        ] = await self.openai_client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore
            stream=True,
        )
        async for chunk in output:
            response = chunk.choices[0].delta.content
            if not response:
                continue
            yield CompletionResponse(
                completion=chunk,
                content=response,
            )

    async def asend(
        self,
        messages: list[dict[str, str]],
        response_model: Type[S],
    ) -> CompletionResponse[S]:
        """
        Sends a message to the LLM asynchronously and returns a structured response.

        Args:
            messages (list[dict[str, str]]): The messages to generate a response to
            response_model (Type[T]): The model to return the response as

        Returns:
            CompletionResponse[T]: The response from the LLM
        """

        (
            instance,
            completion,
        ) = await self.client.chat.completions.create_with_completion(
            response_model=response_model,
            model=self._model,
            messages=messages,  # type: ignore
        )
        if not instance:
            raise LLMAdapterError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE.value,
                message="No response content from the model",
            )
        return CompletionResponse(
            completion=completion,
            content=instance,
        )
