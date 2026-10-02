from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModellerPort(ABC):
    """
    Abstract base class for model operations.
    """

    @abstractmethod
    def inject_types(
        self,
        model: type[T],
        fields: list[tuple[str, Any]],
        docstring: str | None = None,
    ) -> type[T]:
        """
        Injects field types into a model.
        """

    @abstractmethod
    def reduce_model_schema(
        self, model: type[T], include_description: bool = True
    ) -> str:
        """
        Reduces the model schema into version with less tokens. Helpful for reducing prompt noise.
        """
