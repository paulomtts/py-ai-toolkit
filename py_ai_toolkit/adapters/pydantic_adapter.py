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

    def _extract_field_kwargs(self, field_info: Any) -> dict[str, Any]:
        """
        Extracts all kwargs from a FieldInfo object that can be passed to Field().
        """
        deprecated_fields = {"metadata", "metadata_lookup"}
        kwargs = {}
        field_dict = vars(field_info) if hasattr(field_info, "__dict__") else {}
        seen_attrs = set(field_dict.keys())
        for attr_name, attr_value in field_dict.items():
            if attr_name.startswith("_") or attr_name in deprecated_fields:
                continue
            if attr_value is None or attr_value is PydanticUndefined:
                continue
            if not callable(attr_value):
                kwargs[attr_name] = attr_value
        for attr_name in dir(field_info):
            if (
                attr_name.startswith("_")
                or attr_name in seen_attrs
                or attr_name in deprecated_fields
            ):
                continue
            try:
                attr_value = getattr(field_info, attr_name)
                if (
                    not callable(attr_value)
                    and attr_value is not None
                    and attr_value is not PydanticUndefined
                ):
                    kwargs[attr_name] = attr_value
            except (AttributeError, TypeError):
                continue
        return kwargs

    def inject_types(
        self,
        model: Type[T],
        fields: list[tuple[str, Any]],
        docstring: str | None = None,
    ) -> Type[T]:
        """
        Injects field types into a model.
        """
        return create_model(
            model.__name__ + "Model",
            __base__=(model,),
            __doc__=docstring or model.__doc__,
            **{
                field_name: (
                    field_type,
                    Field(**self._extract_field_kwargs(model.model_fields[field_name])),
                )
                for field_name, field_type in fields
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
