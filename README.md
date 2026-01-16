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
- Easy prompting - you need only provide a path or a template
- Calling LLMs - instructor takes care of that for us
- Modifying response models - we use Pydantic (duh)

Additionally, we provide `grafo` out of the box for convenient workflow building.

## About Grafo
Grafo (see Recommended Docs below) is a library for building executable DAGs where each node contains a coroutine. Since the DAG abstraction fits particularly well into AI-driven building, we have provided the `BaseWorkflow` class with the following methods:
- `task` for LLM calling
- `redirect` to help you manage redirections in your `grafo` workflows

# Examples
### Simple text:
```python
from py_ai_toolkit import AIT

ait = AIT("gpt-5")
template = "./prompt.md"
response = ait.chat(template)
print(response.completion)
print(response.content)
```

### Structured response:
```python
from py_ai_toolkit import AIT
from pydantic import BaseModel

class Purchase(BaseModel):
    product: str
    quantity: int

ait = AIT("gpt-5")
template = "./prompt.md" # PROMPT: {{ message }}
message = "I want to buy 5 apples"
response = ait.asend(response_model=Fruit, template=template, message=message)
```

### Structured response with model type injection:
```python
from py_ai_toolkit import AIT
from pydantic import BaseModel

class Purchase(BaseModel):
    product: str
    quantity: int

ait = AIT("gpt-5")
template = "./prompt.md" # PROMPT: {{ message }}
message = "I want to buy 5 apples"
available_fruits = ["apple", "banana", "orange"]
FruitModel = ait.inject_types(Purchase, [
    ("product", Literal[tuple(available_fruits)])
])
response = ait.asend(response_model=Purchase, template=template, message=message)
```

### Using run_task with validation:
```python
from py_ai_toolkit import PyAIToolkit
from py_ai_toolkit.core.domain.interfaces import (
    LLMConfig,
    SingleShotValidationConfig,
)
from pydantic import BaseModel

class Purchase(BaseModel):
    product: str
    quantity: int

ai_toolkit = PyAIToolkit(main_model_config=LLMConfig())

result = await ai_toolkit.run_task(
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

print(result.product)  # "apple"
print(result.quantity)  # 5
```

### Simple workflow:
```python
from py_ai_toolkit import AIT, BaseWorkflow, BaseValidation, Node, TreeExecutor
from pydantic import BaseModel
from typing import Literal

class Purchase(BaseModel):
    product: str
    quantity: int

ait = AIT("gpt-5")
prompts_path = "./"
message = "I want to buy 5 apples"
available_fruits = ["apple", "banana", "orange"]
FruitModel = ait.inject_types(Purchase, [
    ("product", Literal[tuple(available_fruits)])
])

class PurchaseWorkflow(BaseWorkflow):
    def __init__(...):
        ...

    async def run(self, message) -> Purchase:
        purchase_node = Node[FruitModel](
            uuid="fruit purchase node",
            coroutine=self.task,
            kwargs=dict(
                template=f"{prompts_path}/purchase.md",
                response_model=FruitModel,
                message=message,
            )
        )
        validation_node = self.create_validation_node(
            input=message,
            output=purchase_node.output,
            issues=["The identified purchase matches the user's request."],
            source_node=purchase_node,
        )

        await purchase_node.connect(validation_node)
        executor = TreeExecutor(uuid="Purchase Workflow", roots=[purchase_node])
        await executor.run()

        if not purchase_node.output or not validation_node.output:
            raise ValueError("Purchase validation failed.")

        if not validation_node.output.valid:
            raise ValueError("Purchase failed validation.")

        return purchase_node.output
```

## Validation Modes

The `run_task` method supports three validation modes that control how the LLM output is validated:

### SingleShotValidationConfig
- **Count**: 1 validation attempt
- **Required Ahead**: 1 (needs 1 more success than failure)
- **Max Retries**: 3
- **Use Case**: Simple validation for straightforward tasks where a single validation check is sufficient

```python
from py_ai_toolkit.core.domain.interfaces import SingleShotValidationConfig

config = SingleShotValidationConfig(
    issues=["The identified purchase matches the user's request."],
)
```

### ThresholdVotingValidationConfig
- **Count**: 3 validation attempts (default)
- **Required Ahead**: 1 (needs 1 more success than failure)
- **Use Case**: Moderate confidence validation where multiple checks provide better reliability

```python
from py_ai_toolkit.core.domain.interfaces import ThresholdVotingValidationConfig

config = ThresholdVotingValidationConfig(
    issues=["The identified purchase matches the user's request."],
)
```

### KAheadVotingValidationConfig
- **Count**: 5 validation attempts (default)
- **Required Ahead**: 3 (needs 3 more successes than failures)
- **Use Case**: High-stakes validation where you need strong consensus across multiple validation checks

```python
from py_ai_toolkit.core.domain.interfaces import KAheadVotingValidationConfig

config = KAheadVotingValidationConfig(
    issues=["The identified purchase matches the user's request."],
)
```

All validation configs accept an `issues` parameter, which is a list of validation criteria that will be checked against the task output. Each issue is evaluated independently, and the validation passes only if all issues pass according to the configured mode.

## Recommended Docs
- `instructor` https://python.useinstructor.com/
- `jinja2` https://jinja.palletsprojects.com/en/stable/
- `pydantic` https://docs.pydantic.dev/latest/
- `grafo` https://github.com/paulomtts/grafo