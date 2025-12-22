from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar, Union

from grafo import Node
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
S = TypeVar("S", bound=BaseModel)
V = TypeVar("V", bound=BaseModel)


class WorkflowPort(ABC):
    """
    Abstract base class for workflow operations.
    """

    @abstractmethod
    async def task(
        self, path: str, response_model: Type[S] | None = None, **kwargs: Any
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
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """
        Run the workflow.
        """
        pass
