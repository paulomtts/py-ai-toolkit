# Workflows

Workflows enable complex, multi-step LLM orchestration using the `BaseWorkflow` class built on [grafo](https://github.com/paulomtts/grafo).

## What are Workflows?

Workflows represent task execution as directed acyclic graphs (DAGs), where:

- **Nodes** contain async coroutines (LLM calls, validations, data processing)
- **Edges** define execution dependencies
- **Executors** manage parallel and sequential execution

This abstraction fits naturally with AI-driven tasks, where outputs from one LLM call often feed into another.

## BaseWorkflow

The `BaseWorkflow` class provides conveniences for building LLM-powered workflows:

```python
from py_ai_toolkit import PyAIToolkit
from py_ai_toolkit.core.base import BaseWorkflow
from py_ai_toolkit.core.domain.errors import WorkflowError

ait = PyAIToolkit(main_model_config=LLMConfig())

workflow = BaseWorkflow(
    ai_toolkit=ait,
    error_class=WorkflowError,
    echo=False  # Set True for debug logging
)
```

## Simple Task Execution

Use the `task()` method for individual LLM calls within workflows:

```python
# Text response
result = await workflow.task(
    template="Summarize: {{ text }}",
    text=long_article
)

# Structured response
result = await workflow.task(
    template="Extract entities from: {{ text }}",
    response_model=Entities,
    text=document
)
```

## Building Task Trees

Create complex workflows with validation using `create_task_tree()`:

```python
from py_ai_toolkit.core.domain.schemas import SingleShotValidationConfig

executor = await workflow.create_task_tree(
    template="Extract purchase intent: {{ message }}",
    response_model=Purchase,
    kwargs=dict(message="I want 5 apples"),
    config=SingleShotValidationConfig(
        issues=["The purchase matches the user's request"]
    )
)

results = await executor.run()
purchase = results[0].output
```

This creates a task node with automatic validation and retry logic.

## Manual Node Creation

For fine-grained control, create nodes manually:

```python
from grafo import Node, TreeExecutor

# Create task node
task_node = Node[Purchase](
    uuid="purchase_extraction",
    coroutine=workflow.task,
    kwargs=dict(
        template="Extract purchase: {{ message }}",
        response_model=Purchase,
        message="I want 3 bananas"
    )
)

# Create dependent node
summary_node = Node[str](
    uuid="purchase_summary",
    coroutine=workflow.task,
    kwargs=dict(
        template="Summarize this purchase: {{ purchase }}",
        purchase=task_node.output  # Uses output from task_node
    )
)

# Connect nodes
await task_node.connect(summary_node)

# Execute workflow
executor = TreeExecutor(uuid="purchase_workflow", roots=[task_node])
results = await executor.run()
```

## Parallel Execution

Execute independent tasks concurrently:

```python
# Create multiple independent nodes
node1 = Node(uuid="task1", coroutine=workflow.task, kwargs={...})
node2 = Node(uuid="task2", coroutine=workflow.task, kwargs={...})
node3 = Node(uuid="task3", coroutine=workflow.task, kwargs={...})

# All nodes run in parallel
executor = TreeExecutor(uuid="parallel_tasks", roots=[node1, node2, node3])
results = await executor.run()
```

## Sequential with Branching

Combine sequential and parallel patterns:

```python
# Initial task
extract_node = Node(uuid="extract", coroutine=workflow.task, kwargs={...})

# Parallel analysis tasks
sentiment_node = Node(uuid="sentiment", coroutine=workflow.task, kwargs={...})
entities_node = Node(uuid="entities", coroutine=workflow.task, kwargs={...})

# Final synthesis
synthesis_node = Node(uuid="synthesis", coroutine=workflow.task, kwargs={...})

# Build graph
await extract_node.connect(sentiment_node)
await extract_node.connect(entities_node)
await sentiment_node.connect(synthesis_node)
await entities_node.connect(synthesis_node)

executor = TreeExecutor(uuid="analysis_workflow", roots=[extract_node])
await executor.run()
```

## Validation Integration

Workflows automatically integrate validation (see [Running Tasks](running-tasks.md)):

```python
executor = await workflow.create_task_tree(
    template="...",
    response_model=MyModel,
    kwargs={...},
    config=ThresholdVotingValidationConfig(
        issues=["Output is accurate", "Format is correct"],
        max_retries=3
    )
)
```

The workflow handles:

- Running validation nodes after task nodes
- Collecting failure reasons
- Retrying with feedback
- Redirecting flow on validation failure

## Custom Workflows

Extend `BaseWorkflow` for domain-specific needs:

```python
class DataProcessingWorkflow(BaseWorkflow):
    async def run(self, data: str) -> ProcessedData:
        # Custom orchestration logic
        extract_node = self._create_task_node(
            template="Extract data: {{ input }}",
            response_model=RawData,
            input=data
        )

        # ... build workflow graph

        executor = TreeExecutor(uuid="data_processor", roots=[extract_node])
        results = await executor.run()
        return results[0].output
```

## Learn More

- [grafo documentation](https://github.com/paulomtts/grafo) for advanced DAG patterns
- [Running Tasks](running-tasks.md) for validation and task tree details
