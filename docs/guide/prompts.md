# Prompts

The toolkit uses Jinja2-based templates for flexible prompt management.

## Template Basics

You can provide prompts in two ways:

### Inline Strings

```python
response = await ait.chat(
    template="Translate '{{ text }}' to {{ language }}.",
    text="Hello, world!",
    language="Spanish"
)
```

### Template Files

**prompts/translate.md:**
```markdown
You are a professional translator.

Translate the following text to {{ language }}:

{{ text }}
```

**Usage:**
```python
response = await ait.chat(
    template="./prompts/translate.md",
    text="Hello, world!",
    language="Spanish"
)
```

## Variable Interpolation

Pass any keyword arguments to inject variables:

```python
await ait.chat(
    template="Summarize: {{ article }}",
    article=long_article_text
)
```

## Pydantic Model Serialization

Pydantic models are automatically serialized to JSON:

```python
class User(BaseModel):
    name: str
    age: int

user = User(name="Alice", age=30)

response = await ait.chat(
    template="Generate a greeting for: {{ user }}",
    user=user  # Automatically converted to JSON
)
```

Lists of Pydantic models are also handled:

```python
users = [User(name="Alice", age=30), User(name="Bob", age=25)]

response = await ait.chat(
    template="Summarize these users: {{ users }}",
    users=users  # Converts to JSON array
)
```

## System Prompts

Templates are automatically injected as system messages:

```python
# This becomes a system message
template = """
You are an expert programmer.
Help the user with: {{ task }}
"""

response = await ait.chat(template=template, task="debugging")
```

## Path Detection

The toolkit automatically detects whether your template is a file path or inline string:

```python
# File path (if file exists)
await ait.chat(template="./prompts/task.md", ...)

# Inline string (if file doesn't exist)
await ait.chat(template="Do this: {{ task }}", ...)
```

## Previous Evaluations

When using validation with retries, previous failure reasons are automatically appended to help the LLM improve:

```python
# Internally handled by run_task
# On retry, the prompt includes:
# """
# # Previous Evaluations
# You have attempted this task before and failed because of the following:
# <failure reasons>
#
# Use this information to improve your next attempt.
# """
```

This is managed automatically by the validation system (see [Running Tasks](running-tasks.md#validation-modes)).
