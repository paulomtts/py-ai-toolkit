---
name: py-ai-toolkit
description: Load the py-ai-toolkit public API reference. Use when writing or reviewing code that uses py-ai-toolkit — covers imports, all method signatures, validation configs, workflow patterns, and common mistakes.
argument-hint: [topic]
allowed-tools: Read, Grep, Glob
---

You are helping a user work with **py-ai-toolkit**, a Python library for building LLM-driven applications. Use this reference to write correct, idiomatic code.

---

## Installation

```bash
uv add py-ai-toolkit
```

---

## Configuration

`PyAIToolkit` reads from environment variables by default:

| Variable | Description |
|---|---|
| `LLM_MODEL` | Model identifier (e.g. `gpt-4o`) |
| `LLM_API_KEY` | API key |
| `LLM_BASE_URL` | Base URL for the API |
| `EMBEDDING_MODEL` | Embedding model identifier |
| `LLM_REASONING_EFFORT` | `low`, `medium`, or `high` |

Or pass `LLMConfig` directly:

```python
from py_ai_toolkit import PyAIToolkit, LLMConfig

toolkit = PyAIToolkit(main_model_config=LLMConfig(model="gpt-4o", api_key="..."))
```

---

## Public API

### Top-level imports

```python
from py_ai_toolkit import (
    PyAIToolkit,       # Main class
    LLMConfig,         # Configuration model
    CompletionResponse, # Response wrapper
    BaseWorkflow,      # Base class for custom workflows
    WorkflowError,     # Exception class for workflow errors
    BaseIssue,         # Base model for validation issues
    Node,              # grafo node (re-exported)
    TreeExecutor,      # grafo executor (re-exported)
    Chunk,             # grafo chunk (re-exported)
)
```

Validation configs are imported from:

```python
from py_ai_toolkit.core.domain.schemas import (
    SingleShotValidationConfig,
    ThresholdVotingValidationConfig,
    KAheadVotingValidationConfig,
    ValidationConfig,   # Union type alias
)
```

---

### PyAIToolkit

#### Constructor

```python
toolkit = PyAIToolkit(
    main_model_config: LLMConfig | None = None,
    alternative_models_configs: list[LLMConfig] | None = None,
)
```

- `main_model_config`: Falls back to env vars if `None`.
- `alternative_models_configs`: When provided, `asend()` randomly selects from these for load balancing.

---

#### `chat()` — plain text response

```python
response = await toolkit.chat(
    template="Explain {{ topic }} in one sentence.",
    topic="machine learning",
)
print(response.content)  # str
```

- `template`: inline string or path to a `.md` file
- `**kwargs`: Jinja2 template variables
- Returns `CompletionResponse` where `.content` is `str`

---

#### `asend()` — structured response

```python
from pydantic import BaseModel

class Purchase(BaseModel):
    product: str
    quantity: int

response = await toolkit.asend(
    response_model=Purchase,
    template="Extract purchase from: {{ message }}",
    message="I want 5 apples",
)
print(response.content.product)   # "apple"
print(response.content.quantity)  # 5
```

- Returns `CompletionResponse[T]` where `.content` is an instance of `response_model`
- When `alternative_models_configs` is set, randomly picks one of them

---

#### `stream()` — streaming text

```python
async for chunk in toolkit.stream(
    template="Write a story about {{ topic }}",
    topic="space exploration",
):
    print(chunk.content, end="", flush=True)
```

---

#### `embed()` — text embeddings

```python
response: EmbeddingResponse = await toolkit.embed("some text")
vector = response.embedding    # list[float]
usage = response.usage         # EmbeddingUsage
```

---

#### `embed_batch()` — batch text embeddings

```python
responses: list[EmbeddingResponse] = await toolkit.embed_batch(["text one", "text two"])
vectors = [r.embedding for r in responses]
```

- Embeds multiple texts in a single API request
- Returns one `EmbeddingResponse` per input, preserving order
- Usage is aggregated across all inputs (same on each response)

---

#### `run_task()` — structured response with validation and retry

```python
from py_ai_toolkit.core.domain.schemas import SingleShotValidationConfig

result = await toolkit.run_task(
    template="Extract purchase from: {{ message }}",
    response_model=Purchase,
    kwargs=dict(message="I want 5 apples"),
    config=SingleShotValidationConfig(
        issues=["The identified purchase matches the user's request."],
    ),
    echo=False,  # set True for debug logging
)
print(result.product)   # Direct instance, not wrapped in CompletionResponse
print(result.quantity)
```

- `kwargs` is a `dict`, not `**kwargs`
- Returns the `response_model` instance directly (not a `CompletionResponse`)
- Validation issues are each checked independently by an LLM-based validator

---

#### `inject_types()` — constrain field types at runtime

```python
from typing import Literal

FruitModel = toolkit.inject_types(
    Purchase,
    fields=[("product", Literal[("apple", "banana", "orange")])],
    docstring="Purchase with constrained product choices",
)
```

---

#### `reduce_model_schema()` — compact schema string for prompts

```python
schema_str = toolkit.reduce_model_schema(Purchase, include_description=True)
```

---

### CompletionResponse

```python
class CompletionResponse(BaseModel, Generic[T]):
    completion: ChatCompletion | ChatCompletionChunk  # raw OpenAI object
    content: str | T

    @property
    def response_model(self) -> T: ...  # raises if content is a string
```

---

### Validation Configs

All configs accept `issues: list[str]` — validation criteria evaluated independently.

| Config | `count` | `required_ahead` | `max_retries` | Use case |
|---|---|---|---|---|
| `SingleShotValidationConfig` | 1 | 1 | 3 | Simple tasks |
| `ThresholdVotingValidationConfig` | 3 | 1 | 0 | Moderate confidence |
| `KAheadVotingValidationConfig` | 5 | 3 | 0 | High-stakes tasks |

`count` must always be odd. When validation fails and `max_retries > 0`, the task is re-run with failure reasoning injected into the prompt automatically.

---

### BaseWorkflow — custom workflow orchestration

```python
from py_ai_toolkit import PyAIToolkit, BaseWorkflow, WorkflowError

toolkit = PyAIToolkit()
workflow = BaseWorkflow(
    ai_toolkit=toolkit,
    error_class=WorkflowError,
    echo=False,
)
```

#### `task()` — LLM call inside a workflow

```python
# Text
result: str = await workflow.task(template="...", **kwargs)

# Structured
result: Purchase = await workflow.task(
    template="...",
    response_model=Purchase,
    **kwargs,
)
```

#### `create_task_tree()` — task + validation subtree

```python
from py_ai_toolkit.core.domain.schemas import SingleShotValidationConfig

executor = await workflow.create_task_tree(
    template="Extract purchase: {{ message }}",
    response_model=Purchase,
    kwargs=dict(message="I want 5 apples"),
    config=SingleShotValidationConfig(
        issues=["The purchase matches the user's request"],
    ),
)
results = await executor.run()
purchase = results[0].output
```

#### `build_task_node()` — wraps a task tree in a single Node

```python
node = await workflow.build_task_node(
    uuid="purchase_node",
    template="...",
    response_model=Purchase,
    kwargs=dict(...),
    config=SingleShotValidationConfig(...),
)
```

Use this to embed a validated task as a node inside a larger grafo graph.

---

### Building graphs with grafo

```python
from py_ai_toolkit import Node, TreeExecutor

# Sequential
node_a = Node[Purchase](
    uuid="extract",
    coroutine=workflow.task,
    kwargs=dict(template="...", response_model=Purchase, message="..."),
)
node_b = Node[str](
    uuid="summarize",
    coroutine=workflow.task,
    kwargs=dict(template="Summarize: {{ purchase }}", purchase=node_a.output),
)
await node_a.connect(node_b)

executor = TreeExecutor(uuid="my_workflow", roots=[node_a])
results = await executor.run()

# Parallel (multiple roots)
executor = TreeExecutor(uuid="parallel", roots=[node_a, node_b, node_c])
```

---

### Custom Workflow class

```python
from py_ai_toolkit import PyAIToolkit, BaseWorkflow, Node, TreeExecutor, WorkflowError
from py_ai_toolkit.core.domain.schemas import SingleShotValidationConfig

class PurchaseWorkflow(BaseWorkflow):
    async def run(self, message: str) -> Purchase:
        executor = await self.create_task_tree(
            template="Extract purchase: {{ message }}",
            response_model=Purchase,
            kwargs=dict(message=message),
            config=SingleShotValidationConfig(
                issues=["The purchase matches the user's request"],
            ),
        )
        results = await executor.run()
        return results[0].output

toolkit = PyAIToolkit()
workflow = PurchaseWorkflow(ai_toolkit=toolkit, error_class=WorkflowError)
result = await workflow.run("I want 5 apples")
```

---

## Common mistakes to avoid

- **Wrong import path**: validation configs live in `py_ai_toolkit.core.domain.schemas`, NOT `interfaces`
- **Missing `await`**: `chat()`, `asend()`, `stream()`, `embed()`, `embed_batch()`, `run_task()`, `task()`, `create_task_tree()`, and `build_task_node()` are all `async`
- **`run_task` kwargs**: pass as `kwargs=dict(...)`, not `**kwargs`
- **`run_task` return**: returns the model instance directly, not a `CompletionResponse`
- **`asend` return**: returns `CompletionResponse[T]`; access the model via `.content`
- **`count` must be odd** in all validation configs
