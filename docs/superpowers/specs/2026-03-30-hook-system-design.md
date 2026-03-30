# Hook System Design

Passive observation hooks for py-ai-toolkit's public API, enabling token tracking, latency monitoring, and pipeline visibility without altering behavior.

## Hook Points

Seven hook points covering the full pipeline:

| Hook | Fires when | Available in |
|---|---|---|
| `before_render` | Before Jinja2 template rendering | `chat`, `stream`, `asend`, `run_task` |
| `after_render` | After template rendering | `chat`, `stream`, `asend`, `run_task` |
| `before_llm_call` | Before hitting the LLM API | `chat`, `stream`, `asend`, `run_task` |
| `after_llm_call` | After LLM response received | `chat`, `stream`, `asend`, `run_task` |
| `before_validation` | Before validation round starts | `run_task` |
| `after_validation` | After validation round completes | `run_task` |
| `on_retry` | When a retry is triggered | `run_task` |

`embed()` is excluded — no template rendering or structured output involved.

## Hook Context Dataclasses

Each hook point has a frozen (immutable) dataclass carrying observation data:

```python
@dataclass(frozen=True)
class BeforeRenderContext:
    template: str | None       # template path or inline string
    kwargs: dict[str, Any]     # template variables

@dataclass(frozen=True)
class AfterRenderContext:
    prompt: str                # the rendered prompt string

@dataclass(frozen=True)
class BeforeLLMCallContext:
    messages: list[dict[str, str]]
    model: str
    response_model: Type | None  # None for chat/stream

@dataclass(frozen=True)
class AfterLLMCallContext:
    response: CompletionResponse
    model: str
    elapsed_ms: float

@dataclass(frozen=True)
class BeforeValidationContext:
    output: BaseModel
    config: SingleShotValidationConfig

@dataclass(frozen=True)
class AfterValidationContext:
    is_valid: bool
    failure_reasons: list[str]

@dataclass(frozen=True)
class OnRetryContext:
    current_retry: int
    max_retries: int
    evaluations: str            # feedback string passed to next attempt
```

## Callback Types

Type aliases for each hook callback, enabling linter validation of user-provided functions:

```python
BeforeRenderHook = Callable[[BeforeRenderContext], Awaitable[None]]
AfterRenderHook = Callable[[AfterRenderContext], Awaitable[None]]
BeforeLLMCallHook = Callable[[BeforeLLMCallContext], Awaitable[None]]
AfterLLMCallHook = Callable[[AfterLLMCallContext], Awaitable[None]]
BeforeValidationHook = Callable[[BeforeValidationContext], Awaitable[None]]
AfterValidationHook = Callable[[AfterValidationContext], Awaitable[None]]
OnRetryHook = Callable[[OnRetryContext], Awaitable[None]]
```

## Hooks Container

A single dataclass that users populate with optional callbacks:

```python
@dataclass
class Hooks:
    before_render: BeforeRenderHook | None = None
    after_render: AfterRenderHook | None = None
    before_llm_call: BeforeLLMCallHook | None = None
    after_llm_call: AfterLLMCallHook | None = None
    before_validation: BeforeValidationHook | None = None
    after_validation: AfterValidationHook | None = None
    on_retry: OnRetryHook | None = None
```

## Public API Changes

The `hooks` parameter is added as a keyword-only argument to every user-facing method on `PyAIToolkit`:

```python
class PyAIToolkit:
    async def chat(self, template, *, hooks: Hooks | None = None, **kwargs) -> CompletionResponse
    async def stream(self, template, *, hooks: Hooks | None = None, **kwargs) -> AsyncGenerator[CompletionResponse]
    async def asend(self, response_model, template, *, hooks: Hooks | None = None, **kwargs) -> CompletionResponse[T]
    async def run_task(self, template, response_model, kwargs, config, *, hooks: Hooks | None = None, echo) -> T
```

## Hook Execution

- Hooks are awaited inline at each hook point, sequentially within the flow
- Hook exceptions propagate to the caller (not swallowed)
- A simple internal helper avoids repetition:

```python
async def _fire_hook(hook: Callable | None, ctx: Any) -> None:
    if hook is not None:
        await hook(ctx)
```

## Timing

`AfterLLMCallContext.elapsed_ms` measures API latency only: timer starts immediately before the adapter call and stops when the response is received. Template rendering and validation are not included.

## Hook Fire Locations

| Hook | Location |
|---|---|
| `before_render`, `after_render` | `_prepare_messages()` in `toolkit.py` |
| `before_llm_call`, `after_llm_call` | Wrapping the adapter call in `chat()`, `stream()`, `asend()` in `toolkit.py` |
| `before_validation`, `after_validation` | `_run_validations()` in `base.py` |
| `on_retry` | `_redirect()` in `base.py`, just before re-running the task node |

## Usage Example

```python
from py_ai_toolkit import PyAIToolkit, Hooks
from py_ai_toolkit.hooks import AfterLLMCallContext

async def track_tokens(ctx: AfterLLMCallContext) -> None:
    print(f"Model: {ctx.model}, Tokens: {ctx.response.completion.usage.total_tokens}")
    print(f"Latency: {ctx.elapsed_ms:.0f}ms")

toolkit = PyAIToolkit(config)
result = await toolkit.asend(
    response_model=MyModel,
    template="prompt.md",
    hooks=Hooks(after_llm_call=track_tokens),
    name="John",
)
```
