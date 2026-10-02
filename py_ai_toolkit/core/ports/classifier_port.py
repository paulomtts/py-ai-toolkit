from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from py_ai_toolkit.core.domain.classifier import ClassifierResponse, Question


class ClassifierPort(ABC):
    """
    Abstract base class for classifier ports.
    """

    @abstractmethod
    async def classify(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: Mapping[str, Question],
    ) -> ClassifierResponse:
        """
        Answers structured questions about a state.

        Args:
            state (str | dict[str, Any] | list[Any]): The state to classify
            questions (Mapping[str, Question]): The questions to answer, by name

        Returns:
            ClassifierResponse: The answers from the classifier
        """

    async def aclose(self) -> None:
        """Release network resources. Default: no-op."""
