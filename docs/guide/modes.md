# Modes of Interaction

The toolkit provides three primary methods for interacting with LLMs, each suited to different use cases.

## chat() - Text Responses

Use `chat()` for simple text-based responses:

```python
response = await ait.chat(
    template="Write a haiku about {{ topic }}",
    topic="mountains"
)

print(response.content)  # Plain text response
print(response.completion)  # Raw OpenAI completion object
```

**Use when:**

- You need unstructured text output
- The response format is flexible
- You're doing creative or open-ended tasks

## asend() - Structured Responses

Use `asend()` for type-safe, structured outputs:

```python
class Analysis(BaseModel):
    sentiment: str
    confidence: float

response = await ait.asend(
    response_model=Analysis,
    template="Analyze sentiment: {{ text }}",
    text="This product is amazing!"
)

print(response.content.sentiment)    # Type-safe access
print(response.content.confidence)   # IDE autocomplete works
```

**Use when:**

- You need predictable, structured data
- Type safety matters
- You're building APIs or data pipelines
- You want IDE autocomplete and type checking

## stream() - Streaming Responses

Use `stream()` for real-time text generation:

```python
async for chunk in ait.stream(
    template="Write a story about {{ topic }}",
    topic="time travel"
):
    print(chunk.content, end="", flush=True)
```

**Use when:**

- Building interactive UIs
- Showing progress to users
- Reducing perceived latency
- Processing long-form content incrementally

## run_task() - Validated Execution

Use `run_task()` for high-reliability structured outputs with validation:

```python
result = await ait.run_task(
    template="Extract key points from: {{ article }}",
    response_model=Summary,
    kwargs=dict(article=article_text),
    config=SingleShotValidationConfig(
        issues=["All main points are captured"]
    )
)
```

**Use when:**

- Output correctness is critical
- You need automatic retries
- Quality assurance is important
- Building production systems

See [Running Tasks](running-tasks.md) for details on validation.

## Embeddings

Generate vector embeddings for semantic search or similarity:

```python
response = await ait.embed("Machine learning is fascinating")
vector = response.embedding  # list[float]
usage = response.usage       # EmbeddingUsage with .prompt_tokens, .total_tokens
```

For batch operations (RAG ingestion, knowledge-graph grounding), use `embed_batch()` to send multiple texts in a single API request:

```python
responses = await ait.embed_batch(["Machine learning", "Deep learning", "NLP"])
vectors = [r.embedding for r in responses]
```

**Use when:**

- Building semantic search
- Doing similarity comparisons
- Creating recommendation systems
- Clustering or classification tasks

## Comparison

| Method | Output Type | Validation | Streaming | Use Case |
|--------|-------------|------------|-----------|----------|
| `chat()` | Text | No | No | Simple text generation |
| `asend()` | Structured | No | No | Type-safe data extraction |
| `stream()` | Text | No | Yes | Interactive UIs |
| `run_task()` | Structured | Yes | No | Production workflows |
| `embed()` | EmbeddingResponse | N/A | No | Single text embedding |
| `embed_batch()` | list[EmbeddingResponse] | N/A | No | Batch text embedding |

## Alternative Models

When using `asend()`, you can leverage alternative models for load balancing:

```python
ait = PyAIToolkit(
    main_model_config=LLMConfig(model="gpt-4"),
    alternative_models_configs=[
        LLMConfig(model="gpt-4"),
        LLMConfig(model="claude-3-sonnet")
    ]
)

# Randomly selects from alternative_models_configs
response = await ait.asend(response_model=MyModel, ...)
```

Note that `chat()` and `stream()` always use the main model, while `asend()` randomly selects from alternative models if provided.
