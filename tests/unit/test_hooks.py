import asyncio
from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest
from openai.types.chat import ChatCompletion
from pydantic import BaseModel as PydanticBaseModel

from py_ai_toolkit.adapters import Jinja2Adapter
from py_ai_toolkit.core.domain.schemas import (
    CompletionResponse,
    SingleShotValidationConfig,
)
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


def _new_toolkit(*, prompt_formatter=None):
    from py_ai_toolkit.core.toolkit import PyAIToolkit

    ait = PyAIToolkit.__new__(PyAIToolkit)
    if prompt_formatter is not None:
        ait.prompt_formatter = prompt_formatter
    return ait


@pytest.mark.asyncio
async def test_prepare_messages_fires_before_render_hook():
    ait = _new_toolkit(prompt_formatter=Jinja2Adapter())
    captured = []

    async def on_before(ctx: BeforeRenderContext):
        captured.append(ctx)

    hooks = Hooks(before_render=on_before)
    await ait._prepare_messages(
        template="{{ name }} hello",
        hooks=hooks,
        name="Alice",
    )
    assert len(captured) == 1
    assert captured[0].template == "{{ name }} hello"
    assert captured[0].kwargs["name"] == "Alice"


@pytest.mark.asyncio
async def test_prepare_messages_fires_after_render_hook():
    ait = _new_toolkit(prompt_formatter=Jinja2Adapter())
    captured = []

    async def on_after(ctx: AfterRenderContext):
        captured.append(ctx)

    hooks = Hooks(after_render=on_after)
    await ait._prepare_messages(
        template="{{ name }} hello",
        hooks=hooks,
        name="Alice",
    )
    assert len(captured) == 1
    assert captured[0].prompt == "Alice hello"


@pytest.mark.asyncio
async def test_prepare_messages_works_without_hooks():
    ait = _new_toolkit(prompt_formatter=Jinja2Adapter())
    messages = await ait._prepare_messages(template="plain prompt")
    assert messages == [{"role": "system", "content": "plain prompt"}]


def _new_toolkit_with_llm():
    from py_ai_toolkit.core.toolkit import PyAIToolkit

    ait = PyAIToolkit.__new__(PyAIToolkit)
    ait.prompt_formatter = Jinja2Adapter()
    ait.alternative_llm_clients = []

    mock_completion = create_autospec(ChatCompletion, instance=True)
    mock_response = CompletionResponse(completion=mock_completion, content="hello")
    ait.llm_client = AsyncMock()
    ait.llm_client.chat = AsyncMock(return_value=mock_response)
    ait.llm_client._model = "test-model"
    return ait, mock_response


@pytest.mark.asyncio
async def test_chat_fires_before_and_after_llm_hooks():
    ait, mock_response = _new_toolkit_with_llm()
    before_captured = []
    after_captured = []

    async def on_before(ctx: BeforeLLMCallContext):
        before_captured.append(ctx)

    async def on_after(ctx: AfterLLMCallContext):
        after_captured.append(ctx)

    hooks = Hooks(before_llm_call=on_before, after_llm_call=on_after)
    await ait.chat(template="hello", hooks=hooks)

    assert len(before_captured) == 1
    assert before_captured[0].model == "test-model"
    assert before_captured[0].response_model is None

    assert len(after_captured) == 1
    assert after_captured[0].response is mock_response
    assert after_captured[0].elapsed_ms >= 0


@pytest.mark.asyncio
async def test_asend_fires_before_and_after_llm_hooks():
    from pydantic import BaseModel

    class MyModel(BaseModel):
        value: str

    ait, _ = _new_toolkit_with_llm()
    mock_instance = MyModel(value="test")
    mock_completion = create_autospec(ChatCompletion, instance=True)
    mock_response = CompletionResponse(
        completion=mock_completion, content=mock_instance
    )
    ait.llm_client.asend = AsyncMock(return_value=mock_response)

    before_captured = []
    after_captured = []

    async def on_before(ctx: BeforeLLMCallContext):
        before_captured.append(ctx)

    async def on_after(ctx: AfterLLMCallContext):
        after_captured.append(ctx)

    hooks = Hooks(before_llm_call=on_before, after_llm_call=on_after)
    await ait.asend(response_model=MyModel, template="hello", hooks=hooks)

    assert len(before_captured) == 1
    assert before_captured[0].response_model is MyModel

    assert len(after_captured) == 1
    assert after_captured[0].elapsed_ms >= 0


@pytest.mark.asyncio
async def test_run_validations_fires_before_and_after_validation_hooks():
    from py_ai_toolkit.core.base import BaseWorkflow
    from py_ai_toolkit.core.domain.errors import WorkflowError

    ait, _ = _new_toolkit_with_llm()
    workflow = BaseWorkflow(ai_toolkit=ait, error_class=WorkflowError)

    before_captured = []
    after_captured = []

    async def on_before(ctx: BeforeValidationContext):
        before_captured.append(ctx)

    async def on_after(ctx: AfterValidationContext):
        after_captured.append(ctx)

    hooks = Hooks(before_validation=on_before, after_validation=on_after)
    workflow.hooks = hooks

    # Create a mock task_node with output
    mock_output = MagicMock(spec=PydanticBaseModel)
    mock_output.model_dump_json = MagicMock(return_value="{}")
    task_node = MagicMock()
    task_node.output = mock_output
    task_node.kwargs = {"response_model": type(mock_output)}

    config = SingleShotValidationConfig(issues=["Is it correct?"])

    # Mock _run_issue to return True (valid)
    workflow._run_issue = AsyncMock(return_value=True)

    await workflow._run_validations(
        task_node=task_node,
        config=config,
    )

    assert len(before_captured) == 1
    assert before_captured[0].config is config

    assert len(after_captured) == 1
    assert after_captured[0].is_valid is True
    assert after_captured[0].failure_reasons == []


@pytest.mark.asyncio
async def test_redirect_fires_on_retry_hook():
    from py_ai_toolkit.core.base import BaseWorkflow
    from py_ai_toolkit.core.domain.errors import WorkflowError
    from py_ai_toolkit.core.domain.schemas import SingleShotValidationConfig

    ait, _ = _new_toolkit_with_llm()
    workflow = BaseWorkflow(ai_toolkit=ait, error_class=WorkflowError)

    retry_captured = []

    async def on_retry(ctx: OnRetryContext):
        retry_captured.append(ctx)

    hooks = Hooks(on_retry=on_retry)
    workflow.hooks = hooks

    mock_output = MagicMock(spec=PydanticBaseModel)
    mock_output.model_dump_json = MagicMock(return_value="{}")

    task_node = MagicMock()
    task_node.output = mock_output
    task_node.kwargs = {}

    validation_node = MagicMock()
    validation_node.output = False  # failed validation
    validation_node.redirect = AsyncMock()

    config = SingleShotValidationConfig(issues=["check"], max_retries=3)

    await workflow._redirect(
        task_node=task_node,
        validation_node=validation_node,
        config=config,
    )

    assert len(retry_captured) == 1
    assert retry_captured[0].current_retry == 1
    assert retry_captured[0].max_retries == 3


def test_after_embed_context_is_frozen():
    from py_ai_toolkit.core.hooks import AfterEmbedContext
    from py_ai_toolkit.core.domain.schemas import EmbeddingUsage

    usage = EmbeddingUsage(prompt_tokens=10, total_tokens=10)
    ctx = AfterEmbedContext(
        embedding=[0.1, 0.2],
        model="text-embedding-3-small",
        usage=usage,
        elapsed_ms=50.0,
    )
    assert ctx.embedding == [0.1, 0.2]
    assert ctx.model == "text-embedding-3-small"
    assert ctx.usage.total_tokens == 10
    assert ctx.elapsed_ms == 50.0
    with pytest.raises(FrozenInstanceError):
        ctx.model = "other"


def test_hooks_has_after_embed():
    hooks = Hooks()
    assert hooks.after_embed is None

    async def my_hook(ctx):
        pass

    hooks = Hooks(after_embed=my_hook)
    assert hooks.after_embed is my_hook


@pytest.mark.asyncio
async def test_embed_fires_after_embed_hook():
    from py_ai_toolkit.core.hooks import AfterEmbedContext
    from py_ai_toolkit.core.domain.schemas import EmbeddingResponse, EmbeddingUsage

    ait, _ = _new_toolkit_with_llm()

    mock_usage = EmbeddingUsage(prompt_tokens=5, total_tokens=5)
    mock_embed_response = EmbeddingResponse(
        embedding=[0.1, 0.2, 0.3],
        usage=mock_usage,
    )
    ait.llm_client.embed = AsyncMock(return_value=mock_embed_response)
    ait.llm_client._embedding_model = "text-embedding-3-small"

    captured = []

    async def on_after_embed(ctx: AfterEmbedContext):
        captured.append(ctx)

    hooks = Hooks(after_embed=on_after_embed)
    result = await ait.embed("hello world", hooks=hooks)

    assert result == [0.1, 0.2, 0.3]
    assert len(captured) == 1
    assert captured[0].embedding == [0.1, 0.2, 0.3]
    assert captured[0].usage.total_tokens == 5
    assert captured[0].model == "text-embedding-3-small"
    assert captured[0].elapsed_ms >= 0


@pytest.mark.asyncio
async def test_embed_without_hooks_returns_embedding():
    from py_ai_toolkit.core.domain.schemas import EmbeddingResponse, EmbeddingUsage

    ait, _ = _new_toolkit_with_llm()

    mock_usage = EmbeddingUsage(prompt_tokens=5, total_tokens=5)
    mock_embed_response = EmbeddingResponse(
        embedding=[0.1, 0.2, 0.3],
        usage=mock_usage,
    )
    ait.llm_client.embed = AsyncMock(return_value=mock_embed_response)

    result = await ait.embed("hello world")
    assert result == [0.1, 0.2, 0.3]


def test_hooks_exported_from_package():
    from py_ai_toolkit import Hooks
    from py_ai_toolkit.core.hooks import (
        BeforeRenderContext,
    )

    assert Hooks is not None
    assert BeforeRenderContext is not None
