import os
import random
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional, Type, TypeVar
from uuid import uuid4

from grafo import Node, TreeExecutor
from grafo._internal import AwaitableCallback
from pydantic import BaseModel
from toon_python import encode

from py_ai_toolkit.core.domain.errors import BaseError
from py_ai_toolkit.core.domain.interfaces import CompletionResponse, LLMConfig
from py_ai_toolkit.core.domain.models import BaseValidation
from py_ai_toolkit.core.utils import logger
from py_ai_toolkit.factories import (
    create_llm_client,
    create_model_handler,
    create_prompt_formatter,
)

if TYPE_CHECKING:
    from py_ai_toolkit.core.base import BaseWorkflow

T = TypeVar("T", bound=BaseModel)
S = TypeVar("S", bound=BaseModel)


class PyAIToolkit:
    """
    A class that bundles methods for easily interacting with LLMs and manipulating pydantic BaseModels.
    """

    def __init__(
        self,
        main_model_config: LLMConfig,
        alternative_models_configs: list[LLMConfig] | None = None,
    ):
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

    def _create_workflow(
        self,
        max_retries: int = 3,
        echo: bool = False,
    ) -> "BaseWorkflow":
        from py_ai_toolkit.core.base import BaseWorkflow

        return BaseWorkflow(
            ai_toolkit=self,
            error_class=BaseError,
            max_retries=max_retries,
            echo=echo,
        )

    async def _create_task_subtree(
        self,
        response_model: Type[S],
        kwargs: dict[str, Any],
        prompt: str | None = None,
        path: str | None = None,
        on_before_run: tuple[AwaitableCallback, Optional[dict[str, Any]]] | None = None,
        on_after_run: tuple[AwaitableCallback, Optional[dict[str, Any]]] | None = None,
        issues: list[str] | None = None,
        split: bool = False,
    ) -> tuple[
        TreeExecutor[Type[S] | BaseValidation],
        Node[Type[S]],
        list[Node[BaseValidation]],
    ]:
        workflow = self._create_workflow()
        task_node = workflow._create_task_node(
            response_model=response_model,
            prompt=prompt,
            path=path,
            on_before_run=on_before_run,
            on_after_run=on_after_run,
            kwargs=kwargs,
        )
        validation_nodes = []
        if issues:
            validation_nodes = workflow.create_validation_nodes(
                input=lambda: task_node.output,
                issues=issues,
                source_node=task_node,
                split_tests=split,
            )
            if isinstance(validation_nodes, list):
                for node in validation_nodes:
                    await task_node.connect(node)
            else:
                await task_node.connect(validation_nodes)

        return (
            TreeExecutor[Type[S] | BaseValidation](
                uuid=f"{response_model.__name__}_{uuid4().hex}",
                roots=[task_node],
            ),
            task_node,
            validation_nodes,
        )

    async def run_task(
        self,
        response_model: Type[S],
        kwargs: dict[str, Any],
        prompt: str | None = None,
        path: str | None = None,
        on_before_run: tuple[AwaitableCallback, Optional[dict[str, Any]]] | None = None,
        on_after_run: tuple[AwaitableCallback, Optional[dict[str, Any]]] | None = None,
        issues: list[str] | None = None,
        split: bool = False,
        echo: bool = False,
    ) -> S:
        """
        Run a task and validate the output. Notes:
        - You can provide a prompt or a path, but NEVER both.
        - You can provide issues to validate the output, but if you don't provide issues, the validation node will not be created.
        - Grafo allows us to execute callbacks before and after the task is run. They are attached to the task node.

        Args:
            response_model: The type of the task output.
            kwargs: The kwargs to pass to the task node.
            prompt: The prompt to pass to the task node.
            path: The path to the prompt template file.
            on_before_run: The on_before_run callback to pass to the task node.
            on_after_run: The on_after_run callback to pass to the task node.
            issues: The issues to pass to the validation node.
            split: Whether to split the issues into multiple LLM calls.
            echo: Whether to echo the output.

        Returns:
            The output of the task.
        """
        executor, task_node, validation_nodes = await self._create_task_subtree(
            response_model=response_model,
            kwargs=kwargs,
            prompt=prompt,
            path=path,
            issues=issues,
            split=split,
            on_before_run=on_before_run,
            on_after_run=on_after_run,
        )
        await executor.run()

        if isinstance(validation_nodes, list):
            validation_nodes_list = validation_nodes
        else:
            validation_nodes_list = [validation_nodes]

        if not task_node.output or any(
            not node.output for node in validation_nodes_list
        ):
            raise BaseError(
                message="Triple extraction workflow failed.", status_code=500
            )
        if not isinstance(task_node.output, response_model):
            raise BaseError(
                message=f"Task output is not an instance of {response_model.__name__}",
                status_code=500,
            )

        if echo:
            if task_node.output and isinstance(task_node.output, BaseModel):
                logger.debug(task_node.output.model_dump_json(indent=2))
            for node in validation_nodes_list:
                if node.output and isinstance(node.output, BaseModel):
                    logger.debug(node.output.model_dump_json(indent=2))

        return task_node.output
