# Getting Started

This guide will walk you through setting up and making your first LLM calls with py-ai-toolkit.

## Installation

Install using `uv`:

```bash
uv add py-ai-toolkit
```

Or with `pip`:

```bash
pip install py-ai-toolkit
```

## Configuration

The toolkit requires an LLM configuration. You can provide this via environment variables or directly in code.

### Environment Variables

```bash
export LLM_MODEL="gpt-4"
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"  # optional
export EMBEDDING_MODEL="text-embedding-3-small"  # optional
```

### Programmatic Configuration

```python
from py_ai_toolkit import PyAIToolkit
from py_ai_toolkit.core.domain.interfaces import LLMConfig

ait = PyAIToolkit(
    main_model_config=LLMConfig(
        model="gpt-4",
        api_key="your-api-key",
        base_url="https://api.openai.com/v1",  # optional
        embedding_model="text-embedding-3-small"  # optional
    )
)
```

## Your First LLM Call

### Simple Text Response

```python
from py_ai_toolkit import PyAIToolkit
from py_ai_toolkit.core.domain.interfaces import LLMConfig

ait = PyAIToolkit(main_model_config=LLMConfig())

response = await ait.chat(
    template="Explain what {{ topic }} means in one sentence.",
    topic="machine learning"
)

print(response.content)  # Text response from the LLM
```

### Structured Response

For structured outputs, define a Pydantic model:

```python
from pydantic import BaseModel

class Explanation(BaseModel):
    topic: str
    explanation: str
    complexity: int  # 1-10 scale

response = await ait.asend(
    response_model=Explanation,
    template="Explain {{ topic }} and rate its complexity from 1-10.",
    topic="quantum computing"
)

print(response.content.explanation)
print(f"Complexity: {response.content.complexity}/10")
```

## Using Template Files

Instead of inline templates, you can use template files:

**prompts/explain.md:**
```markdown
You are a helpful teacher.

Explain {{ topic }} in simple terms for a {{ audience }} audience.
Be concise but accurate.
```

**Python code:**
```python
response = await ait.chat(
    template="./prompts/explain.md",
    topic="neural networks",
    audience="beginner"
)
```

## Alternative Models

You can configure multiple models for load balancing:

```python
ait = PyAIToolkit(
    main_model_config=LLMConfig(model="gpt-4"),
    alternative_models_configs=[
        LLMConfig(model="gpt-4"),
        LLMConfig(model="claude-3-sonnet")
    ]
)
```

When using `asend()`, the toolkit will randomly select from the alternative models if provided.

## Next Steps

- Learn about [Prompts](guide/prompts.md) and template management
- Explore [Response Models](guide/response-models.md) and type injection
- Understand [Modes of Interaction](guide/modes.md) with LLMs
- Build [Workflows](guide/workflows.md) for complex tasks
