# Running Tasks

The `run_task()` method provides a high-level interface for executing validated LLM tasks with automatic retry logic.

## Basic Usage

Execute a task with validation:

```python
result = await ait.run_task(
    template="Extract purchase from: {{ message }}",
    response_model=Purchase,
    kwargs=dict(message="I want 5 apples"),
    config=SingleShotValidationConfig(
        issues=["The purchase matches the user's request"]
    )
)

print(result.product)   # Direct access to validated output
print(result.quantity)
```

## About Grafo

Under the hood, `run_task()` uses [grafo](https://github.com/paulomtts/grafo), a library for building executable DAGs (directed acyclic graphs). Each node in the graph contains an async coroutine, and grafo orchestrates execution respecting dependencies.

**Why grafo?** The DAG abstraction naturally maps to AI workflows:

- Nodes represent LLM calls, validations, or data transformations
- Edges define execution order and data flow
- The executor handles parallel and sequential execution automatically

You don't need to understand grafo to use `run_task()`, but it powers the validation and retry logic described below.

## The Task Tree

When you call `run_task()`, it creates a task tree:

```
┌─────────────┐
│  Task Node  │  (Executes LLM call with template)
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Validation Node │  (Runs issue validations)
└──────┬──────────┘
       │
       ▼
  ┌────────┐
  │ Retry? │  (Redirects to task node if validation fails)
  └────────┘
```

**Flow:**

1. **Task Node** executes the LLM call with your template and kwargs
2. **Validation Node** runs configured issue validations on the output
3. **Redirect Logic** determines whether to retry based on validation results and max_retries

If validation fails and retries remain, the task node is re-executed with feedback from previous failures appended to the prompt.

## Validation Modes

The toolkit provides three validation strategies that control how LLM outputs are verified.

### SingleShotValidationConfig

Single validation attempt with retries on failure.

```python
config = SingleShotValidationConfig(
    issues=["The output matches the request"],
    max_retries=3  # Will retry up to 3 times
)
```

**Parameters:**

- `count`: 1 (fixed)
- `required_ahead`: 1 (must succeed)
- `max_retries`: 3 (default)

**Use when:** Simple validation for straightforward tasks where one check is sufficient.

### ThresholdVotingValidationConfig

Multiple validators vote; output is valid if successes outnumber failures by a threshold.

```python
config = ThresholdVotingValidationConfig(
    issues=["Output is accurate", "Format is correct"],
    count=3,  # 3 validation attempts per issue
    required_ahead=1,  # Need 1 more success than failure
    max_retries=2
)
```

**Parameters:**

- `count`: 3 (default, must be odd)
- `required_ahead`: 1 (default)
- `max_retries`: 0 (default, no retries)

**Use when:** You need moderate confidence through consensus voting across multiple validators.

### KAheadVotingValidationConfig

High-consensus validation requiring strong agreement across many validators.

```python
config = KAheadVotingValidationConfig(
    issues=["Critical accuracy requirement"],
    count=5,  # 5 validation attempts
    required_ahead=3,  # Need 3 more successes than failures
    max_retries=2
)
```

**Parameters:**

- `count`: 5 (default, must be odd)
- `required_ahead`: 3 (default)
- `max_retries`: 0 (default, no retries)

**Use when:** High-stakes scenarios requiring strong validation consensus.

## Issues

The `issues` parameter defines validation criteria:

```python
config = SingleShotValidationConfig(
    issues=[
        "The extracted data is complete",
        "The format matches requirements",
        "No hallucinated information is present"
    ]
)
```

Each issue is evaluated independently by an LLM-based validator. The validation passes only if **all issues pass** according to the configured mode's voting rules.

### How Issue Validation Works

For each issue:

1. The toolkit creates an `IssueNode` with a custom-generated Pydantic model
2. The validator LLM evaluates the task output against the issue
3. The validator returns `is_valid` (bool) and `reasoning` (str)
4. Votes are aggregated according to the validation mode

If any issue fails, the entire validation fails (unless retries are available).

## Retries with Feedback

When validation fails and retries remain, the task node is re-executed with feedback:

```python
# On retry, the prompt automatically includes:
"""
# Previous Evaluations
You have attempted this task before and failed because of the following:

## Output
<previous output JSON>

## Failure Reasonings
<collected failure reasons from validators>

Use this information to improve your next attempt.
"""
```

This gives the LLM context about previous failures, improving success rates on retries.

## Voting Logic

**ThresholdVoting:**

- Runs `count` validators per issue
- If `successes - failures >= required_ahead`: issue passes
- If `failures - successes >= required_ahead`: issue fails

**KAheadVoting:**

- Similar to ThresholdVoting but typically requires larger consensus margins
- Runs validation rounds until a clear decision is reached
- If no clear winner after `count` attempts, continues until ahead threshold is met

## Example: Production Task

```python
from py_ai_toolkit.core.domain.schemas import ThresholdVotingValidationConfig

result = await ait.run_task(
    template="""
        Extract structured product information from this listing:
        {{ listing }}
    """,
    response_model=Product,
    kwargs=dict(listing=raw_product_listing),
    config=ThresholdVotingValidationConfig(
        issues=[
            "All product details are accurately extracted",
            "Price is in correct format",
            "No information is hallucinated"
        ],
        count=3,
        required_ahead=1,
        max_retries=2
    ),
    echo=True  # Enable logging for debugging
)
```

This configuration:

- Runs 3 validators per issue (9 validators total)
- Requires 2+ successes out of 3 for each issue
- Retries up to 2 times with feedback if validation fails
- Logs execution details when `echo=True`

## When to Use run_task()

Use `run_task()` when:

- Output correctness is critical
- You need automatic validation and retries
- Building production systems with quality requirements
- Handling unreliable or complex extractions

For simpler use cases without validation, use `asend()` directly (see [Modes of Interaction](modes.md)).
