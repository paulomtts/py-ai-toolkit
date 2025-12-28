import os
import random
from typing import Any, AsyncGenerator, Type, TypeVar

from pydantic import BaseModel
from toon_python import encode

from py_ai_toolkit.core.domain.interfaces import CompletionResponse, LLMConfig
from py_ai_toolkit.factories import (
    create_llm_client,
    create_model_handler,
    create_prompt_formatter,
)

T = TypeVar("T", bound=BaseModel)
N = TypeVar("N")
C = TypeVar("C")


class PyAIToolkit:
    """
    A class that bundles methods for easily interacting with LLMs and manipulating pydantic BaseModels.
    """

    def __init__(
        self,
        main_model_config: LLMConfig,
        alternative_models_configs: list[LLMConfig] | None = None,
    ):
        """
        Initialize AIT with LLM client and prompt formatter.

        Args:
            model (str): The model to use for completions
            embedding_model (str): The model to use for embeddings
            api_key (str): The API key for authentication
        """
        self.llm_client = create_llm_client(
            model=main_model_config.model or os.getenv("LLM_MODEL", ""),
            embedding_model=main_model_config.embedding_model
            or os.getenv("EMBEDDING_MODEL", ""),
            api_key=main_model_config.api_key or os.getenv("LLM_API_KEY", ""),
            base_url=main_model_config.base_url or os.getenv("LLM_BASE_URL", ""),
        )
        self.alternative_llm_clients = []
        if alternative_models_configs:
            self.alternative_llm_clients = [
                create_llm_client(**config.model_dump())
                for config in alternative_models_configs
            ]
        self.prompt_formatter = create_prompt_formatter()
        self.model_handler = create_model_handler()

    def inject_types(
        self,
        model: Type[T],
        fields: list[tuple[str, Any]],
        docstring: str | None = None,
    ) -> Type[T]:
        """
        Injects field types into a response model.

        Args:
            model (Type[T]): The model to inject types into
            fields (list[tuple[str, Any]]): The fields to inject types into

        Returns:
            Type[T]: The model with injected types

        Example:
            >>> ait.inject_types(Fruit, [("name", Literal[tuple(available_fruits)])])
        """
        return self.model_handler.inject_types(model, fields, docstring)

    def reduce_model_schema(
        self, model: Type[T], include_description: bool = True
    ) -> str:
        """
        Reduces a response model schema into version with less tokens. Helpful for reducing prompt noise.

        Args:
            model (Type[T]): The model to reduce the schema of
            include_description (bool): Whether to include the description in the schema

        Returns:
            str: The reduced schema
        """
        return self.model_handler.reduce_model_schema(model, include_description)

    def _prepare_messages(
        self, path: str | None = None, prompt: str | None = None, **kwargs: Any
    ) -> list:
        for key, value in kwargs.items():
            if isinstance(value, BaseModel):
                kwargs[key] = encode(value.model_dump_json())
            elif (
                isinstance(value, list)
                and len(value) > 0
                and isinstance(value[0], BaseModel)
                and all(isinstance(item, type(value[0])) for item in value)
            ):
                kwargs[key] = encode([item.model_dump_json() for item in value])
        final_prompt = self.prompt_formatter.render(
            path=path,
            prompt=prompt,
            input=kwargs,
        )
        return [
            {"role": "system", "content": final_prompt},
        ]

    async def embed(self, text: str) -> list[float]:
        """
        Embeds text into a vector space.
        """
        return await self.llm_client.embed(text=text)

    async def chat(
        self,
        path: str | None = None,
        prompt: str | None = None,
        **kwargs: Any,
    ) -> CompletionResponse:
        """
        Execute a chat task and return a text response.

        Args:
            path (str): The path to the prompt template file
            **kwargs: Additional arguments to pass to the prompt formatter

        Returns:
            CompletionResponse: The response from the LLM with text content
        """
        messages = self._prepare_messages(path, prompt, **kwargs)
        return await self.llm_client.chat(messages=messages)

    async def stream(
        self,
        path: str | None = None,
        prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[CompletionResponse, None]:
        """
        Execute a streaming task and return a stream of text responses.

        Args:
            path (str): The path to the prompt template file
            **kwargs: Additional arguments to pass to the prompt formatter

        Returns:
            AsyncGenerator[CompletionResponse, None]: Stream of responses from the LLM
        """
        messages = self._prepare_messages(path, prompt, **kwargs)
        async for response in self.llm_client.stream(messages=messages):
            yield response

    async def asend(
        self,
        response_model: Type[T],
        path: str | None = None,
        prompt: str | None = None,
        **kwargs: Any,
    ) -> CompletionResponse[T]:
        """
        Execute a structured task and return a typed response.

        Args:
            response_model (Type[T]): The model to return the response as
            path (str): Path to the prompt template file
            **kwargs: Additional arguments to pass to the prompt formatter

        Returns:
            CompletionResponse[T]: The response from the LLM with structured content
        """
        client = self.llm_client
        if self.alternative_llm_clients:
            client = random.choice(self.alternative_llm_clients)
        messages = self._prepare_messages(path, prompt, **kwargs)
        response = await client.asend(
            messages=messages,
            response_model=response_model,
        )
        if not isinstance(response.content, response_model):
            raise ValueError(
                f"Response content is not an instance of {response_model.__name__}"
            )
        return response
