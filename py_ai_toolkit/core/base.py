from http import HTTPStatus
from typing import Any, Literal, Optional, Type, TypeVar, Union, overload
from uuid import uuid4

from grafo import Node
from grafo._internal import AwaitableCallback
from pydantic import BaseModel

from py_ai_toolkit.core.domain.errors import BaseError
from py_ai_toolkit.core.domain.models import BaseValidation, ValidationTest
from py_ai_toolkit.core.ports import WorkflowPort
from py_ai_toolkit.core.tools import PyAIToolkit
from py_ai_toolkit.core.utils import logger

S = TypeVar("S", bound=BaseModel)
V = TypeVar("V", bound=BaseValidation)
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
        path: str | None = None,
        prompt: str | None = None,
        response_model: Type[S] | None = None,
        **kwargs: Any,
    ) -> Union[str, S]:
        """
        Execute a task.

        Args:
            path (str | None): The path to the prompt template file
            prompt (str | None): The prompt to use for the task
            response_model (Type[S] | None): The response model to return the response as
            **kwargs: Additional arguments to pass to the prompt formatter

        Returns:
            Union[str, bool, S]: The response from the LLM with text content or a boolean indicating if the output is valid
        """
        if not path and not prompt:
            raise ValueError("Either path or prompt must be provided")
        if path and prompt:
            raise ValueError("Only one of path or prompt can be provided")

        base_kwargs = dict[str, str | None](
            path=path,
            prompt=prompt,
        )

        if not response_model:
            response = await self.ai_toolkit.chat(**base_kwargs, **kwargs)
            return response.content

        response = await self.ai_toolkit.asend(
            response_model=response_model,
            **base_kwargs,
            **kwargs,
        )
        return response.content

    def _ensure_source_node_output(self, node: Node[T], detail: str) -> T:
        """
        Ensures the output of a node is not None.
        """
        if not node.output:
            raise self.ErrorClass(
                status_code=HTTPStatus.BAD_REQUEST.value,
                message=detail,
            )
        return node.output

    def _ensure_validation_node_output(self, node: Node[V], detail: str) -> V:
        """
        Ensures the output of a node is a BaseValidation model.
        """
        if not isinstance(node.output, BaseValidation):
            raise self.ErrorClass(
                status_code=HTTPStatus.BAD_REQUEST.value,
                message=detail,
            )
        return node.output

    async def _disconnect_children(self, node: Node[V]):
        """
        Disconnects all children of a node.
        """
        for child in node.children:
            await node.disconnect(child)

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
        source_output = self._ensure_source_node_output(
            source_node, "Source node output is None"
        )
        validation_output = self._ensure_validation_node_output(
            validation_node, "Validation node output is None"
        )
        self.current_retries += 1
        if self.current_retries > self.max_retries and not validation_output.valid:
            await self._disconnect_children(validation_node)
            raise self.ErrorClass(
                status_code=HTTPStatus.BAD_REQUEST.value,
                message=f"Max retries reached. Validation node output: {validation_output.model_dump_json(indent=4)}",
            )

        if self.echo:
            logger.debug(f"Source Output: {source_output.model_dump_json(indent=2)}")
            logger.debug(
                f"Validation Output: {validation_output.model_dump_json(indent=2)}"
            )
        await self._disconnect_children(validation_node)

        if validation_output.valid:
            if target_nodes:
                for target_node in target_nodes:
                    await validation_node.connect(target_node)
            return
        failed_tests_reasonings = "\n".join(
            [
                test.reasoning
                for test in validation_output.validations
                if not test.is_valid
            ]
        )
        eval_property_name = (
            source_node.uuid.strip().replace(" ", "_").lower() + "_eval"
        )
        source_node.kwargs[eval_property_name] = lambda: str(
            source_output.model_dump_json(indent=2)
        ) + str(failed_tests_reasonings)
        await validation_node.connect(source_node)

    @overload
    def _create_validation_model(self, issues: list[str]) -> Type[BaseValidation]: ...

    @overload
    def _create_validation_model(
        self, issues: list[str], *, split_tests: Literal[True]
    ) -> list[Type[ValidationTest]]: ...

    def _create_validation_model(
        self, issues: list[str], split_tests: bool = False
    ) -> Type[BaseValidation] | list[Type[ValidationTest]]:
        """
        Creates a validation model for a list of issues.

        Args:
            issues (list[str]): The issues to validate against

        Returns:
            list[Type[ValidationTest]]: The validation models
        """
        validation_models = [
            self.ai_toolkit.inject_types(ValidationTest, [], issue) for issue in issues
        ]
        if split_tests:
            return validation_models
        return self.ai_toolkit.inject_types(
            BaseValidation, [("validations", list[Union[*validation_models]])]
        )

    @overload
    def create_validation_nodes(
        self,
        input: Any,
        issues: list[str],
        source_node: Node[Any],
        target_nodes: list[Node[T]] | None = None,
        coroutine: AwaitableCallback | None = None,
    ) -> Node[BaseValidation]: ...

    @overload
    def create_validation_nodes(
        self,
        input: Any,
        issues: list[str],
        source_node: Node[Any],
        target_nodes: list[Node[T]] | None = None,
        coroutine: AwaitableCallback | None = None,
        *,
        split_tests: bool,
    ) -> list[Node[BaseValidation]]: ...

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
        Creates a validation node for a list of issues and setups it's redirection callback.
        NOTE: if you need extra functionality, you can override the `on_after_run` callback.

        Args:
            input (Any): The input used to create the source node output
            issues (list[str]): The issues to validate against
            source_node (Node[Any]): The source node
            target_nodes (list[Node[T]] | None): The target nodes
            coroutine (AwaitableCallback | None): The coroutine to use for the validation node. Defaults to the `self.task(...)` method.
            split_tests (bool): Whether to split the tests into multiple nodes. Defaults to False.
        Returns:
            Node: The validation node
        """
        base_kwargs = dict(
            input=input,
            output=lambda: source_node.output,
            prompt="""
                # Task
                Evaluate the output against each test.
                
                # Context
                ## Input
                {{ input }}

                ## Output
                {{ output }}
            """,
        )
        if not split_tests:
            validation_model = self._create_validation_model(issues)
            validation_node = Node[BaseValidation](
                uuid=uuid4().hex + "_validation_node",
                coroutine=coroutine or self.task,
                kwargs={**base_kwargs, **dict(response_model=validation_model)},
            )
            validation_node.on_after_run = (
                self.redirect,
                dict(
                    source_node=source_node,
                    validation_node=validation_node,
                    target_nodes=target_nodes,
                ),
            )

            return validation_node

        validation_nodes = []
        for index, response_model in enumerate(
            self._create_validation_model(issues, split_tests=split_tests)
        ):
            validation_node = Node[BaseValidation](
                uuid=uuid4().hex + f"_issue{index}_validation_node",
                coroutine=coroutine or self.task,
                kwargs={**base_kwargs, **dict(response_model=response_model)},
            )
            validation_node.on_after_run = (
                self.redirect,
                dict(
                    source_node=source_node,
                    validation_node=validation_node,
                    target_nodes=target_nodes,
                ),
            )
            validation_nodes.append(validation_node)
        return validation_nodes

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
        Creates a task node with a prompt and path.
        """
        return Node[Type[S]](
            uuid=uuid4().hex + "_task_node",
            coroutine=coroutine or self.task,
            on_before_run=on_before_run,
            on_after_run=on_after_run,
            kwargs=dict(
                prompt=prompt,
                path=path,
                response_model=response_model,
                **(kwargs or {}),
            ),
        )

    async def run(self, *_: Any, **__: Any) -> Any:
        """
        Run the workflow.
        """
        raise NotImplementedError("Run method not implemented")
