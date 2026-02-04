# py-ai-toolkit

A streamlined toolkit for building AI-driven software with LLMs.

## What is py-ai-toolkit?

**py-ai-toolkit** bundles together essential utilities and patterns for working with Large Language Models into a cohesive, easy-to-use package. Instead of piecing together different tools and libraries, you get a unified interface for:

- **Prompt management** - Template-based prompting with Jinja2
- **LLM interactions** - Structured responses via instructor
- **Response models** - Dynamic Pydantic model manipulation
- **Workflow orchestration** - DAG-based task execution with grafo

## Why Use This Toolkit?

Building AI-driven applications requires juggling multiple concerns: prompt formatting, HTTP requests to LLM APIs, structured output parsing, and complex workflow management. This toolkit consolidates these needs into simple, composable methods.

Rather than managing each piece separately, you can focus on your application logic while the toolkit handles the plumbing.

## Key Features

### Simple LLM Calling
```python
ait = Toolkit(main_model_config=LLMConfig())
response = await ait.chat(template="./prompt.md", message="Hello!")
```

### Structured Responses
```python
class Purchase(BaseModel):
    product: str
    quantity: int

response = await ait.asend(
    response_model=Purchase,
    template="Extract purchase from: {{ message }}",
    message="I want 5 apples"
)
```

### Validated Task Execution
```python
result = await ait.run_task(
    template="Extract a purchase from: {{ message }}",
    response_model=Purchase,
    kwargs=dict(message="I want 5 apples"),
    config=SingleShotValidationConfig(
        issues=["The purchase matches the user's request"]
    )
)
```

### Workflow Building
```python
workflow = BaseWorkflow(ai_toolkit=ait, error_class=WorkflowError)
task_tree = await workflow.create_task_tree(
    template="...",
    response_model=MyModel,
    kwargs={...},
    config=ValidationConfig()
)
```

## Quick Start

Install the package:

```bash
uv add py-ai-toolkit
```

Then jump into the [Getting Started](getting-started.md) guide.

## Philosophy

This toolkit embraces **composition over complexity**. Each component serves a clear purpose and works independently, while integrating seamlessly when combined. You're not locked into a framework - you can use as much or as little as you need.
