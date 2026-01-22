# Response Models

Response models define the structure of LLM outputs using Pydantic.

## Basic Response Models

Define the structure you want the LLM to return:

```python
from pydantic import BaseModel

class Product(BaseModel):
    name: str
    price: float
    in_stock: bool

response = await ait.asend(
    response_model=Product,
    template="Extract product info: {{ text }}",
    text="The laptop costs $999 and is in stock"
)

print(response.content.name)   # "laptop"
print(response.content.price)  # 999.0
```

## Nested Models

Models can contain other models:

```python
class Address(BaseModel):
    street: str
    city: str
    country: str

class User(BaseModel):
    name: str
    email: str
    address: Address

response = await ait.asend(
    response_model=User,
    template="Extract user data: {{ text }}",
    text="John lives at 123 Main St, Boston, USA. Email: john@example.com"
)
```

## Lists of Models

Extract multiple items:

```python
from typing import List

class Task(BaseModel):
    title: str
    priority: str

class TaskList(BaseModel):
    tasks: List[Task]

response = await ait.asend(
    response_model=TaskList,
    template="Extract all tasks from: {{ text }}",
    text="High priority: Fix bug. Low priority: Update docs."
)
```

## Type Injection

Dynamically modify model fields at runtime using `inject_types()`.

### Basic Example

Constrain a field to specific values:

```python
from typing import Literal

class Purchase(BaseModel):
    product: str
    quantity: int

available_products = ["apple", "banana", "orange"]

# Inject Literal type for product field
PurchaseModel = ait.inject_types(
    Purchase,
    fields=[("product", Literal[tuple(available_products)])]
)

response = await ait.asend(
    response_model=PurchaseModel,
    template="Extract purchase: {{ text }}",
    text="I want 5 apples"
)
# response.content.product will only be one of: apple, banana, orange
```

### Custom Docstrings

Add context to injected fields:

```python
FruitPurchase = ait.inject_types(
    Purchase,
    fields=[("product", Literal[tuple(available_products)])],
    docstring="A purchase of fruits from our inventory"
)
```

### Use Cases

Type injection is useful when:

- Constraining outputs to predefined options (enums)
- Dynamically adjusting schemas based on runtime data
- Enforcing domain-specific constraints
- Building type-safe APIs with LLM outputs

## Schema Reduction

Reduce token usage by simplifying model schemas:

```python
class DetailedProduct(BaseModel):
    """A product with extensive metadata"""
    name: str
    description: str
    price: float
    # ... many more fields

# Get simplified schema
schema = ait.reduce_model_schema(DetailedProduct)
print(schema)  # Compact representation

# Exclude descriptions
schema = ait.reduce_model_schema(DetailedProduct, include_description=False)
```

This is helpful for including schemas in prompts without exceeding token limits.

## Validation

Response models automatically validate LLM outputs:

```python
from pydantic import validator

class Age(BaseModel):
    value: int

    @validator('value')
    def check_age(cls, v):
        if v < 0 or v > 150:
            raise ValueError('Invalid age')
        return v

# LLM output will be validated against your constraints
response = await ait.asend(
    response_model=Age,
    template="Extract age from: {{ text }}",
    text="She is 25 years old"
)
```
