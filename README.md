# Install
```
uv add py-ai-toolkit
```

# WHAT
A set of tools for easily interacting with LLMs.

# WHY
Building AI-driven software leans upon a number of utilities, such as prompt building and LLM calling via HTTP requests. Additionally, writing agents and workflows can prove particularly challenging using conventional code structures.

# HOW
This simple library offers a set of predefined functions for:
- Easy prompting - you need only provide a path or a template string
- Calling LLMs - instructor takes care of structured responses
- Modifying response models - we use Pydantic

Additionally, we provide `grafo` out of the box for convenient workflow building.

## Configuration

`PyAIToolkit` reads configuration from environment variables by default:

| Variable | Description |
|---|---|
| `LLM_MODEL` | Model identifier (e.g. `gpt-4o`) |
| `LLM_API_KEY` | API key |
| `LLM_BASE_URL` | Base URL for the API |
| `EMBEDDING_MODEL` | Embedding model identifier |
| `LLM_REASONING_EFFORT` | Reasoning effort (e.g. `low`, `medium`, `high`) |

You can also pass an `LLMConfig` directly:

```python
from py_ai_toolkit import PyAIToolkit, LLMConfig

toolkit = PyAIToolkit(main_model_config=LLMConfig(model="gpt-4o", api_key="..."))
```

## About Grafo
Grafo (see Recommended Docs below) is a library for building executable DAGs where each node contains a coroutine. Since the DAG abstraction fits particularly well into AI-driven building, we provide the `BaseWorkflow` class with:
- `task` — for LLM calling (structured or plain text)
- `create_task_tree` — builds a task + validation subtree
- `build_task_node` — wraps a task tree in a single `Node` for use in larger graphs

# Examples
### Simple text:
```python
from py_ai_toolkit import PyAIToolkit

toolkit = PyAIToolkit()
template = "./prompt.md"
response = await toolkit.chat(template)
print(response.content)
```

### Structured response:
```python
from py_ai_toolkit import PyAIToolkit
from pydantic import BaseModel

class Purchase(BaseModel):
    product: str
    quantity: int

toolkit = PyAIToolkit()
template = "./prompt.md"  # PROMPT: {{ message }}
response = await toolkit.asend(response_model=Purchase, template=template, message="I want to buy 5 apples")
print(response.content.product)   # "apple"
print(response.content.quantity)  # 5
```

### Structured response with model type injection:
```python
from py_ai_toolkit import PyAIToolkit
from pydantic import BaseModel
from typing import Literal

class Purchase(BaseModel):
    product: str
    quantity: int

toolkit = PyAIToolkit()
available_fruits = ["apple", "banana", "orange"]
FruitModel = toolkit.inject_types(Purchase, [
    ("product", Literal[tuple(available_fruits)])
])
response = await toolkit.asend(response_model=FruitModel, template="./prompt.md", message="I want to buy 5 apples")
```

### Using run_task with validation:
```python
from py_ai_toolkit import PyAIToolkit, LLMConfig
from py_ai_toolkit.core.domain.schemas import SingleShotValidationConfig
from pydantic import BaseModel

class Purchase(BaseModel):
    product: str
    quantity: int

toolkit = PyAIToolkit(main_model_config=LLMConfig())

result = await toolkit.run_task(
    template="""
        You will extract a purchase from the following message:
        {{ message }}
    """.strip(),
    response_model=Purchase,
    kwargs=dict(message="I want to buy 5 apples."),
    config=SingleShotValidationConfig(
        issues=["The identified purchase matches the user's request."],
    ),
)

print(result.product)   # "apple"
print(result.quantity)  # 5
```

### Custom workflow with validation:
```python
from py_ai_toolkit import PyAIToolkit, BaseWorkflow, Node, TreeExecutor
from py_ai_toolkit.core.domain.schemas import SingleShotValidationConfig
from pydantic import BaseModel
from typing import Literal

class Purchase(BaseModel):
    product: str
    quantity: int

toolkit = PyAIToolkit()
available_fruits = ["apple", "banana", "orange"]
FruitModel = toolkit.inject_types(Purchase, [
    ("product", Literal[tuple(available_fruits)])
])

class PurchaseWorkflow(BaseWorkflow):
    async def run(self, message: str) -> Purchase:
        executor = await self.create_task_tree(
            template="./purchase.md",
            response_model=FruitModel,
            kwargs=dict(message=message),
            config=SingleShotValidationConfig(
                issues=["The identified purchase matches the user's request."],
            ),
        )
        results = await executor.run()
        return results[0].output

workflow = PurchaseWorkflow(ai_toolkit=toolkit, error_class=ValueError)
result = await workflow.run("I want to buy 5 apples")
```

## Validation Modes

The `run_task` method supports three validation modes that control how the LLM output is validated:

### SingleShotValidationConfig
- **Count**: 1 validation attempt
- **Required Ahead**: 1 (needs 1 more success than failure)
- **Max Retries**: 3
- **Use Case**: Simple validation for straightforward tasks where a single validation check is sufficient

```python
from py_ai_toolkit.core.domain.schemas import SingleShotValidationConfig

config = SingleShotValidationConfig(
    issues=["The identified purchase matches the user's request."],
)
```

### ThresholdVotingValidationConfig
- **Count**: 3 validation attempts (default)
- **Required Ahead**: 1 (needs 1 more success than failure)
- **Use Case**: Moderate confidence validation where multiple checks provide better reliability

```python
from py_ai_toolkit.core.domain.schemas import ThresholdVotingValidationConfig

config = ThresholdVotingValidationConfig(
    issues=["The identified purchase matches the user's request."],
)
```

### KAheadVotingValidationConfig
- **Count**: 5 validation attempts (default)
- **Required Ahead**: 3 (needs 3 more successes than failures)
- **Use Case**: High-stakes validation where you need strong consensus across multiple validation checks

```python
from py_ai_toolkit.core.domain.schemas import KAheadVotingValidationConfig

config = KAheadVotingValidationConfig(
    issues=["The identified purchase matches the user's request."],
)
```

All validation configs accept an `issues` parameter — a list of validation criteria checked against the task output. Each issue is evaluated independently, and the validation passes only if all issues pass according to the configured mode.

## Recommended Docs
- `instructor` https://python.useinstructor.com/
- `jinja2` https://jinja.palletsprojects.com/en/stable/
- `pydantic` https://docs.pydantic.dev/latest/
- `grafo` https://github.com/paulomtts/grafo
