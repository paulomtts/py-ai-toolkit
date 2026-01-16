from typing import Any, Type, TypeVar, Union
from uuid import uuid4

from grafo import Node, TreeExecutor
from pydantic import BaseModel

from py_ai_toolkit.core.domain.errors import WorkflowError
from py_ai_toolkit.core.domain.interfaces import (
    IssueTreeExecutor,
    KAheadVotingValidationConfig,
    SingleShotValidationConfig,
    ThresholdVotingValidationConfig,
    ValidationConfig,
)
from py_ai_toolkit.core.domain.models import BaseIssue
from py_ai_toolkit.core.tools import PyAIToolkit
from py_ai_toolkit.core.utils import logger

S = TypeVar("S", bound=BaseModel)
V = TypeVar("V", bound=BaseIssue)
T = TypeVar("T", bound=BaseModel)


class BaseWorkflow:
    """
    Base class for workflows.
    """

    def __init__(
        self,
        ai_toolkit: PyAIToolkit,
        error_class: Type[Exception],
        echo: bool = False,
    ):
        self.ai_toolkit = ai_toolkit
        self.ErrorClass = error_class
        self.echo = echo

        # Stateful context
        self.current_retries = 0
        self.executor: TreeExecutor[S | V] | None = None
        self.failure_reasonings: dict[str, list[str]] = {}

    async def task(
        self,
        template: str | None = None,
        response_model: Type[S] | None = None,
        echo: bool = False,
        **kwargs: Any,
    ) -> Union[str, S]:
        """
        Execute a task.

        Args:
            template (str | None): A path to a prompt template file or a prompt string
            response_model (Type[S] | None): A response model to return the response as
            echo (bool): Whether to echo the output
            **kwargs: Additional arguments to pass to the prompt formatter

        Returns:
            Union[str, S]: The response from the LLM
        """
        base_kwargs = dict[str, str | None](
            template=template,
            **kwargs,
        )

        if not response_model:
            return await self.ai_toolkit.chat(**base_kwargs)

        result = await self.ai_toolkit.asend(
            response_model=response_model,
            **base_kwargs,
        )
        if echo:
            logger.debug(result.content.model_dump_json(indent=2))
        return result.content

    def _create_task_node(
        self,
        template: str,
        uuid: str | None = None,
        response_model: Type[S] | None = None,
        echo: bool = False,
        **kwargs: Any,
    ) -> Node[Any]:
        """
        Creates a task node.

        Args:
            template (str): The template to use for the task node
            uuid (str | None): The UUID of the task node. Defaults to a <random UUID>_task_node.
            response_model (Type[S] | None): The response model to return the response as
            echo (bool): Whether to echo the output
            **kwargs: Additional arguments to pass to the task node.

        Returns:
            Node[Any]: The task node
        """
        return Node[response_model](
            uuid=uuid or "task_node_" + uuid4().hex,
            coroutine=self.task,
            kwargs=dict(
                template=template,
                response_model=response_model,
                echo=echo,
                **kwargs,
            ),
        )

    def _ensure_source_node_output(self, node: Node[T]) -> T:
        if not node.output:
            raise self.ErrorClass(
                message="Source node output is None",
            )
        if not isinstance(node.output, BaseModel):
            raise self.ErrorClass(
                message=f"Source node output expected to be a BaseModel, but got {type(node.output).__name__}",
            )
        return node.output

    def _ensure_validation_node_output(self, node: Node[bool]) -> bool:
        if not isinstance(node.output, bool):
            raise self.ErrorClass(
                message="Validation node output is not a bool",
            )
        return node.output

    async def _redirect(
        self,
        task_node: Node[S],
        validation_node: Node[bool],
        config: ValidationConfig,
    ):
        """
        Redirects the flow of the workflow based on the validation node output.

        Args:
            source_node (Node[S]): The source node.
            validation_subtree (TreeExecutor[V]): The validation subtree.
        """
        await validation_node.redirect([])

        source_output = self._ensure_source_node_output(task_node)
        is_valid = self._ensure_validation_node_output(validation_node)

        if config.max_retries == 0 or is_valid:
            return

        self.current_retries += 1
        if self.current_retries > config.max_retries:
            raise self.ErrorClass(
                message="Max retries reached.",
            )

        task_node.kwargs["__evaluations__"] = f"""
        ## Output
        {source_output.model_dump_json(indent=2)}

        ## Failure Reasonings
        {self.failure_reasonings}
        """
        await validation_node.redirect([task_node])

    def _create_issue_node(
        self,
        issue: str,
        task_node: Node[Any],
        echo: bool = False,
    ) -> Node[V]:
        """
        Creates an issue node with a custom-generated response model.

        Args:
            issue (str): The issue to validate against
            task_node (Node[Any]): The task node

        Returns:
            Node[V]: The issue node
        """
        IssueModel = self.ai_toolkit.inject_types(BaseIssue, [], issue)
        issue_node = Node[IssueModel](
            uuid=issue,
            coroutine=self.task,
            kwargs=dict(
                response_model=IssueModel,
                input=task_node.kwargs,
                output=task_node.output,
                template="""
                    # Task
                    Evaluate the output with regards to the issue. Rules:
                    - The issue is the only dimension that matters - everything else is irrelevant to whether the output is valid or not
                    - Whether the output is factually correct is irrelevant to the issue

                    # Context
                    ## Inpute
                    {{ input }}

                    ## Output
                    {{ output }}
                """,
                echo=echo,
            ),
        )
        return issue_node

    async def _run_issue(
        self,
        issue: str,
        task_node: Node[Any],
        config: ValidationConfig,
        executor: IssueTreeExecutor[V] | None = None,
        echo: bool = False,
    ) -> bool:
        """
        Runs an issue subtree for a given issue.

        Args:
            issue (str): The issue to validate against
            task_node (Node[Any]): The task node
            config (ValidationConfig): Configuration for the issue
            executor (IssueTreeExecutor[V] | None): The executor for the issue
            echo (bool): Whether to echo the output

        Returns:
            bool: Whether the issue passed
        """
        if not executor:
            issue_nodes = []
            for _ in range(config.count):
                issue_node = self._create_issue_node(
                    issue=issue,
                    task_node=task_node,
                    echo=echo,
                )
                issue_nodes.append(issue_node)
            executor = IssueTreeExecutor[V](
                config=config,
                uuid=f"Issue: {issue}",
                roots=issue_nodes,
            )
        result = await executor.run_validation_round(echo=echo)
        self.failure_reasonings[issue] = (
            executor.failure_reasonings
        )  # ? NOTE: temporary, until we have a way to consolidate failure reasonings

        ############################
        # TODO: consolidate failure reasonings
        if result is False and (
            isinstance(config, ThresholdVotingValidationConfig)
            or isinstance(config, KAheadVotingValidationConfig)
        ):
            pass
        ############################
        if isinstance(config, KAheadVotingValidationConfig) and result is None:
            return await self._run_issue(
                issue=issue,
                task_node=task_node,
                config=config,
                executor=executor,
            )
        return result

    async def _run_validations(
        self,
        task_node: Node[Any],
        config: ValidationConfig,
        echo: bool = False,
    ) -> bool:
        """
        Runs issue subtress concurrently.

        Args:
            task_node (Node[Any]): The task node
            config (ValidationConfig): Configuration for the validation
            echo (bool): Whether to echo the output

        Returns:
            bool: Whether the issues passed
        """
        issue_nodes: list[Node[bool]] = []
        for issue in config.issues:
            issue_node = Node[bool](
                uuid=f"validation: {issue}",
                coroutine=self._run_issue,
                kwargs=dict(
                    issue=issue,
                    task_node=task_node,
                    config=config,
                    echo=echo,
                ),
            )
            issue_nodes.append(issue_node)
        executor = TreeExecutor[bool](
            uuid=f"{task_node.kwargs.get('response_model').__name__}_validations",
            roots=issue_nodes,
        )  # ? REASON: run all subtrees concurrently
        await executor.run()
        return all(bool(issue_node.output) for issue_node in issue_nodes)

    async def create_task_tree(
        self,
        template: str,
        response_model: Type[S],
        kwargs: dict[str, Any],
        config: ValidationConfig = SingleShotValidationConfig(),
        echo: bool = False,
    ) -> TreeExecutor[S | V]:
        """
        Creates a task executor.

        Args:
            template (str): The template to use for the task node
            response_model (Type[S]): The response model to return the response as
            kwargs (dict[str, Any]): The kwargs to pass to the task node
            config (ValidationConfig): Configuration for the validation
            echo (bool): Whether to echo the output

        Returns:
            TreeExecutor[S | V]: The task executor
        """
        task_node: Node[S] = self._create_task_node(
            template=template,
            response_model=response_model,
            echo=echo,
            **kwargs,
        )
        if config.issues:
            validation_node = Node[bool](
                uuid=f"{response_model.__name__}_validation_node",
                coroutine=self._run_validations,
                kwargs=dict(
                    task_node=task_node,
                    config=config,
                    echo=echo,
                ),
            )
            validation_node.on_after_run = (
                self._redirect,
                dict(
                    task_node=task_node,
                    validation_node=validation_node,
                    config=config,
                ),
            )

            await task_node.connect(validation_node)

        executor = TreeExecutor[S | V](
            uuid=f"{response_model.__name__}_tree",
            roots=[task_node],
        )
        self.executor = executor
        return executor

    async def build_task_node(
        self,
        uuid: str,
        template: str,
        response_model: Type[S],
        kwargs: dict[str, Any],
        config: ValidationConfig = SingleShotValidationConfig(),
    ) -> Node[S]:
        """
        Convenience method for creating a node that contains a subtree that runs a task and validates the output.
        """
        tree: TreeExecutor[S | V] = await self.create_task_tree(
            template=template,
            response_model=response_model,
            kwargs=kwargs,
            config=config,
        )
        return Node[S](
            uuid=uuid,
            coroutine=tree.run,
        )

    async def run(self, *_: Any, **__: Any) -> S | V:
        """
        Run the workflow.
        """
        if not self.executor:
            raise WorkflowError(message="Executor not initialized")
        return await self.executor.run()
