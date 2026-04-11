# Hooks

Hooks let you observe what happens inside the toolkit without changing its behavior. Use them to track token usage, measure latency, log prompts, or feed data into a dashboard.

## Quick Start

```python
from py_ai_toolkit import PyAIToolkit, Hooks
from py_ai_toolkit.core.hooks import AfterLLMCallContext

async def log_usage(ctx: AfterLLMCallContext) -> None:
    tokens = ctx.response.completion.usage.total_tokens
    print(f"[{ctx.model}] {tokens} tokens in {ctx.elapsed_ms:.0f}ms")

toolkit = PyAIToolkit(config)
result = await toolkit.asend(
    response_model=MyModel,
    template="Summarize: {{ text }}",
    hooks=Hooks(after_llm_call=log_usage),
    text="Hello world",
)
```

Hooks are passed directly to the method you're calling. Every hook is an async function that receives a typed context object.

## Available Hooks

The toolkit fires hooks at seven points in the pipeline:

| Hook | Fires when | Context type |
|---|---|---|
| `before_render` | Before Jinja2 template rendering | `BeforeRenderContext` |
| `after_render` | After template rendering | `AfterRenderContext` |
| `before_llm_call` | Before the LLM API call | `BeforeLLMCallContext` |
| `after_llm_call` | After the LLM response | `AfterLLMCallContext` |
| `before_validation` | Before a validation round | `BeforeValidationContext` |
| `after_validation` | After a validation round | `AfterValidationContext` |
| `on_retry` | When a retry is triggered | `OnRetryContext` |

## Which Methods Support Which Hooks

| Method | Render hooks | LLM hooks | Embed hooks | Validation/retry hooks |
|---|---|---|---|---|
| `chat()` | Yes | Yes | -- | -- |
| `stream()` | Yes | Yes | -- | -- |
| `asend()` | Yes | Yes | -- | -- |
| `run_task()` | Yes | Yes | -- | Yes |
| `embed()` | -- | -- | `after_embed` | -- |
| `embed_batch()` | -- | -- | `after_embed_batch` | -- |

Validation and retry hooks only fire in `run_task()` because that's where the validation loop lives.

## The Hooks Container

Register your callbacks using the `Hooks` dataclass. All fields are optional and default to `None`:

```python
from py_ai_toolkit import Hooks

hooks = Hooks(
    before_render=my_before_render,
    after_render=my_after_render,
    before_llm_call=my_before_llm,
    after_llm_call=my_after_llm,
    after_embed=my_after_embed,
    after_embed_batch=my_after_embed_batch,
    before_validation=my_before_val,
    after_validation=my_after_val,
    on_retry=my_on_retry,
)
```

Pass it to any supported method:

```python
await toolkit.chat(template="Hello", hooks=hooks)
await toolkit.asend(response_model=MyModel, template="...", hooks=hooks)
await toolkit.run_task(template="...", response_model=MyModel, kwargs={}, hooks=hooks)
```

## Context Objects

Each hook receives a frozen (immutable) context object with the data available at that point in the pipeline. Your editor will autocomplete the fields for you.

### BeforeRenderContext

```python
async def on_before_render(ctx: BeforeRenderContext) -> None:
    print(ctx.template)   # str | None - template path or inline string
    print(ctx.kwargs)     # dict[str, Any] - template variables
```

### AfterRenderContext

```python
async def on_after_render(ctx: AfterRenderContext) -> None:
    print(ctx.prompt)     # str - the fully rendered prompt
```

### BeforeLLMCallContext

```python
async def on_before_llm(ctx: BeforeLLMCallContext) -> None:
    print(ctx.messages)       # list[dict[str, str]] - messages sent to the API
    print(ctx.model)          # str - model name
    print(ctx.response_model) # Type | None - None for chat/stream
```

### AfterLLMCallContext

```python
async def on_after_llm(ctx: AfterLLMCallContext) -> None:
    print(ctx.response)    # CompletionResponse - the full response
    print(ctx.model)       # str - model name
    print(ctx.elapsed_ms)  # float - API call duration in milliseconds
```

### BeforeValidationContext

```python
async def on_before_validation(ctx: BeforeValidationContext) -> None:
    print(ctx.output)  # BaseModel - the task output being validated
    print(ctx.config)  # ValidationConfig - the validation configuration
```

### AfterValidationContext

```python
async def on_after_validation(ctx: AfterValidationContext) -> None:
    print(ctx.is_valid)         # bool - whether validation passed
    print(ctx.failure_reasons)  # list[str] - reasons for failure (empty if valid)
```

### OnRetryContext

```python
async def on_retry(ctx: OnRetryContext) -> None:
    print(ctx.current_retry)  # int - which retry this is (1-based)
    print(ctx.max_retries)    # int - maximum retries configured
    print(ctx.evaluations)    # str - feedback string passed to next attempt
```

## Example: Token Usage Tracker

```python
from py_ai_toolkit import PyAIToolkit, Hooks
from py_ai_toolkit.core.hooks import AfterLLMCallContext

total_tokens = 0

async def track_tokens(ctx: AfterLLMCallContext) -> None:
    global total_tokens
    usage = ctx.response.completion.usage
    total_tokens += usage.total_tokens
    print(f"Call used {usage.total_tokens} tokens ({ctx.elapsed_ms:.0f}ms)")

hooks = Hooks(after_llm_call=track_tokens)

# All calls through this hooks instance accumulate token counts
await toolkit.asend(response_model=Summary, template="...", hooks=hooks)
await toolkit.chat(template="...", hooks=hooks)

print(f"Total tokens used: {total_tokens}")
```

## Example: Retry Monitor

```python
from py_ai_toolkit.core.hooks import OnRetryContext, AfterValidationContext

async def on_validation(ctx: AfterValidationContext) -> None:
    status = "PASS" if ctx.is_valid else "FAIL"
    print(f"Validation: {status}")
    if not ctx.is_valid:
        for reason in ctx.failure_reasons:
            print(f"  - {reason}")

async def on_retry(ctx: OnRetryContext) -> None:
    print(f"Retrying ({ctx.current_retry}/{ctx.max_retries})...")

result = await toolkit.run_task(
    template="Extract: {{ text }}",
    response_model=Extraction,
    kwargs=dict(text=raw_text),
    config=SingleShotValidationConfig(
        issues=["Extraction is complete and accurate"],
        max_retries=3,
    ),
    hooks=Hooks(after_validation=on_validation, on_retry=on_retry),
)
```

## Important Notes

- Hooks are **observation-only**. They cannot modify requests or responses.
- Hooks are **async functions**. They are awaited inline in the pipeline.
- If a hook raises an exception, it **propagates to the caller**. Keep your hooks simple and handle errors within them if needed.
- `elapsed_ms` in `AfterLLMCallContext` measures **API latency only**, not template rendering or validation time.
- For `stream()`, the `after_llm_call` hook fires after the stream completes and receives the last chunk as the response.

## All Imports

```python
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
```
