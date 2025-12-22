import re
from typing import Any, Type, TypeVar

from pydantic import BaseModel, Field, create_model
from pydantic_core import PydanticUndefined

from py_ai_toolkit.core.ports import ModellerPort

T = TypeVar("T", bound=BaseModel)


class PydanticAdapter(ModellerPort):
    """
    Service for creating Pydantic models from schemas.
    """

    def _normalize(self, text: str) -> str:
        """
        Normalizes the text to a valid Pydantic model field name.
        """
        return re.sub(r"[^a-zA-Z0-9_]", "", text)

    def _pascal_case(self, string: str) -> str:
        """
        Converts a string to pascal case.
        """
        normalized = re.sub(r"[^a-zA-Z0-9\s]", " ", string).strip()
        return "".join(word.capitalize() for word in normalized.split())

    def inject_types(
        self,
        model: Type[T],
        fields: list[tuple[str, Any]],
    ) -> Type[T]:
        """
        Injects field types into a model.
        """
        return create_model(
            model.__name__ + "Model",
            __base__=(model,),
            __doc__=model.__doc__,
            **{
                field_name: (
                    field_type,
                    Field(
                        description=model.model_fields[field_name].description,
                        examples=model.model_fields[field_name].examples,
                    ),
                )
                for (field_name, field_type) in fields
            },  # type: ignore
        )

    def reduce_model_schema(
        self, model: Type[T], include_description: bool = True
    ) -> str:
        """
        Reduces the model schema into version with less tokens. Helpful for reducing prompt noise.
        """
        reduced_schema = []
        for field, info in model.model_fields.items():
            reduced_schema.append(
                f"{field}({info.annotation}"
                + (
                    f", default={info.default})"
                    if info.default is not PydanticUndefined
                    else ")"
                )
                + (f": {info.description}" if include_description else "")
            )
        return "\n".join(reduced_schema)
