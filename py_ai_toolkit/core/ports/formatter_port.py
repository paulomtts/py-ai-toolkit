from abc import ABC, abstractmethod
from typing import Any, Optional


class FormatterPort(ABC):
    """Base class for LLM models."""

    @abstractmethod
    def render(
        self,
        path: str | None = None,
        prompt: str | None = None,
        input: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Render a template with variables.
        """
        pass
