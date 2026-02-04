import asyncio
import inspect
from typing import Annotated, Any, Callable, Type, get_args, get_origin, get_type_hints

from pydantic import BaseModel, Field, create_model
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from py_ai_toolkit.core.utils import (
    _extract_description,
    _is_basemodel_subclass,
    _pascal_case,
    _unwrap_annotated,
)


class Tool:
    __slots__ = (
        "name",
        "description",
        "parameters",
        "fn",
        "_param_types",
        "_single_model_param",
    )

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Type[BaseModel],
        fn: Callable[..., Any],
        param_types: dict[str, Any],
        single_model_param: str | None = None,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.fn = fn
        self._param_types = param_types
        self._single_model_param = single_model_param

    @property
    def schema(self) -> dict[str, Any]:
        return self.parameters.model_json_schema()

    async def execute(self, **kwargs: Any) -> Any:
        validated = self.parameters(**kwargs)

        if self._single_model_param:
            call_kwargs = {self._single_model_param: validated}
        else:
            call_kwargs = {}
            for param_name, value in validated.model_dump().items():
                param_type = self._param_types.get(param_name)
                if (
                    param_type is not None
                    and _is_basemodel_subclass(param_type)
                    and isinstance(value, dict)
                ):
                    call_kwargs[param_name] = param_type(**value)
                else:
                    call_kwargs[param_name] = value

        if asyncio.iscoroutinefunction(self.fn):
            return await self.fn(**call_kwargs)
        return self.fn(**call_kwargs)

    def __repr__(self) -> str:
        return f"Tool(name={self.name!r})"


def tool(fn: Callable[..., Any] | Tool) -> Tool:
    if isinstance(fn, Tool):
        return fn

    description = _extract_description(fn.__doc__)

    sig = inspect.signature(fn)
    try:
        hints = get_type_hints(fn, include_extras=True)
    except Exception:
        hints = {}

    skip_params = {"self", "cls"}
    param_items: list[tuple[str, inspect.Parameter]] = [
        (name, param)
        for name, param in sig.parameters.items()
        if name not in skip_params
        and param.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    ]

    if len(param_items) == 1:
        param_name, param = param_items[0]
        hint = hints.get(param_name, Any)
        base_type = _unwrap_annotated(hint)
        if _is_basemodel_subclass(base_type):
            return Tool(
                name=fn.__name__,
                description=description or _extract_description(base_type.__doc__),
                parameters=base_type,
                fn=fn,
                param_types={param_name: base_type},
                single_model_param=param_name,
            )

    fields: dict[str, Any] = {}
    param_types: dict[str, Any] = {}

    for param_name, param in param_items:
        hint = hints.get(param_name, Any)
        default = param.default if param.default is not inspect.Parameter.empty else ...

        origin = get_origin(hint)
        if origin is Annotated:
            args = get_args(hint)
            base_type = args[0]
            field_info = next(
                (arg for arg in args[1:] if isinstance(arg, FieldInfo)), None
            )

            if field_info is not None:
                field_has_no_default = (
                    field_info.default is PydanticUndefined
                    and field_info.default_factory is None
                )
                if field_has_no_default and default is not ...:
                    field_info = Field(
                        default=default, description=field_info.description
                    )
                fields[param_name] = (base_type, field_info)
            else:
                fields[param_name] = (base_type, Field(default=default))
            param_types[param_name] = base_type
            continue

        fields[param_name] = (hint, Field(default=default))
        param_types[param_name] = hint

    model_name = _pascal_case(fn.__name__) + "Params"
    parameters_model = create_model(model_name, __doc__=description or None, **fields)

    return Tool(
        name=fn.__name__,
        description=description,
        parameters=parameters_model,
        fn=fn,
        param_types=param_types,
    )
