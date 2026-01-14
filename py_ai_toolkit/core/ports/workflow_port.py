from abc import ABC, abstractmethod
from typing import Any, Optional, Type, TypeVar, Union

from grafo import Node
from grafo._internal import AwaitableCallback
from pydantic import BaseModel

from py_ai_toolkit.core.domain.models import BaseValidation

T = TypeVar("T", bound=BaseModel)
S = TypeVar("S", bound=BaseModel)
V = TypeVar("V", bound=BaseValidation)


class WorkflowPort(ABC):
    """
    Abstract base class for workflow operations.
    """

    @abstractmethod
    async def task(
        self,
        path: str | None = None,
        prompt: str | None = None,
        response_model: Type[S] | None = None,
        **kwargs: Any,
    ) -> Union[str, S]:
        """
        Execute a task.

        Args:
            path (str): The path to the prompt template file
            prompt (str | None): The prompt to use for the task
            response_model (Type[S] | None): The response model to return the response as
            **kwargs: Additional arguments to pass to the prompt formatter

        Returns:
            Union[str, bool, S]: The response from the LLM with text content or a boolean indicating if the output is valid
        """
        pass

    @abstractmethod
    async def redirect(
        self,
        source_node: Node[S],
        validation_node: Node[V],
        target_nodes: list[Node[T]] | None = None,
    ) -> None:
        """
        Redirect the workflow.

        Args:
            source_node (Node[S]): The source node.
            validation_node (Node[V]): The validation node.
            target_nodes (list[Node[T]], optional): The target nodes. Defaults to None.
        """
        pass

    @abstractmethod
    def create_validation_nodes(
        self,
        input: Any,
        issues: list[str],
        source_node: Node[Any],
        target_nodes: list[Node[T]] | None = None,
        coroutine: AwaitableCallback | None = None,
        split_tests: bool = False,
    ) -> Node[BaseValidation] | list[Node[BaseValidation]]:
        """
        Create a validation node.
        """
        pass

    @abstractmethod
    def _create_task_node(
        self,
        coroutine: AwaitableCallback | None = None,
        response_model: Type[S] | None = None,
        prompt: str | None = None,
        path: str | None = None,
        kwargs: dict[str, Any] | None = None,
        on_before_run: tuple[AwaitableCallback, Optional[dict[str, Any]]] | None = None,
        on_after_run: tuple[AwaitableCallback, Optional[dict[str, Any]]] | None = None,
    ) -> Node[Any]:
        """
        Create a task node.
        """
        pass

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """
        Run the workflow.
        """
        pass
