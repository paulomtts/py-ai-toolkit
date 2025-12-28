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
- Easy prompting - you need only provide a path
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
path = "./prompt.md"
response = ait.chat(path)
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
path = "./prompt.md" # PROMPT: {{ message }}
message = "I want to buy 5 apples"
response = ait.asend(response_model=Fruit, path=path, message=message)
```

### Structured response with model type injection:
```python
from py_ai_toolkit import AIT
from pydantic import BaseModel

class Purchase(BaseModel):
    product: str
    quantity: int

ait = AIT("gpt-5")
path = "./prompt.md" # PROMPT: {{ message }}
message = "I want to buy 5 apples"
available_fruits = ["apple", "banana", "orange"]
FruitModel = ait.inject_types(Purchase, [
    ("product", Literal[tuple(available_fruits)])
])
response = ait.asend(response_model=Purchase, path=path, message=message)
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
                path=f"{prompts_path}/purchase.md",
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

## Recommended Docs
- `instructor` https://python.useinstructor.com/
- `jinja2` https://jinja.palletsprojects.com/en/stable/
- `pydantic` https://docs.pydantic.dev/latest/
- `grafo` https://github.com/paulomtts/grafo