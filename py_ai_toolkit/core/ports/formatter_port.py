from abc import ABC, abstractmethod
from typing import Optional, Any


class FormatterPort(ABC):
    """Base class for LLM models."""

    @abstractmethod
    def render(self, path: str, input: Optional[dict[str, Any]] = None) -> str:
        """
        Render a template with variables.
        """
        pass
