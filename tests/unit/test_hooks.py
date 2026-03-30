import asyncio
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from py_ai_toolkit.core.hooks import (
    AfterLLMCallContext,
    AfterRenderContext,
    AfterValidationContext,
    BeforeLLMCallContext,
    BeforeRenderContext,
    BeforeValidationContext,
    Hooks,
    OnRetryContext,
    _fire_hook,
)


def test_before_render_context_is_frozen():
    ctx = BeforeRenderContext(template="prompt.md", kwargs={"name": "John"})
    assert ctx.template == "prompt.md"
    assert ctx.kwargs == {"name": "John"}
    with pytest.raises(FrozenInstanceError):
        ctx.template = "other.md"


def test_after_render_context_is_frozen():
    ctx = AfterRenderContext(prompt="Hello John")
    assert ctx.prompt == "Hello John"
    with pytest.raises(FrozenInstanceError):
        ctx.prompt = "other"


def test_before_llm_call_context_is_frozen():
    ctx = BeforeLLMCallContext(
        messages=[{"role": "system", "content": "hi"}],
        model="gpt-4",
        response_model=None,
    )
    assert ctx.model == "gpt-4"
    assert ctx.response_model is None
    with pytest.raises(FrozenInstanceError):
        ctx.model = "other"


def test_after_llm_call_context_is_frozen():
    ctx = AfterLLMCallContext(response=None, model="gpt-4", elapsed_ms=123.4)
    assert ctx.elapsed_ms == 123.4
    with pytest.raises(FrozenInstanceError):
        ctx.elapsed_ms = 0.0


def test_before_validation_context_is_frozen():
    ctx = BeforeValidationContext(output=None, config=None)
    with pytest.raises(FrozenInstanceError):
        ctx.output = "x"


def test_after_validation_context_is_frozen():
    ctx = AfterValidationContext(is_valid=True, failure_reasons=[])
    assert ctx.is_valid is True
    with pytest.raises(FrozenInstanceError):
        ctx.is_valid = False


def test_on_retry_context_is_frozen():
    ctx = OnRetryContext(current_retry=1, max_retries=3, evaluations="feedback")
    assert ctx.current_retry == 1
    with pytest.raises(FrozenInstanceError):
        ctx.current_retry = 2


def test_hooks_defaults_to_none():
    hooks = Hooks()
    assert hooks.before_render is None
    assert hooks.after_render is None
    assert hooks.before_llm_call is None
    assert hooks.after_llm_call is None
    assert hooks.before_validation is None
    assert hooks.after_validation is None
    assert hooks.on_retry is None


def test_hooks_accepts_callbacks():
    async def my_hook(ctx):
        pass

    hooks = Hooks(before_render=my_hook, after_llm_call=my_hook)
    assert hooks.before_render is my_hook
    assert hooks.after_llm_call is my_hook
    assert hooks.after_render is None


def test_fire_hook_calls_callback():
    called_with = []

    async def my_hook(ctx):
        called_with.append(ctx)

    ctx = AfterRenderContext(prompt="hello")
    asyncio.get_event_loop().run_until_complete(_fire_hook(my_hook, ctx))
    assert called_with == [ctx]


def test_fire_hook_skips_none():
    # Should not raise
    asyncio.get_event_loop().run_until_complete(_fire_hook(None, "anything"))
