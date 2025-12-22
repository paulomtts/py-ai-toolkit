from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModellerPort(ABC):
    """
    Abstract base class for model operations.
    """

    @abstractmethod
    def inject_types(
        self,
        model: Type[T],
        fields: list[tuple[str, Any]],
    ) -> Type[T]:
        """
        Injects field types into a model.
        """
        pass

    @abstractmethod
    def reduce_model_schema(
        self, model: Type[T], include_description: bool = True
    ) -> str:
        """
        Reduces the model schema into version with less tokens. Helpful for reducing prompt noise.
        """
        pass
