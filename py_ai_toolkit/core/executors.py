from typing import TypeVar

from grafo import TreeExecutor

from py_ai_toolkit.core.domain.schemas import ValidationConfig
from py_ai_toolkit.core.domain.models import BaseIssue
from py_ai_toolkit.core.utils import logger

V = TypeVar("V", bound=BaseIssue)


class IssueTreeExecutor(TreeExecutor[V]):
    def __init__(self, config: ValidationConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.successes: int = 0
        self.failures: int = 0
        self.failure_reasonings: list[str] = []
        self.round_number: int = 0

    async def run_validation_round(
        self,
        echo: bool = False,
    ) -> bool | None:
        """
        Executes a round of issue validation for all leaf nodes in the tree.

        This method runs the tree executor to evaluate all issue nodes corresponding to a
        validation round. It aggregates the number of successes and failures by inspecting
        each leaf node's output (expecting an "is_valid" attribute). The function also
        collects failure reasonings for reporting or further decision making.

        Returns:
            bool | None:
                - True if the number of additional successes over failures meets or exceeds
                  the `required_ahead` threshold.
                - False if the number of additional failures over successes meets or exceeds
                  the `required_ahead` threshold.
                - None if neither threshold has been met, indicating that further rounds
                  are needed or a decision cannot be made yet.
        """
        self.round_number += 1
        nodes = await self.run()
        self.successes += sum(int(node.output.is_valid) for node in nodes)
        self.failures += sum(int(not node.output.is_valid) for node in nodes)
        self.failure_reasonings.extend(
            [node.output.reasoning for node in nodes if not node.output.is_valid]
        )
        if self.successes - self.failures >= self.config.required_ahead:
            if echo:
                logger.debug(
                    f"Round {self.round_number} Succeeded, successes: {self.successes}, failures: {self.failures}"
                )
            return True
        elif self.failures - self.successes >= self.config.required_ahead:
            if echo:
                logger.debug(
                    f"Round {self.round_number} Failed, successes: {self.successes}, failures: {self.failures}"
                )
            return False
        else:
            return None
