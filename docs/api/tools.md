# PyAIToolkit API Reference

The main class for interacting with LLMs and managing response models.

## Constructor

```python
PyAIToolkit(
    main_model_config: LLMConfig,
    alternative_models_configs: list[LLMConfig] | None = None
)
```

**Parameters:**

- `main_model_config` (LLMConfig): Primary LLM configuration
- `alternative_models_configs` (list[LLMConfig] | None): Optional list of alternative models for load balancing

**Example:**

```python
from py_ai_toolkit import PyAIToolkit
from py_ai_toolkit.core.domain.interfaces import LLMConfig

ait = PyAIToolkit(
    main_model_config=LLMConfig(
        model="gpt-4",
        api_key="your-api-key"
    ),
    alternative_models_configs=[
        LLMConfig(model="gpt-4"),
        LLMConfig(model="claude-3-sonnet")
    ]
)
```

## Methods

### chat()

Execute a text-based chat task.

```python
async def chat(
    template: str | None = None,
    **kwargs: Any
) -> CompletionResponse
```

**Parameters:**

- `template` (str | None): Path to prompt template file or inline prompt string
- `**kwargs`: Variables to inject into the template

**Returns:** `CompletionResponse` with text content

**Example:**

```python
response = await ait.chat(
    template="Explain {{ topic }} in one sentence.",
    topic="quantum computing"
)
print(response.content)
```

---

### asend()

Execute a structured task with typed response.

```python
async def asend(
    response_model: Type[T],
    template: str | None = None,
    **kwargs: Any
) -> CompletionResponse[T]
```

**Parameters:**

- `response_model` (Type[T]): Pydantic model defining the response structure
- `template` (str | None): Path to prompt template file or inline prompt string
- `**kwargs`: Variables to inject into the template

**Returns:** `CompletionResponse[T]` with structured content

**Example:**

```python
class Summary(BaseModel):
    key_points: list[str]
    word_count: int

response = await ait.asend(
    response_model=Summary,
    template="Summarize: {{ text }}",
    text=long_article
)
print(response.content.key_points)
```

---

### stream()

Execute a streaming task returning text incrementally.

```python
async def stream(
    template: str | None = None,
    **kwargs: Any
) -> AsyncGenerator[CompletionResponse, None]
```

**Parameters:**

- `template` (str | None): Path to prompt template file or inline prompt string
- `**kwargs`: Variables to inject into the template

**Returns:** `AsyncGenerator` yielding `CompletionResponse` chunks

**Example:**

```python
async for chunk in ait.stream(
    template="Write a story about {{ topic }}",
    topic="space exploration"
):
    print(chunk.content, end="", flush=True)
```

---

### embed()

Generate embedding vector for text.

```python
async def embed(text: str) -> list[float]
```

**Parameters:**

- `text` (str): Text to embed

**Returns:** List of floats representing the embedding vector

**Example:**

```python
vector = await ait.embed("Machine learning is fascinating")
print(len(vector))  # Embedding dimension
```

---

### run_task()

Execute a validated task with automatic retries.

```python
async def run_task(
    template: str,
    response_model: Type[T],
    kwargs: dict[str, Any],
    config: ValidationConfig = SingleShotValidationConfig(),
    echo: bool = False
) -> T
```

**Parameters:**

- `template` (str): Prompt template
- `response_model` (Type[T]): Pydantic model for output
- `kwargs` (dict[str, Any]): Template variables
- `config` (ValidationConfig): Validation configuration
- `echo` (bool): Enable debug logging

**Returns:** Instance of `response_model` with validated output

**Example:**

```python
from py_ai_toolkit.core.domain.interfaces import SingleShotValidationConfig

result = await ait.run_task(
    template="Extract data from: {{ input }}",
    response_model=ExtractedData,
    kwargs=dict(input=raw_data),
    config=SingleShotValidationConfig(
        issues=["Data is complete and accurate"]
    )
)
```

---

### inject_types()

Inject field types into a Pydantic model.

```python
def inject_types(
    model: Type[T],
    fields: list[tuple[str, Any]],
    docstring: str | None = None
) -> Type[T]
```

**Parameters:**

- `model` (Type[T]): Base Pydantic model
- `fields` (list[tuple[str, Any]]): List of (field_name, type) tuples to inject
- `docstring` (str | None): Optional docstring for the new model

**Returns:** New model class with injected types

**Example:**

```python
from typing import Literal

class Product(BaseModel):
    name: str
    category: str

categories = ["electronics", "clothing", "food"]

ProductModel = ait.inject_types(
    Product,
    fields=[("category", Literal[tuple(categories)])],
    docstring="Product with constrained categories"
)
```

---

### reduce_model_schema()

Reduce model schema to a compact string representation.

```python
def reduce_model_schema(
    model: Type[T],
    include_description: bool = True
) -> str
```

**Parameters:**

- `model` (Type[T]): Pydantic model to reduce
- `include_description` (bool): Whether to include field descriptions

**Returns:** Compact schema string

**Example:**

```python
schema = ait.reduce_model_schema(ComplexModel)
print(schema)  # Compact representation for prompts
```

## Supporting Classes

### LLMConfig

Configuration for LLM connection.

```python
class LLMConfig(BaseModel):
    model: str | None = None
    embedding_model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
```

Falls back to environment variables: `LLM_MODEL`, `EMBEDDING_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`.

### CompletionResponse

Response wrapper for LLM outputs.

```python
class CompletionResponse(BaseModel, Generic[T]):
    completion: ChatCompletion | ChatCompletionChunk
    content: str | T

    @property
    def response_model(self) -> T:
        """Returns structured content (raises if content is string)"""
```

**Attributes:**

- `completion`: Raw OpenAI completion object
- `content`: Text string or structured model instance
- `response_model`: Property for type-safe access to structured content
