from typing import Annotated

import pytest
from pydantic import BaseModel, Field, ValidationError

from py_ai_toolkit import Tool, tool
from py_ai_toolkit.core.utils import _extract_description, _pascal_case


class TestExtractDescription:
    def test_empty_docstring(self):
        assert _extract_description(None) == ""
        assert _extract_description("") == ""

    def test_single_line(self):
        assert _extract_description("Search the web.") == "Search the web."

    def test_multiline_first_paragraph(self):
        docstring = """Search the web
        for information."""
        assert _extract_description(docstring) == "Search the web for information."

    def test_stops_at_blank_line(self):
        docstring = """Short description.

        Args:
            query: The search query.
        """
        assert _extract_description(docstring) == "Short description."


class TestPascalCase:
    def test_simple_name(self):
        assert _pascal_case("search") == "Search"

    def test_snake_case(self):
        assert _pascal_case("search_web") == "SearchWeb"

    def test_with_special_chars(self):
        assert _pascal_case("my-function_name") == "MyFunctionName"


class TestToolFactory:
    def test_typed_function_with_defaults(self):
        @tool
        def search(
            query: Annotated[str, Field(description="Search query")],
            max_results: Annotated[int, Field(description="Max results")] = 10,
        ) -> list[str]:
            """Search the web."""
            return []

        assert isinstance(search, Tool)
        assert search.name == "search"
        assert search.description == "Search the web."
        assert search.parameters.__name__ == "SearchParams"

        schema = search.schema
        assert schema["properties"]["query"]["description"] == "Search query"
        assert schema["properties"]["max_results"]["description"] == "Max results"
        assert schema["properties"]["max_results"]["default"] == 10
        assert "query" in schema["required"]
        assert "max_results" not in schema["required"]

    def test_no_docstring(self):
        @tool
        def simple(x: int) -> int:
            return x * 2

        assert simple.name == "simple"
        assert simple.description == ""
        assert "x" in simple.schema["properties"]

    def test_no_type_hints(self):
        @tool
        def untyped(a, b=5):
            """Do something."""
            return a + b

        assert untyped.name == "untyped"
        schema = untyped.schema
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]
        assert schema["properties"]["b"]["default"] == 5

    def test_decorator_usage(self):
        def my_func(x: str) -> str:
            """A function."""
            return x

        wrapped = tool(my_func)
        assert isinstance(wrapped, Tool)
        assert wrapped.name == "my_func"

    def test_preserves_fn_reference(self):
        def original(x: int) -> int:
            return x

        t = tool(original)
        assert t.fn is original

    def test_annotated_with_description(self):
        @tool
        def fetch(url: Annotated[str, Field(description="The URL to fetch")]) -> str:
            """Fetch a URL."""
            return ""

        schema = fetch.schema
        assert schema["properties"]["url"]["description"] == "The URL to fetch"

    def test_annotated_without_field(self):
        @tool
        def process(data: Annotated[str, "some metadata"]) -> str:
            """Process data."""
            return data

        schema = process.schema
        assert "data" in schema["properties"]
        assert "data" in schema["required"]

    def test_skips_self_args_kwargs(self):
        @tool
        def method(self, x: int, *args, **kwargs) -> int:
            return x

        schema = method.schema
        assert "self" not in schema["properties"]
        assert "args" not in schema["properties"]
        assert "kwargs" not in schema["properties"]
        assert "x" in schema["properties"]

    def test_keyword_only_params(self):
        @tool
        def kw_only(
            a: int,
            *,
            b: Annotated[str, Field(description="B param")],
            c: float = 1.0,
        ) -> None:
            """Function with keyword-only params."""
            pass

        schema = kw_only.schema
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]
        assert "c" in schema["properties"]
        assert schema["properties"]["c"]["default"] == 1.0

    def test_idempotent(self):
        @tool
        def fn(x: int) -> int:
            return x

        assert tool(fn) is fn


class TestToolClass:
    def test_schema_structure(self):
        @tool
        def example(
            required_param: Annotated[str, Field(description="A required string")],
            optional_param: Annotated[
                int, Field(description="An optional integer")
            ] = 42,
        ) -> str:
            """Example function."""
            return ""

        schema = example.schema
        assert schema["type"] == "object"
        assert "required_param" in schema["properties"]
        assert "optional_param" in schema["properties"]
        assert (
            schema["properties"]["required_param"]["description"] == "A required string"
        )
        assert (
            schema["properties"]["optional_param"]["description"]
            == "An optional integer"
        )
        assert schema["properties"]["optional_param"]["default"] == 42
        assert "required_param" in schema["required"]
        assert "optional_param" not in schema["required"]

    @pytest.mark.asyncio
    async def test_sync_execution(self):
        @tool
        def add(a: int, b: int) -> int:
            return a + b

        result = await add.execute(a=2, b=3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_async_execution(self):
        @tool
        async def async_add(a: int, b: int) -> int:
            return a + b

        result = await async_add.execute(a=2, b=3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_validation_error_on_bad_input(self):
        @tool
        def typed_fn(x: int) -> int:
            return x

        with pytest.raises(ValidationError):
            await typed_fn.execute(x="not_an_int")

    @pytest.mark.asyncio
    async def test_validation_error_missing_required(self):
        @tool
        def requires_param(x: int) -> int:
            return x

        with pytest.raises(ValidationError):
            await requires_param.execute()

    def test_repr(self):
        @tool
        def my_tool(x: int) -> int:
            return x

        assert repr(my_tool) == "Tool(name='my_tool')"

    def test_default_none(self):
        @tool
        def with_none(x: str | None = None) -> str:
            return x or "default"

        schema = with_none.schema
        assert schema["properties"]["x"]["default"] is None
        assert "x" not in schema.get("required", [])


class TestBaseModelParameters:
    def test_single_basemodel_param_uses_model_directly(self):
        class SearchParams(BaseModel):
            query: str
            limit: int = 10

        @tool
        def search(params: SearchParams) -> str:
            return params.query

        assert search.parameters is SearchParams
        schema = search.schema
        assert "query" in schema["properties"]
        assert "limit" in schema["properties"]
        assert "params" not in schema["properties"]

    def test_single_basemodel_uses_model_docstring_if_no_fn_docstring(self):
        class SearchParams(BaseModel):
            """Search parameters for the API."""

            query: str

        @tool
        def search(params: SearchParams) -> str:
            return params.query

        assert search.description == "Search parameters for the API."

    def test_single_basemodel_prefers_fn_docstring(self):
        class SearchParams(BaseModel):
            """Model docstring."""

            query: str

        @tool
        def search(params: SearchParams) -> str:
            """Function docstring."""
            return params.query

        assert search.description == "Function docstring."

    @pytest.mark.asyncio
    async def test_single_basemodel_receives_instance(self):
        class SearchParams(BaseModel):
            query: str
            limit: int = 10

        received_type = None

        @tool
        def search(params: SearchParams) -> str:
            nonlocal received_type
            received_type = type(params)
            return params.query

        result = await search.execute(query="test", limit=5)
        assert result == "test"
        assert received_type is SearchParams

    def test_multiple_params_with_basemodel(self):
        class Options(BaseModel):
            verbose: bool = False

        @tool
        def process(data: str, options: Options) -> str:
            return data

        schema = process.schema
        assert "data" in schema["properties"]
        assert "options" in schema["properties"]

    @pytest.mark.asyncio
    async def test_multiple_params_basemodel_receives_instance(self):
        class Options(BaseModel):
            verbose: bool = False
            limit: int = 10

        received_options_type = None

        @tool
        def process(data: str, options: Options) -> str:
            nonlocal received_options_type
            received_options_type = type(options)
            return f"{data}-{options.verbose}-{options.limit}"

        result = await process.execute(
            data="hello", options={"verbose": True, "limit": 5}
        )
        assert result == "hello-True-5"
        assert received_options_type is Options

    def test_single_annotated_basemodel_param(self):
        class Params(BaseModel):
            value: int

        @tool
        def fn(p: Annotated[Params, Field(description="The params")]) -> int:
            return p.value

        assert fn.parameters is Params

    @pytest.mark.asyncio
    async def test_nested_basemodel_in_params(self):
        class Inner(BaseModel):
            x: int

        class Outer(BaseModel):
            inner: Inner
            name: str

        @tool
        def fn(params: Outer) -> int:
            return params.inner.x

        result = await fn.execute(inner={"x": 42}, name="test")
        assert result == 42
