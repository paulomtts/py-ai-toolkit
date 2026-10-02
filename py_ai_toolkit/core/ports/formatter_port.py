from abc import ABC, abstractmethod
from typing import Any


class FormatterPort(ABC):
    """Base class for LLM models."""

    @abstractmethod
    def render(
        self,
        path: str | None = None,
        prompt: str | None = None,
        input: dict[str, Any] | None = None,
    ) -> str:
        """
        Render a template with variables.
        """
