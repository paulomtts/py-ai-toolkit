# Hook System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add passive observation hooks to py-ai-toolkit's public API for token tracking, latency monitoring, and pipeline visibility.

**Architecture:** A new `py_ai_toolkit/core/hooks.py` module defines frozen context dataclasses, callback type aliases, and a `Hooks` container. The `hooks: Hooks | None = None` parameter is added to `chat()`, `stream()`, `asend()`, and `run_task()`. Hooks are fired inline via a `_fire_hook()` helper. `_prepare_messages()` becomes async to support hook firing.

**Tech Stack:** Python dataclasses, typing (Callable, Awaitable), pydantic BaseModel (for type refs in contexts), time module for elapsed_ms.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `py_ai_toolkit/core/hooks.py` | Create | Context dataclasses, callback types, `Hooks` container, `_fire_hook()` helper |
| `py_ai_toolkit/__init__.py` | Modify | Export `Hooks` and all context types |
| `py_ai_toolkit/core/toolkit.py` | Modify | Add `hooks` param to `chat/stream/asend/run_task`, fire render and LLM hooks, make `_prepare_messages` async |
| `py_ai_toolkit/core/base.py` | Modify | Accept and fire validation/retry hooks in `_redirect()` and `_run_validations()` |
| `tests/unit/test_hooks.py` | Create | All hook tests |
| `tests/unit/test_tools.py` | Modify | Update `_prepare_messages` calls for async |

---

### Task 1: Create hooks module with context dataclasses and Hooks container

**Files:**
- Create: `py_ai_toolkit/core/hooks.py`
- Test: `tests/unit/test_hooks.py`

- [ ] **Step 1: Write failing tests for hook types**

```python
# tests/unit/test_hooks.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_hooks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'py_ai_toolkit.core.hooks'`

- [ ] **Step 3: Implement hooks module**

```python
# py_ai_toolkit/core/hooks.py
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Type

from pydantic import BaseModel

from py_ai_toolkit.core.domain.schemas import CompletionResponse, ValidationConfig


@dataclass(frozen=True)
class BeforeRenderContext:
    template: str | None
    kwargs: dict[str, Any]


@dataclass(frozen=True)
class AfterRenderContext:
    prompt: str


@dataclass(frozen=True)
class BeforeLLMCallContext:
    messages: list[dict[str, str]]
    model: str
    response_model: Type | None


@dataclass(frozen=True)
class AfterLLMCallContext:
    response: CompletionResponse
    model: str
    elapsed_ms: float


@dataclass(frozen=True)
class BeforeValidationContext:
    output: BaseModel
    config: ValidationConfig


@dataclass(frozen=True)
class AfterValidationContext:
    is_valid: bool
    failure_reasons: list[str]


@dataclass(frozen=True)
class OnRetryContext:
    current_retry: int
    max_retries: int
    evaluations: str


BeforeRenderHook = Callable[[BeforeRenderContext], Awaitable[None]]
AfterRenderHook = Callable[[AfterRenderContext], Awaitable[None]]
BeforeLLMCallHook = Callable[[BeforeLLMCallContext], Awaitable[None]]
AfterLLMCallHook = Callable[[AfterLLMCallContext], Awaitable[None]]
BeforeValidationHook = Callable[[BeforeValidationContext], Awaitable[None]]
AfterValidationHook = Callable[[AfterValidationContext], Awaitable[None]]
OnRetryHook = Callable[[OnRetryContext], Awaitable[None]]


@dataclass
class Hooks:
    before_render: BeforeRenderHook | None = None
    after_render: AfterRenderHook | None = None
    before_llm_call: BeforeLLMCallHook | None = None
    after_llm_call: AfterLLMCallHook | None = None
    before_validation: BeforeValidationHook | None = None
    after_validation: AfterValidationHook | None = None
    on_retry: OnRetryHook | None = None


async def _fire_hook(hook: Callable | None, ctx: Any) -> None:
    if hook is not None:
        await hook(ctx)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_hooks.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add py_ai_toolkit/core/hooks.py tests/unit/test_hooks.py
git commit -m "feat: add hooks module with context dataclasses and Hooks container"
```

---

### Task 2: Wire render hooks into _prepare_messages (make it async)

**Files:**
- Modify: `py_ai_toolkit/core/toolkit.py:88-122` (`_prepare_messages`)
- Modify: `py_ai_toolkit/core/toolkit.py:130-146` (`chat`)
- Modify: `py_ai_toolkit/core/toolkit.py:148-165` (`stream`)
- Modify: `py_ai_toolkit/core/toolkit.py:167-196` (`asend`)
- Test: `tests/unit/test_hooks.py`
- Modify: `tests/unit/test_tools.py:59-103` (update `_prepare_messages` calls to async)

- [ ] **Step 1: Write failing tests for render hooks**

Append to `tests/unit/test_hooks.py`:

```python
from unittest.mock import AsyncMock

from py_ai_toolkit.adapters import Jinja2Adapter
from py_ai_toolkit.core.hooks import (
    BeforeRenderContext,
    AfterRenderContext,
    Hooks,
)


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
    ait._prepare_messages(
        template="{{ name }} hello",
        hooks=hooks,
        name="Alice",
    )
    # _prepare_messages is sync but we need it async for hooks
    # This test will guide us to make it async
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_hooks.py::test_prepare_messages_fires_before_render_hook tests/unit/test_hooks.py::test_prepare_messages_fires_after_render_hook tests/unit/test_hooks.py::test_prepare_messages_works_without_hooks -v`
Expected: FAIL — `_prepare_messages` is not async and doesn't accept `hooks`

- [ ] **Step 3: Make _prepare_messages async and add hook firing**

In `py_ai_toolkit/core/toolkit.py`, add import at top:

```python
from py_ai_toolkit.core.hooks import Hooks, _fire_hook, BeforeRenderContext, AfterRenderContext
```

Change `_prepare_messages` (line 88) from:

```python
def _prepare_messages(self, template: str | None = None, **kwargs: Any) -> list:
```

to:

```python
async def _prepare_messages(self, template: str | None = None, hooks: Hooks | None = None, **kwargs: Any) -> list:
```

Add hook firing around the render call. After the `kwargs` loop (line 102) and before `final_prompt = ...` (line 104), add:

```python
        if hooks:
            await _fire_hook(
                hooks.before_render,
                BeforeRenderContext(template=template, kwargs=kwargs),
            )
```

After `final_prompt = self.prompt_formatter.render(...)` (line 108), add:

```python
        if hooks:
            await _fire_hook(
                hooks.after_render,
                AfterRenderContext(prompt=final_prompt),
            )
```

- [ ] **Step 4: Update all callers of _prepare_messages to await it**

In `py_ai_toolkit/core/toolkit.py`:

`chat()` line 145: change `messages = self._prepare_messages(template, **kwargs)` to:
```python
messages = await self._prepare_messages(template, **kwargs)
```

`stream()` line 163: change `messages = self._prepare_messages(template, **kwargs)` to:
```python
messages = await self._prepare_messages(template, **kwargs)
```

`asend()` line 187: change `messages = self._prepare_messages(template, **kwargs)` to:
```python
messages = await self._prepare_messages(template, **kwargs)
```

In `tests/unit/test_tools.py`, update the two `_prepare_messages` tests (lines 59-103) to be async:

Add `import pytest` at top, then change:
- `def test_prepare_messages_renders_prompt_template_with_kwargs():` → `@pytest.mark.asyncio` + `async def ...`
- `messages = ait._prepare_messages(` → `messages = await ait._prepare_messages(`
- Same for `test_prepare_messages_renders_prompt_with_encoded_kwargs`

- [ ] **Step 5: Run all tests to verify they pass**

Run: `uv run pytest tests/unit/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add py_ai_toolkit/core/toolkit.py tests/unit/test_hooks.py tests/unit/test_tools.py
git commit -m "feat: wire render hooks into _prepare_messages (now async)"
```

---

### Task 3: Wire LLM call hooks into chat, stream, and asend

**Files:**
- Modify: `py_ai_toolkit/core/toolkit.py:130-196` (`chat`, `stream`, `asend`)
- Test: `tests/unit/test_hooks.py`

- [ ] **Step 1: Write failing tests for LLM call hooks**

Append to `tests/unit/test_hooks.py`:

```python
from unittest.mock import AsyncMock, MagicMock
from py_ai_toolkit.core.hooks import BeforeLLMCallContext, AfterLLMCallContext
from py_ai_toolkit.core.domain.schemas import CompletionResponse


def _new_toolkit_with_llm():
    from py_ai_toolkit.core.toolkit import PyAIToolkit

    ait = PyAIToolkit.__new__(PyAIToolkit)
    ait.prompt_formatter = Jinja2Adapter()
    ait.alternative_llm_clients = []

    mock_completion = MagicMock()
    mock_response = CompletionResponse(completion=mock_completion, content="hello")
    ait.llm_client = AsyncMock()
    ait.llm_client.chat = AsyncMock(return_value=mock_response)
    ait.llm_client._model = "test-model"
    # Expose _model for hook context
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
    mock_completion = MagicMock()
    mock_response = CompletionResponse(completion=mock_completion, content=mock_instance)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_hooks.py::test_chat_fires_before_and_after_llm_hooks tests/unit/test_hooks.py::test_asend_fires_before_and_after_llm_hooks -v`
Expected: FAIL — `chat()` and `asend()` don't accept `hooks`

- [ ] **Step 3: Add hooks parameter and LLM hook firing to chat, stream, asend**

Add imports at top of `toolkit.py` (extend existing import):

```python
from py_ai_toolkit.core.hooks import (
    Hooks, _fire_hook,
    BeforeRenderContext, AfterRenderContext,
    BeforeLLMCallContext, AfterLLMCallContext,
)
```

Add `import time` at top of `toolkit.py`.

**chat()** — change signature and body:

```python
async def chat(
    self,
    template: str | None = None,
    *,
    hooks: Hooks | None = None,
    **kwargs: Any,
) -> CompletionResponse:
    messages = await self._prepare_messages(template, hooks=hooks, **kwargs)

    if hooks:
        await _fire_hook(
            hooks.before_llm_call,
            BeforeLLMCallContext(
                messages=messages,
                model=self.llm_client._model,
                response_model=None,
            ),
        )

    start = time.perf_counter()
    response = await self.llm_client.chat(messages=messages)
    elapsed_ms = (time.perf_counter() - start) * 1000

    if hooks:
        await _fire_hook(
            hooks.after_llm_call,
            AfterLLMCallContext(
                response=response,
                model=self.llm_client._model,
                elapsed_ms=elapsed_ms,
            ),
        )

    return response
```

**stream()** — change signature and body:

```python
async def stream(
    self,
    template: str | None = None,
    *,
    hooks: Hooks | None = None,
    **kwargs: Any,
) -> AsyncGenerator[CompletionResponse, None]:
    messages = await self._prepare_messages(template, hooks=hooks, **kwargs)

    if hooks:
        await _fire_hook(
            hooks.before_llm_call,
            BeforeLLMCallContext(
                messages=messages,
                model=self.llm_client._model,
                response_model=None,
            ),
        )

    start = time.perf_counter()
    async for response in self.llm_client.stream(messages=messages):
        yield response

    elapsed_ms = (time.perf_counter() - start) * 1000
    if hooks:
        await _fire_hook(
            hooks.after_llm_call,
            AfterLLMCallContext(
                response=response,
                model=self.llm_client._model,
                elapsed_ms=elapsed_ms,
            ),
        )
```

**asend()** — change signature and body:

```python
async def asend(
    self,
    response_model: Type[T],
    template: str | None = None,
    *,
    hooks: Hooks | None = None,
    **kwargs: Any,
) -> CompletionResponse[T]:
    client = self.llm_client
    if self.alternative_llm_clients:
        client = random.choice(self.alternative_llm_clients)
    messages = await self._prepare_messages(template, hooks=hooks, **kwargs)

    if hooks:
        await _fire_hook(
            hooks.before_llm_call,
            BeforeLLMCallContext(
                messages=messages,
                model=client._model,
                response_model=response_model,
            ),
        )

    start = time.perf_counter()
    response = await client.asend(
        messages=messages,
        response_model=response_model,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    if hooks:
        await _fire_hook(
            hooks.after_llm_call,
            AfterLLMCallContext(
                response=response,
                model=client._model,
                elapsed_ms=elapsed_ms,
            ),
        )

    if not isinstance(response.content, response_model):
        raise ValueError(
            f"Response content is not an instance of {response_model.__name__}"
        )
    return response
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `uv run pytest tests/unit/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add py_ai_toolkit/core/toolkit.py tests/unit/test_hooks.py
git commit -m "feat: wire LLM call hooks into chat, stream, and asend"
```

---

### Task 4: Wire hooks into run_task and BaseWorkflow (validation + retry)

**Files:**
- Modify: `py_ai_toolkit/core/toolkit.py:198-233` (`run_task`)
- Modify: `py_ai_toolkit/core/base.py:29-43` (`BaseWorkflow.__init__`)
- Modify: `py_ai_toolkit/core/base.py:129-164` (`_redirect`)
- Modify: `py_ai_toolkit/core/base.py:264-299` (`_run_validations`)
- Modify: `py_ai_toolkit/core/base.py:301-354` (`create_task_tree`)
- Test: `tests/unit/test_hooks.py`

- [ ] **Step 1: Write failing tests for validation and retry hooks**

Append to `tests/unit/test_hooks.py`:

```python
from py_ai_toolkit.core.hooks import (
    BeforeValidationContext,
    AfterValidationContext,
    OnRetryContext,
)
from py_ai_toolkit.core.domain.schemas import SingleShotValidationConfig


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
    mock_output = MagicMock(spec=BaseModel)
    mock_output.model_dump_json = MagicMock(return_value='{}')
    task_node = MagicMock()
    task_node.output = mock_output
    task_node.kwargs = {"response_model": type(mock_output)}

    config = SingleShotValidationConfig(issues=["Is it correct?"])

    # Mock _run_issue to return True (valid)
    workflow._run_issue = AsyncMock(return_value=True)

    result = await workflow._run_validations(
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

    ait, _ = _new_toolkit_with_llm()
    workflow = BaseWorkflow(ai_toolkit=ait, error_class=WorkflowError)

    retry_captured = []

    async def on_retry(ctx: OnRetryContext):
        retry_captured.append(ctx)

    hooks = Hooks(on_retry=on_retry)
    workflow.hooks = hooks

    mock_output = MagicMock(spec=BaseModel)
    mock_output.model_dump_json = MagicMock(return_value='{}')

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_hooks.py::test_run_validations_fires_before_and_after_validation_hooks tests/unit/test_hooks.py::test_redirect_fires_on_retry_hook -v`
Expected: FAIL — `BaseWorkflow` has no `hooks` attribute

- [ ] **Step 3: Add hooks to BaseWorkflow and wire into _run_validations and _redirect**

In `py_ai_toolkit/core/base.py`, add import at top:

```python
from py_ai_toolkit.core.hooks import (
    Hooks,
    _fire_hook,
    BeforeValidationContext,
    AfterValidationContext,
    OnRetryContext,
)
```

**BaseWorkflow.__init__** — add `hooks` parameter:

```python
def __init__(
    self,
    ai_toolkit: PyAIToolkit,
    error_class: Type[Exception],
    echo: bool = False,
    hooks: Hooks | None = None,
):
    self.ai_toolkit = ai_toolkit
    self.ErrorClass = error_class
    self.echo = echo
    self.hooks = hooks

    # Stateful context
    self.current_retries = 0
    self.executor: TreeExecutor[S | V] | None = None
    self.failure_reasonings: dict[str, list[str]] = {}
```

**_run_validations** — add hook firing before and after (lines 264-299):

After `issue_nodes: list[Node[bool]] = []` (line 281) and before the for loop, add:

```python
        if self.hooks:
            await _fire_hook(
                self.hooks.before_validation,
                BeforeValidationContext(
                    output=task_node.output,
                    config=config,
                ),
            )
```

After `return all(...)` (line 299), restructure to capture result and fire hook:

```python
        result = all(bool(issue_node.output) for issue_node in issue_nodes)

        if self.hooks:
            failure_reasons = []
            for issue, reasons in self.failure_reasonings.items():
                failure_reasons.extend(reasons)
            await _fire_hook(
                self.hooks.after_validation,
                AfterValidationContext(
                    is_valid=result,
                    failure_reasons=failure_reasons,
                ),
            )

        return result
```

**_redirect** — add on_retry hook firing (lines 129-164):

After `await validation_node.redirect([task_node])` (line 164), just before it, add the on_retry hook. The full block after `self.current_retries += 1` and the max_retries check becomes:

```python
        task_node.kwargs["__evaluations__"] = f"""
        ## Output
        {source_output.model_dump_json(indent=2)}

        ## Failure Reasonings
        {self.failure_reasonings}
        """

        if self.hooks:
            await _fire_hook(
                self.hooks.on_retry,
                OnRetryContext(
                    current_retry=self.current_retries,
                    max_retries=config.max_retries,
                    evaluations=task_node.kwargs["__evaluations__"],
                ),
            )

        await validation_node.redirect([task_node])
```

- [ ] **Step 4: Update run_task to pass hooks through to BaseWorkflow**

In `py_ai_toolkit/core/toolkit.py`, update `run_task` (line 198):

```python
async def run_task(
    self,
    template: str,
    response_model: Type[T],
    kwargs: dict[str, Any],
    config: ValidationConfig = SingleShotValidationConfig(),
    echo: bool = False,
    *,
    hooks: Hooks | None = None,
) -> T:
    from py_ai_toolkit.core.base import BaseWorkflow

    workflow = BaseWorkflow(
        ai_toolkit=self,
        error_class=WorkflowError,
        echo=echo,
        hooks=hooks,
    )
    executor = await workflow.create_task_tree(
        template=template,
        response_model=response_model,
        kwargs=kwargs,
        config=config,
        echo=echo,
    )
    results = await executor.run()
    return results[0].output
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `uv run pytest tests/unit/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add py_ai_toolkit/core/base.py py_ai_toolkit/core/toolkit.py tests/unit/test_hooks.py
git commit -m "feat: wire validation and retry hooks into BaseWorkflow"
```

---

### Task 5: Export hooks from __init__.py

**Files:**
- Modify: `py_ai_toolkit/__init__.py`

- [ ] **Step 1: Write failing test for public imports**

Append to `tests/unit/test_hooks.py`:

```python
def test_hooks_exported_from_package():
    from py_ai_toolkit import Hooks
    from py_ai_toolkit.core.hooks import (
        BeforeRenderContext,
        AfterRenderContext,
        BeforeLLMCallContext,
        AfterLLMCallContext,
        BeforeValidationContext,
        AfterValidationContext,
        OnRetryContext,
    )
    assert Hooks is not None
    assert BeforeRenderContext is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_hooks.py::test_hooks_exported_from_package -v`
Expected: FAIL — `cannot import name 'Hooks' from 'py_ai_toolkit'`

- [ ] **Step 3: Add exports to __init__.py**

In `py_ai_toolkit/__init__.py`, add the import:

```python
from .core.hooks import Hooks
```

Add `"Hooks"` to the `__all__` list.

- [ ] **Step 4: Run all tests to verify they pass**

Run: `uv run pytest tests/unit/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add py_ai_toolkit/__init__.py tests/unit/test_hooks.py
git commit -m "feat: export Hooks from py_ai_toolkit package"
```
