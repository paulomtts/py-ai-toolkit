from http import HTTPStatus
from typing import Any, Type, TypeVar, Union

from grafo import Node
from pydantic import BaseModel

from py_ai_toolkit.core.domain.errors import BaseError
from py_ai_toolkit.core.ports import WorkflowPort
from py_ai_toolkit.core.tools import PyAIToolkit
from py_ai_toolkit.core.utils import logger

S = TypeVar("S", bound=BaseModel)
V = TypeVar("V", bound=BaseModel)
T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 3


class BaseWorkflow(WorkflowPort):
    """
    Base class for agentic workflows.
    """

    def __init__(
        self,
        ai_toolkit: PyAIToolkit,
        error_class: Type[BaseError],
        max_retries: int = MAX_RETRIES,
        echo: bool = False,
    ):
        self.ai_toolkit = ai_toolkit
        self.ErrorClass = error_class
        self.echo = echo

        # Stateful context
        self.current_retries = 0
        self.max_retries = max_retries

    # * Methods
    async def task(
        self,
        path: str,
        response_model: Type[S] | None = None,
        **kwargs: Any,
    ) -> Union[str, S]:
        """
        Execute a task.

        Args:
            path (str): The path to the prompt template file
            response_model (Type[S] | None): The response model to return the response as
            **kwargs: Additional arguments to pass to the prompt formatter

        Returns:
            Union[str, S]: The response from the LLM with text content
        """

        if not response_model:
            response = await self.ai_toolkit.chat(path=path, **kwargs)
            return response.content

        response = await self.ai_toolkit.asend(
            response_model=response_model,
            path=path,
            **kwargs,
        )
        return response.content

    def _validate_output(self, node: Node[T], detail: str) -> T:
        """
        Validates the source output of a node.
        """
        if not node.output:
            raise self.ErrorClass(
                status_code=HTTPStatus.BAD_REQUEST.value,
                message=detail,
            )
        return node.output

    async def redirect(
        self,
        source_node: Node[S],
        validation_node: Node[V],
        target_nodes: list[Node[T]] | None = None,
    ):
        """
        Redirects the flow of the workflow based on the validation node output.

        Args:
            source_node (Node[S]): The source node.
            validation_node (Node[V]): The validation node.
            target_nodes (list[Node[T]], optional): The target nodes. Defaults to None.
        """
        source_output = self._validate_output(source_node, "Source node output is None")
        validation_output = self._validate_output(
            validation_node, "Validation node output is None"
        )
        is_valid = getattr(validation_output, "is_valid", False)
        self.current_retries += 1
        if self.current_retries > self.max_retries and not is_valid:
            for child in validation_node.children:
                await validation_node.disconnect(child)
            raise self.ErrorClass(
                status_code=HTTPStatus.BAD_REQUEST.value,
                message=f"Max retries reached. Validation node output: {validation_output.model_dump_json(indent=4)}",
            )

        if self.echo:
            logger.debug(f"Source Output: {source_output.model_dump_json(indent=2)}")
            logger.debug(
                f"Validation Output: {validation_output.model_dump_json(indent=2)}"
            )
        for child in validation_node.children:
            await validation_node.disconnect(child)

        if is_valid:
            if target_nodes:
                for target_node in target_nodes:
                    await validation_node.connect(target_node)
            return
        source_node.kwargs["eval"] = lambda: str(
            source_output.model_dump_json(indent=2)
        ) + str(getattr(validation_output, "reasoning", None))
        await validation_node.connect(source_node)

    async def run(self, *_: Any, **__: Any) -> Any:
        """
        Run the workflow.
        """
        raise NotImplementedError("Run method not implemented")
