from typing import Literal

import pytest
from pydantic import BaseModel, Field

import py_ai_toolkit.core.tools as tools_mod
from py_ai_toolkit.adapters import Jinja2Adapter, PydanticAdapter
from py_ai_toolkit.core.tools import PyAIToolkit


class DemoModel(BaseModel):
    a: int


class OtherModel(BaseModel):
    b: int


def _new_toolkit(*, model_handler=None, prompt_formatter=None) -> PyAIToolkit:
    # Avoid calling __init__ (which wires real clients via factories)
    ait = PyAIToolkit.__new__(PyAIToolkit)
    if model_handler is not None:
        ait.model_handler = model_handler
    if prompt_formatter is not None:
        ait.prompt_formatter = prompt_formatter
    return ait


def test_inject_types_updates_field_type_and_preserves_metadata():
    class Fruit(BaseModel):
        name: str = Field(description="Fruit name", examples=["apple"])

    ait = _new_toolkit(model_handler=PydanticAdapter())

    Injected = ait.inject_types(Fruit, [("name", Literal["apple", "banana"])])

    assert Injected.__name__ == "FruitModel"
    assert issubclass(Injected, Fruit)
    assert Injected.model_fields["name"].annotation == Literal["apple", "banana"]
    assert Injected.model_fields["name"].description == "Fruit name"
    assert Injected.model_fields["name"].examples == ["apple"]


def test_reduce_model_schema_matches_pydantic_adapter_output():
    class Order(BaseModel):
        item: str = Field(description="Item name")
        qty: int = Field(default=5, description="Quantity")

    ait = _new_toolkit(model_handler=PydanticAdapter())

    assert (
        ait.reduce_model_schema(Order, include_description=True)
        == "item(<class 'str'>): Item name\nqty(<class 'int'>, default=5): Quantity"
    )
    assert (
        ait.reduce_model_schema(Order, include_description=False)
        == "item(<class 'str'>)\nqty(<class 'int'>, default=5)"
    )


def test_prepare_messages_renders_prompt_template_with_kwargs(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_encode(x):
        return f"ENC({x})"

    monkeypatch.setattr(tools_mod, "encode", fake_encode)
    ait = _new_toolkit(prompt_formatter=Jinja2Adapter())

    demo = DemoModel(a=1)
    demo_list = [DemoModel(a=2), DemoModel(a=3)]

    messages = ait._prepare_messages(
        template="{{ message }}; S={{ single }}; M={{ many }}",
        message="MY_MESSAGE",
        single=demo,
        many=demo_list,
    )

    expected_single = f"ENC({demo.model_dump_json()})"
    expected_many = f"ENC({[m.model_dump_json() for m in demo_list]})"
    expected_content = f"MY_MESSAGE; S={expected_single}; M={expected_many}"

    assert messages == [{"role": "system", "content": expected_content}]


def test_prepare_messages_renders_prompt_with_encoded_kwargs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    def fake_encode(x):
        return f"ENC({x})"

    monkeypatch.setattr(tools_mod, "encode", fake_encode)
    ait = _new_toolkit(prompt_formatter=Jinja2Adapter())

    demo = DemoModel(a=10)
    demo_list = [DemoModel(a=20), DemoModel(a=30)]

    # real Jinja2Adapter reads a file, so create a real template
    template_path = tmp_path / "template.md"
    template_path.write_text(
        "S={{ single }}; M={{ many }}; P={{ primitive }}; E={{ empty }}",
        encoding="utf-8",
    )

    messages = ait._prepare_messages(
        template=str(template_path),
        single=demo,
        many=demo_list,
        empty=[],
        primitive=123,
    )

    expected_single = f"ENC({demo.model_dump_json()})"
    expected_many = f"ENC({[m.model_dump_json() for m in demo_list]})"
    expected_content = f"S={expected_single}; M={expected_many}; P=123; E=[]"

    assert messages == [{"role": "system", "content": expected_content}]
