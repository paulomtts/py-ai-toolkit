# BaseWorkflow API Reference

Base class for building LLM-powered workflows using grafo DAGs.

## Constructor

```python
BaseWorkflow(
    ai_toolkit: Toolkit,
    error_class: Type[Exception],
    echo: bool = False
)
```

**Parameters:**

- `ai_toolkit` (Toolkit): Instance of Toolkit for LLM operations
- `error_class` (Type[Exception]): Exception class to raise on workflow errors
- `echo` (bool): Enable debug logging

**Example:**

```python
from py_ai_toolkit import Toolkit
from py_ai_toolkit.core.base import BaseWorkflow
from py_ai_toolkit.core.domain.errors import WorkflowError

ait = Toolkit(main_model_config=LLMConfig())

workflow = BaseWorkflow(
    ai_toolkit=ait,
    error_class=WorkflowError,
    echo=True
)
```

## Methods

### task()

Execute a single LLM task (text or structured).

```python
async def task(
    template: str | None = None,
    response_model: Type[S] | None = None,
    echo: bool = False,
    **kwargs: Any
) -> Union[str, S]
```

**Parameters:**

- `template` (str | None): Prompt template (file path or inline string)
- `response_model` (Type[S] | None): Optional Pydantic model for structured output
- `echo` (bool): Log output
- `**kwargs`: Template variables

**Returns:** Text string or model instance

**Example:**

```python
# Text response
text = await workflow.task(
    template="Summarize: {{ article }}",
    article=long_text
)

# Structured response
result = await workflow.task(
    template="Extract entities: {{ text }}",
    response_model=Entities,
    text=document
)
```

---

### create_task_tree()

Create an executable task tree with validation.

```python
async def create_task_tree(
    template: str,
    response_model: Type[S],
    kwargs: dict[str, Any],
    config: ValidationConfig = SingleShotValidationConfig(),
    echo: bool = False
) -> TreeExecutor[S | V]
```

**Parameters:**

- `template` (str): Prompt template
- `response_model` (Type[S]): Pydantic model for output
- `kwargs` (dict[str, Any]): Template variables
- `config` (ValidationConfig): Validation configuration
- `echo` (bool): Enable logging

**Returns:** `TreeExecutor` ready to run

**Example:**

```python
from py_ai_toolkit.core.domain.interfaces import ThresholdVotingValidationConfig

executor = await workflow.create_task_tree(
    template="Parse this: {{ data }}",
    response_model=ParsedData,
    kwargs=dict(data=raw_input),
    config=ThresholdVotingValidationConfig(
        issues=["Output is accurate"]
    )
)

results = await executor.run()
parsed = results[0].output
```

---

### build_task_node()

Create a standalone node containing a task tree subtree.

```python
async def build_task_node(
    uuid: str,
    template: str,
    response_model: Type[S],
    kwargs: dict[str, Any],
    config: ValidationConfig = SingleShotValidationConfig()
) -> Node[S]
```

**Parameters:**

- `uuid` (str): Unique identifier for the node
- `template` (str): Prompt template
- `response_model` (Type[S]): Output model
- `kwargs` (dict[str, Any]): Template variables
- `config` (ValidationConfig): Validation config

**Returns:** `Node[S]` that can be connected to other nodes

**Example:**

```python
node = await workflow.build_task_node(
    uuid="extraction",
    template="Extract: {{ text }}",
    response_model=ExtractedData,
    kwargs=dict(text=input_text),
    config=SingleShotValidationConfig(issues=["Complete extraction"])
)

# Connect to other nodes in larger workflow
await node.connect(another_node)
```

---

### run()

Execute the workflow.

```python
async def run(*args: Any, **kwargs: Any) -> S | V
```

**Returns:** Output from the workflow execution

**Raises:** `WorkflowError` if executor not initialized

**Example:**

```python
executor = await workflow.create_task_tree(...)
workflow.executor = executor
result = await workflow.run()
```

---

## Internal Methods

These methods are available but primarily for advanced use cases:

### _create_task_node()

Create a basic task node.

```python
def _create_task_node(
    template: str,
    uuid: str | None = None,
    response_model: Type[S] | None = None,
    echo: bool = False,
    **kwargs: Any
) -> Node[Any]
```

---

### _create_issue_node()

Create a validation issue node.

```python
def _create_issue_node(
    issue: str,
    task_node: Node[Any],
    echo: bool = False
) -> Node[V]
```

---

## State Management

The workflow maintains internal state:

- `current_retries` (int): Current retry count
- `executor` (TreeExecutor | None): Active executor
- `failure_reasonings` (dict[str, list[str]]): Collected validation failures

These are managed automatically but can be accessed for debugging or custom extensions.

## Extending BaseWorkflow

Create custom workflows by subclassing:

```python
class MyWorkflow(BaseWorkflow):
    async def run(self, input_data: str) -> Output:
        # Custom orchestration logic
        node1 = self._create_task_node(...)
        node2 = self._create_task_node(...)

        await node1.connect(node2)

        executor = TreeExecutor(uuid="my_workflow", roots=[node1])
        results = await executor.run()

        return results[-1].output
```

## Integration with Grafo

`BaseWorkflow` wraps [grafo](https://github.com/paulomtts/grafo) functionality:

- **Node**: Represents a single operation (LLM call, validation, etc.)
- **TreeExecutor**: Orchestrates node execution respecting dependencies
- **DAG structure**: Nodes connected via `.connect()` form the execution graph

You can use grafo's full capabilities alongside `BaseWorkflow` methods for maximum flexibility.
