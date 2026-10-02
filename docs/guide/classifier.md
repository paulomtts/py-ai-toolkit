# Classifier

The toolkit can classify content with Jev, TypeSafe AI's classifier. Jev answers structured questions about a piece of content, called the `state` (a `str`, `dict` or `list`): yes/no questions, single-choice questions and scored questions. It cannot generate text. There is no chat, stream or embed on the classifier; use the LLM methods for those.

!!! note "Early access"
    Jev has been in pre-GA early access since 2026-09-15. Its API and models may change before general availability.

## Installation

The classifier lives behind an optional extra:

```bash
pip install 'py-ai-toolkit[jev]'
```

The `jev` extra installs `typesafe-sdk>=0.6.0`. If the extra is missing and a classifier would be built, `PyAIToolkit(...)` raises `ImportError` at construction with the hint `pip install 'py-ai-toolkit[jev]'`.

## Configuration

Settings live in `ClassifierConfig`. Every field is optional:

```python
class ClassifierConfig(BaseModel):
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
```

Each field falls back to an environment variable:

| Field | Environment variable | Default |
|---|---|---|
| `api_key` | `CLASSIFIER_API_KEY` | none |
| `model` | `CLASSIFIER_MODEL` | `"jev-latest"` |
| `base_url` | `CLASSIFIER_BASE_URL` | the SDK's default endpoint |

The environment is read once, in `PyAIToolkit.__init__`. Resolution is field by field: an explicit config value beats its environment variable, and an unset field falls back to the environment.

```python
from py_ai_toolkit import PyAIToolkit, ClassifierConfig

toolkit = PyAIToolkit(
    classifier_config=ClassifierConfig(api_key="your-jev-api-key"),
)
```

With `CLASSIFIER_API_KEY` set in the environment, no config is needed:

```python
toolkit = PyAIToolkit()
```

### When a classifier is built

- A classifier is built only if you pass a `classifier_config` or `CLASSIFIER_API_KEY` is set. Otherwise `toolkit.classifier is None`, and `classify()` raises `ClassifierAdapterError`.
- If you pass a `classifier_config` and neither it nor the environment provides an API key, the constructor raises `ValueError("ClassifierConfig requires an api_key or CLASSIFIER_API_KEY.")`.
- If the `jev` extra is not installed, the constructor raises `ImportError`.

## Asking Questions

```python
async def classify(
    state: str | dict | list,
    questions: Mapping[str, Question],
    *,
    hooks: Hooks | None = None,
) -> ClassifierResponse
```

`questions` maps a name you choose to a question. The response holds one answer per name in `response.answers`, plus typed views: `response.nouls`, `response.choices` and `response.scores`. One call can mix all three question types.

### Noul (yes/no)

A `NoulQuestion` asks whether something is true. Its optional `NoulCriteria` describes what counts as true and false.

```python
from py_ai_toolkit import NoulQuestion
from py_ai_toolkit.core.domain.classifier import NoulCriteria

response = await toolkit.classify(
    state="Hi, I was charged twice for my March invoice. Please refund one of the charges.",
    questions={
        "is_refund_request": NoulQuestion(
            instructions="Is the customer asking for money back?",
            criteria=NoulCriteria(
                true="The customer asks for a refund, chargeback or credit.",
                false="The customer asks for anything else.",
            ),
        ),
    },
)

answer = response.nouls["is_refund_request"]
print(answer.noul)  # float - the raw value from Jev, unchanged
```

### Choice

A `ChoiceQuestion` picks exactly one option. `criteria` maps each option name to a description (1 to 255 options).

```python
from py_ai_toolkit import ChoiceQuestion

response = await toolkit.classify(
    state={
        "subject": "Can't log in",
        "body": "The password reset link in your email has expired twice.",
    },
    questions={
        "department": ChoiceQuestion(
            instructions="Which team should handle this ticket?",
            criteria={
                "billing": "Payments, invoices and refunds.",
                "account": "Login, passwords and profile settings.",
                "technical": "Bugs, errors and outages.",
                "none": "None of the above.",
            },
        ),
    },
)

answer = response.choices["department"]
print(answer.choice)         # str - the selected option name
print(answer.probabilities)  # dict[str, float] - one entry per option
print(answer.confidence)     # float
```

### Score

A `ScoreQuestion` places the state on a scale. `criteria` lists the levels in order (2 to 10 levels).

```python
from py_ai_toolkit import ScoreQuestion

response = await toolkit.classify(
    state="The app crashes every time I open it and I have lost a day of work.",
    questions={
        "urgency": ScoreQuestion(
            instructions="How urgent is this ticket?",
            criteria=["Not urgent", "Somewhat urgent", "Urgent", "Critical"],
        ),
    },
)

answer = response.scores["urgency"]
print(answer.score)          # float - the raw score from Jev, unchanged
print(answer.probabilities)  # dict[int, float] - keyed by level
print(answer.confidence)     # float
print(answer.legend)         # dict[int, ...] - level -> the criterion you passed
```

Levels are `int` keys. Use `legend` to map a level back to its criterion instead of assuming a numbering base.

## Raw Values

The toolkit passes Jev's numbers through unchanged. Nothing is normalized, rescaled or derived.

- `NoulAnswer` has no confidence. The `noul` value itself is what you threshold.
- `confidence` on a `ChoiceAnswer` and `confidence` on a `ScoreAnswer` come from different question types and are not comparable with each other. Do not rank, average or threshold them as if they were the same quantity.
- Do not derive a confidence figure from `noul` or from the probabilities. The toolkit does not provide one, and any such figure is yours, not Jev's.

## Patterns

### Add a "none" option to choices

A `ChoiceQuestion` is single-select and cannot abstain: it always returns one of your options. If the state may match none of them, add an explicit catch-all option, as in the `"none"` entry above, and check for it:

```python
if response.choices["department"].choice == "none":
    send_to_triage()
```

### Threshold noul directly

Compare `noul` to a threshold you choose from your own labelled examples:

```python
if response.nouls["is_refund_request"].noul >= 0.8:
    route_to_refunds()
```

### Always set instructions

`instructions` is optional on every question type, but always set it. A clear instruction tells Jev what the question means; the criteria alone often do not. This is a recommendation and is not enforced.

## Validation

Questions are pydantic models, so invalid questions raise `pydantic.ValidationError` when you construct them, before any call:

- `ChoiceQuestion.criteria` needs 1 to 255 entries.
- `ScoreQuestion.criteria` needs 2 to 10 entries.

```python
from pydantic import ValidationError

from py_ai_toolkit import ScoreQuestion

try:
    ScoreQuestion(criteria=["only one level"])
except ValidationError as exc:
    print(exc)
```

`classify()` does not check your question names, so use non-empty string names. Answer names on `ClassifierResponse` are validated: a response with an empty answer name fails validation.

## Errors

| Condition | Raised | When |
|---|---|---|
| No classifier configured | `ClassifierAdapterError` | at `classify()` |
| `questions` is empty | `ValueError("questions must not be empty.")` | at `classify()` |
| Any SDK or API failure | `ClassifierAdapterError` | at `classify()` |
| `classifier_config` passed, no API key anywhere | `ValueError` | at `PyAIToolkit(...)` |
| `jev` extra not installed | `ImportError` | at `PyAIToolkit(...)` |
| Invalid question | `pydantic.ValidationError` | at question construction |

The unconfigured message is:

```text
Classifier not configured: pass ClassifierConfig (or set CLASSIFIER_API_KEY) and install `py-ai-toolkit[jev]`.
```

Every SDK or API failure is raised as `ClassifierAdapterError`, with the original `typesafe_sdk` exception on `__cause__`:

- Authentication failure (invalid or missing API key).
- Unprocessable entity: the request was rejected as invalid; the message includes the response body.
- Rate limit: the message includes `retry_after_ms`.
- Internal server error: Jev is unavailable or overloaded.
- Connection failure or timeout.
- Response validation: Jev returned a malformed response; the message includes the `field_path`.
- Any other `TypeSafeError`.

```python
from py_ai_toolkit import ClassifierAdapterError

try:
    response = await toolkit.classify(state, questions)
except ClassifierAdapterError as exc:
    print(exc)
    original = exc.__cause__  # the typesafe_sdk exception, or None when unconfigured
```

The SDK retries failed requests by default (2 retries within a 30 s budget). The toolkit adds no retry logic of its own.

## Hooks

`classify()` fires two hooks: `before_classify` (before the classifier call) and `after_classify` (after a successful response). See the [Hooks guide](hooks.md) for their context objects and when they fire.

```python
from py_ai_toolkit import Hooks
from py_ai_toolkit.core.hooks import AfterClassifyContext

async def log_classify(ctx: AfterClassifyContext) -> None:
    print(f"[{ctx.model}] {ctx.usage.input_tokens} input tokens in {ctx.elapsed_ms:.0f}ms")

response = await toolkit.classify(
    state,
    questions,
    hooks=Hooks(after_classify=log_classify),
)
```

## Closing the Client

The classifier holds an HTTP client. Release it when you are done:

```python
await toolkit.aclose()
```

`aclose()` closes only the classifier. It is a no-op when no classifier is configured.

## Limitations

- Jev is weak at arithmetic and dates. Compute those in code and put the result in the `state`.
- Noisy context degrades answers. Send only the content the question needs.
- Adversarial content, such as text written to steer the classifier, can skew answers.
- The context window is bounded. The toolkit does not split or truncate long states for you.
- Portuguese support is undocumented. Validate on your own data before relying on it.
- Not provided: an LLM-backed or fallback classifier, chat/stream/embed on the classifier, streaming, a sync client, normalized or derived confidence, and retry logic beyond the SDK's own.

## Data Privacy

!!! warning "Third-party processor"
    The `state` you classify is sent to TypeSafe AI (api.typesafe.ai), a third-party processor. If you handle personal or customer data, list TypeSafe AI in your sub-processor documentation, and do not send content you are not permitted to share.
