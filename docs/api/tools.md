# PyAIToolkit API Reference

The main class for interacting with LLMs and managing response models.

## Constructor

```python
PyAIToolkit(
    main_model_config: LLMConfig | None = None,
    alternative_models_configs: list[LLMConfig] | None = None,
    classifier_config: ClassifierConfig | None = None
)
```

**Parameters:**

- `main_model_config` (LLMConfig | None): Primary LLM configuration
- `alternative_models_configs` (list[LLMConfig] | None): Optional list of alternative models for load balancing
- `classifier_config` (ClassifierConfig | None): Optional Jev classifier settings. Unset fields fall back to `CLASSIFIER_API_KEY`, `CLASSIFIER_MODEL` (default `"jev-latest"`) and `CLASSIFIER_BASE_URL`, read here at construction. A classifier is built only if this is passed or `CLASSIFIER_API_KEY` is set; otherwise `classifier` is `None`. See the [Classifier guide](../guide/classifier.md).

**Raises:**

- `ValueError`: `classifier_config` was passed but neither it nor `CLASSIFIER_API_KEY` provides an API key
- `ImportError`: a classifier would be built but the `jev` extra is not installed (`pip install 'py-ai-toolkit[jev]'`)

**Example:**

```python
from py_ai_toolkit import PyAIToolkit
from py_ai_toolkit.core.domain.schemas import LLMConfig

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
async def embed(text: str, *, hooks: Hooks | None = None) -> EmbeddingResponse
```

**Parameters:**

- `text` (str): Text to embed
- `hooks` (Hooks | None): Optional hooks (fires `after_embed`)

**Returns:** `EmbeddingResponse` with `.embedding` (vector) and `.usage` (token data)

**Example:**

```python
response = await ait.embed("Machine learning is fascinating")
print(len(response.embedding))  # Embedding dimension
print(response.usage.total_tokens)  # Token usage
```

---

### embed_batch()

Embed multiple texts in a single API request.

```python
async def embed_batch(texts: list[str], *, hooks: Hooks | None = None) -> list[EmbeddingResponse]
```

**Parameters:**

- `texts` (list[str]): Texts to embed
- `hooks` (Hooks | None): Optional hooks (fires `after_embed_batch`)

**Returns:** List of `EmbeddingResponse`, one per input text, preserving order

**Example:**

```python
responses = await ait.embed_batch(["Machine learning", "Deep learning", "NLP"])
vectors = [r.embedding for r in responses]
print(responses[0].usage.total_tokens)  # Aggregated usage across all inputs
```

---

### classify()

Answer structured questions about a piece of content with the configured Jev classifier.

```python
async def classify(
    state: str | dict | list,
    questions: Mapping[str, Question],
    *,
    hooks: Hooks | None = None
) -> ClassifierResponse
```

**Parameters:**

- `state` (str | dict | list): The text or JSON-like content to classify
- `questions` (Mapping[str, Question]): Question name to question (`NoulQuestion`, `ChoiceQuestion` or `ScoreQuestion`)
- `hooks` (Hooks | None): Optional hooks (fires `before_classify` and `after_classify`)

**Returns:** `ClassifierResponse` with one raw answer per question name, unchanged

**Raises:**

- `ClassifierAdapterError`: no classifier is configured, or the SDK/API call failed (the original exception is on `__cause__`)
- `ValueError`: `questions` is empty (`questions must not be empty.`)

**Example:**

```python
from py_ai_toolkit import ChoiceQuestion, NoulQuestion

response = await ait.classify(
    state="I was charged twice for my March invoice.",
    questions={
        "is_refund_request": NoulQuestion(instructions="Is the customer asking for money back?"),
        "department": ChoiceQuestion(
            instructions="Which team should handle this?",
            criteria={"billing": "Payments and invoices.", "none": "None of the above."},
        ),
    },
)
print(response.nouls["is_refund_request"].noul)
print(response.choices["department"].choice)
```

---

### aclose()

Release the classifier's resources. A no-op when no classifier is configured.

```python
async def aclose() -> None
```

**Returns:** `None`

**Example:**

```python
await ait.aclose()
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
from py_ai_toolkit.core.domain.schemas import SingleShotValidationConfig

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

### ClassifierConfig

Configuration for the Jev classifier.

```python
class ClassifierConfig(BaseModel):
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
```

Falls back to environment variables, field by field: `CLASSIFIER_API_KEY`, `CLASSIFIER_MODEL` (default `"jev-latest"`), `CLASSIFIER_BASE_URL`. The environment is read by `PyAIToolkit`, not by this class.

### ClassifierResponse

Response returned by `classify()`. Values are raw; nothing is normalized or derived.

```python
class ClassifierResponse(BaseModel):
    model: str
    answers: dict[str, Answer]
    usage: ClassifierUsage

    @property
    def nouls(self) -> dict[str, NoulAnswer]: ...

    @property
    def choices(self) -> dict[str, ChoiceAnswer]: ...

    @property
    def scores(self) -> dict[str, ScoreAnswer]: ...
```

**Attributes:**

- `model`: The classifier model that answered
- `answers`: Question name to answer; empty answer names fail validation
- `usage`: Token usage
- `nouls`, `choices`, `scores`: The answers of each type, keyed by question name

### ClassifierUsage

```python
class ClassifierUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
```

### NoulQuestion

A yes/no question.

```python
class NoulQuestion(BaseModel):
    type: Literal["noul"] = "noul"
    instructions: JSONContent | None = None
    criteria: NoulCriteria | None = None
```

`JSONContent` is `str | dict[str, Any] | list[Any]`.

### NoulCriteria

What counts as true and false for a `NoulQuestion`. Not exported from the package root:

```python
from py_ai_toolkit.core.domain.classifier import NoulCriteria
```

```python
class NoulCriteria(BaseModel):
    true: JSONContent | None = None
    false: JSONContent | None = None
```

### ChoiceQuestion

A single-select question. It always picks one option and cannot abstain.

```python
class ChoiceQuestion(BaseModel):
    type: Literal["choice"] = "choice"
    instructions: JSONContent | None = None
    criteria: dict[str, JSONContent | None]  # 1 to 255 entries
```

### ScoreQuestion

A question that places the state on a scale.

```python
class ScoreQuestion(BaseModel):
    type: Literal["score"] = "score"
    instructions: JSONContent | None = None
    criteria: list[JSONContent]  # 2 to 10 entries
```

### NoulAnswer

```python
class NoulAnswer(BaseModel):
    type: Literal["noul"] = "noul"
    noul: float
```

No confidence field: threshold `noul` directly.

### ChoiceAnswer

```python
class ChoiceAnswer(BaseModel):
    type: Literal["choice"] = "choice"
    choice: str
    probabilities: dict[str, float]
    confidence: float
```

### ScoreAnswer

```python
class ScoreAnswer(BaseModel):
    type: Literal["score"] = "score"
    score: float
    probabilities: dict[int, float]
    confidence: float
    legend: dict[int, JSONContent]
```

`probabilities` and `legend` are keyed by `int` level. `confidence` here is not comparable with `ChoiceAnswer.confidence`.

### Question

```python
Question = Annotated[
    NoulQuestion | ChoiceQuestion | ScoreQuestion, Field(discriminator="type")
]
```

### Answer

```python
Answer = Annotated[NoulAnswer | ChoiceAnswer | ScoreAnswer, Field(discriminator="type")]
```

### ClassifierAdapterError

```python
class ClassifierAdapterError(Exception): ...
```

Raised by `classify()` when no classifier is configured and for every SDK or API failure (authentication, unprocessable entity, rate limit, internal server error, connection or timeout, malformed response, any other `TypeSafeError`). The original SDK exception is on `__cause__`. Import it with `from py_ai_toolkit import ClassifierAdapterError`.
