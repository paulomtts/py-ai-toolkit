<!-- task-pipeline: validated -->
# Task 4.2 (e4860d92): docs for the classifier guide, hooks, API and nav

Parent: Story 4 "live test and docs" (de7e2839). Milestone: "ClassifierPort with Jev adapter" (e3bd09dc). Blocked by 4.1 (d00457fd), which is done.

## Base

This worktree (`task-4-2-docs-classifier-e4860d92`) already contains the classifier code from stories 1 to 3 (`py_ai_toolkit/core/domain/classifier.py`, `core/hooks.py`, `core/toolkit.py`, `adapters/jev_adapter.py`, `factories.py`). No rebase is needed. All documentation must describe that code as built, not the milestone design doc.

## Scope

This card changes docs only. The owned files are:

- `docs/guide/classifier.md` (new)
- `docs/guide/hooks.md`
- `docs/api/tools.md`
- `mkdocs.yml`

Out of scope: source edits, `tests/` (including `tests/live/`), `pyproject.toml`, and the version bump (it stays at 0.7.0 and is left to bump2version). Also out of scope: the `.claude/commands/py-ai-toolkit.md` skill doc and any build output under `site/`. The docs may name the following only as non-features: an LLM-backed or fallback adapter, chat/stream/embed on the classifier, normalization or derived confidence, streaming, a sync client, the toolkit's own retry logic, and consumer integration. Use no emojis and match the existing `docs/guide` and `docs/api` style.

## 1. `docs/guide/classifier.md` (new)

The guide must state each of these facts and stay consistent with the code:

- **What Jev is.** Jev is TypeSafe AI's classifier. It answers structured questions about a `state` (a str, dict or list) and cannot generate text.
- **Install.** `pip install 'py-ai-toolkit[jev]'`. The extra pulls in `typesafe-sdk>=0.6.0`.
- **Config.** `ClassifierConfig(api_key, model, base_url)`, all `str | None`. The matching env vars are `CLASSIFIER_API_KEY`, `CLASSIFIER_MODEL` (falls back to `"jev-latest"`) and `CLASSIFIER_BASE_URL`. The env is read in `PyAIToolkit.__init__`, and an explicit config value beats the env, field by field.
- **Activation** (`toolkit.py:76-94`):
  - A classifier is built only if `classifier_config` is passed or `CLASSIFIER_API_KEY` is set. Otherwise `toolkit.classifier is None`.
  - If a `classifier_config` is passed and neither it nor the env provides a key, the constructor raises `ValueError("ClassifierConfig requires an api_key or CLASSIFIER_API_KEY.")`.
  - If the extra is missing, the constructor raises `ImportError` (from `create_classifier`).
- **Examples.** Give one example each for `NoulQuestion`, `ChoiceQuestion` and `ScoreQuestion`. Read the results through `response.nouls`, `.choices` and `.scores`, using the answer fields: `noul`; `choice` with `probabilities` and `confidence`; `score` with `probabilities` (int keys), `confidence` and `legend` (int keys).
  - `NoulCriteria` is not exported at the top level. Import it from `py_ai_toolkit.core.domain.classifier`.
  - All other types import from `py_ai_toolkit`.
- **Raw values.**
  - `NoulAnswer` has no confidence.
  - `confidence` on a choice and on a score are not comparable with each other.
  - The toolkit does not normalize anything. Do not present `max(p, 1-p)` or any derived figure as a confidence.
- **Patterns.**
  - Choices are single-select and cannot abstain, so recommend adding a "none" option to the criteria.
  - Threshold `noul` directly.
  - Always set `instructions`. This is a recommendation, not enforced.
- **Validation.** Pydantic `ValidationError` is raised at question construction: choice `criteria` needs 1 to 255 entries, and score `criteria` needs 2 to 10. Do not claim that `classify()` rejects empty question names: `validate_question_names` exists but nothing calls it. Only answer names on `ClassifierResponse` are validated.
- **Errors at call time.**
  - `ClassifierAdapterError` when the classifier is unconfigured, using the exact message from `toolkit.py:249-250`.
  - `ValueError("questions must not be empty.")` for empty questions.
  - `ClassifierAdapterError` for every SDK or API failure, with the original exception on `__cause__`. The failures are: authentication, unprocessable entity (the message includes the body), rate limit (includes `retry_after_ms`), internal server error, connection or timeout, response validation (includes `field_path`), and generic `TypeSafeError`.
  - The SDK retries by default (2 retries within a 30 s budget). The toolkit adds no retries of its own.
- **Hooks.** Mention `before_classify` and `after_classify` briefly and link to the hooks guide.
- **Lifecycle.** Call `await toolkit.aclose()`. It is a no-op when no classifier is configured.
- **Limitations.** Jev is weak at arithmetic and dates, and with noisy context and adversarial content. Its context window is bounded. Its Portuguese support is undocumented.
- **Data privacy.** The `state` is sent to TypeSafe AI (api.typesafe.ai), a third-party processor, so consumers must list it in their sub-processor documentation.
- **Status.** Jev has been pre-GA early access since 2026-09-15.

## 2. `docs/guide/hooks.md`

- **Available Hooks table (lines 28-38).** Add `before_classify` -> `BeforeClassifyContext` (fires before the classifier call) and `after_classify` -> `AfterClassifyContext` (fires after a successful classifier response). Fix the count in the "fires hooks at seven points" sentence to match the rows. The table already omits `after_embed` and `after_embed_batch`, which are real `Hooks` fields, so add rows for them too. That makes eleven, which matches the `Hooks` dataclass. Context type names for the embed rows come from `core/hooks.py` (`AfterEmbedContext`, `AfterEmbedBatchContext`).
- **Method table (line 42).** Add a "Classify hooks" column. The `classify()` row is `--` in every other column and `before_classify`, `after_classify` in the new one. Every existing row gets `--` in the new column.
- **Context sections.** Add `### BeforeClassifyContext` (`state`, `questions`, `model`) and `### AfterClassifyContext` (`response`, `model`, `elapsed_ms`, `usage: ClassifierUsage`) after `OnRetryContext`, in the existing field-table format.
- **Behaviour notes.**
  - `before_classify` fires only after the guards pass, so it does not fire when the classifier is unconfigured or `questions` is empty.
  - `after_classify` fires on success only.
  - Hooks only observe; they do not change the call.
- **All Imports.** Add both contexts to the import block, from `py_ai_toolkit.core.hooks`.

## 3. `docs/api/tools.md`

- **Constructor (lines 5-35).** Document the `classifier_config: ClassifierConfig | None = None` kwarg, its env fallback and its activation rule.
- **Methods.** After `embed_batch()` and before `run_task()` (line 186), add `### classify()` and `### aclose()` in the existing format: signature, Parameters, Returns, Example and a `---` separator.
  - The `classify` signature is `async def classify(state: str | dict | list, questions: Mapping[str, Question], *, hooks: Hooks | None = None) -> ClassifierResponse`. Its Raises entries are the same as in the guide.
  - The `aclose` signature is `async def aclose() -> None`.
- **Supporting Classes (line 292 onward).** Add `ClassifierConfig`, `ClassifierResponse` (`model`, `answers`, `usage`, and the properties `nouls`, `choices` and `scores`), `NoulQuestion`, `ChoiceQuestion`, `ScoreQuestion`, `NoulCriteria` (with its import path), `NoulAnswer`, `ChoiceAnswer`, `ScoreAnswer`, the `Question` and `Answer` discriminated unions, `ClassifierUsage` (`input_tokens`, `output_tokens`, both `int | None`) and `ClassifierAdapterError`. Field types must match `classifier.py` exactly.

## 4. `mkdocs.yml`

Under `nav` -> Guide, add `- Classifier: guide/classifier.md` right after `- Hooks: guide/hooks.md` (line 50).

## Verification

- `uv run mkdocs build --strict` passes, with no broken links or missing nav targets.
- `site/` changes are not committed.
- Every import line in the docs resolves against this worktree: top-level names come from `py_ai_toolkit.__all__`, `NoulCriteria` from `core.domain.classifier`, and the hook contexts from `core.hooks`.
- `git diff --name-only` lists only the four owned files.

## Tests

None. This card changes docs only, and the repo has no testing standards doc. By the conventional layout (see the milestone design's Testing section), any later behaviour test would go in `tests/unit/` (plain pytest), and key-gated live tests stay in `tests/live/test_jev_live.py`, which belongs to 4.1 and is not touched here.

## Notes

- The exploration summary was cut off at the start of its VERIFICATION field, which shows the upstream stage over-ran its brief. The verification above comes from the card's deliverable 5 and its constraints, not from the missing text.
- The code differs from the findings in two places, and the docs must follow the code:
  - An explicit config with no key raises `ValueError` at construction.
  - Empty question names are not rejected by `classify()`.

---

# Classifier Docs (Task 4.2, e4860d92) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document the already-built Jev classifier (guide page, hooks reference, API reference, nav entry) so the docs match the code in this worktree exactly.

**Architecture:** Docs-only change to four owned files. Each task edits one doc surface and is gated by a throwaway shell/Python check that fails before the edit (RED) and passes after (GREEN); the checks read the real code (`Hooks` dataclass fields, pydantic `model_fields`) so the docs cannot drift from it. `mkdocs build --strict` is the site-level gate. No test files are added (spec "Tests": none); the checks are run inline and never committed.

**Tech Stack:** MkDocs 1.6.1 with the Material theme (`admonition`, `pymdownx.superfences`, `toc` with permalinks), uv, Python >= 3.11, pydantic v2.

**Spec:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92/docs/superpowers/specs/task-4-2-docs-classifier-e4860d92-design.md` (prepended verbatim above).

**Working directory for every command:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92` (branch `m-classifier/task-4-2-docs-classifier-e4860d92`, cut from `m-classifier/task-4-1-test-live-jev-test-d00457fd`). Every command block below starts with `cd` into it because shell cwd is not preserved between calls.

## Global Constraints

- Only these files may change: `docs/guide/classifier.md` (new), `docs/guide/hooks.md`, `docs/api/tools.md`, `mkdocs.yml`.
- No source edits, no `tests/` edits (including `tests/live/`), no `pyproject.toml` edit, no version bump (stays `0.7.0`).
- Do not edit `.claude/commands/py-ai-toolkit.md`; do not commit anything under `site/` (always build to `/tmp/pyait-site-4-2` with `-d`).
- Docs follow the code in this worktree, not the milestone design doc.
- Raw values only: no normalization, no derived confidence; never present `max(p, 1-p)` or any derived figure as a confidence.
- Non-features (LLM-backed/fallback adapter, chat/stream/embed on the classifier, normalization, streaming, sync client, own retry logic, consumer integration) may appear only as non-features or limitations.
- `NoulCriteria` imports from `py_ai_toolkit.core.domain.classifier`; hook contexts import from `py_ai_toolkit.core.hooks`; every other classifier name imports from `py_ai_toolkit`.
- No emojis. Match existing `docs/guide` and `docs/api` style. No hard-wrapped prose.
- Exact messages: unconfigured call is ``Classifier not configured: pass ClassifierConfig (or set CLASSIFIER_API_KEY) and install `py-ai-toolkit[jev]`.``; empty questions is `questions must not be empty.`; config without key is `ClassifierConfig requires an api_key or CLASSIFIER_API_KEY.`
- Mkdocs build gate: `uv run mkdocs build --strict -d /tmp/pyait-site-4-2`.

## Review Focus

Docs have no runtime inputs; the failure modes that would bite a reader are wrong facts. Most likely first:

1. A reader copies an import line from the docs and it fails (e.g. `from py_ai_toolkit import NoulCriteria`). Expected: every `from py_ai_toolkit... import ...` line in the three docs resolves. Pinned by the import-resolution check in Task 4, Step 2.
2. A reader trusts the Available Hooks table as complete and misses a hook. Expected: the table rows equal the `Hooks` dataclass fields exactly (eleven). Pinned by the check in Task 2, Step 1.
3. A reader relies on a context or model field the docs list but the code lacks (or vice versa). Expected: documented `ctx.<field>` names equal the dataclass fields; documented class fields equal pydantic `model_fields`. Pinned by Task 2, Step 1 (contexts) and Task 3, Step 1 (supporting classes).
4. A reader passes `ClassifierConfig()` with no key and expects a lazy call-time error. Expected: docs say `ValueError` at construction. Pinned by the phrase check in Task 1, Step 1 and Task 3, Step 1.
5. A reader expects `classify()` to reject empty question names. Expected: docs do not claim this. Pinned by the negative phrase check in Task 1, Step 1.

---

### Task 1: Classifier guide page and nav entry

**Files:**
- Create: `docs/guide/classifier.md`
- Modify: `mkdocs.yml:50` (insert one line after it)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: page `docs/guide/classifier.md` with headings `## Configuration`, `## Errors`, `## Hooks`, `## Closing the Client` (slugs `configuration`, `errors`, `hooks`, `closing-the-client`). Task 3 links to `../guide/classifier.md`; Task 2 is linked from this page as `hooks.md`.

- [ ] **Step 1: Baseline the strict build and write the RED check**

Run the strict build on the untouched tree first, to separate pre-existing warnings from ours:

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
uv run mkdocs build --strict -d /tmp/pyait-site-4-2
```

Expected: PASS ("Documentation built in ..."). If it fails and every WARNING names a file under `docs/superpowers/` (gitignored locally, absent in CI), use this fallback build command everywhere this plan says "Mkdocs build gate":

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
cat > /tmp/mkdocs-4-2.yml <<'EOF'
INHERIT: /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92/mkdocs.yml
docs_dir: /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92/docs
exclude_docs: |
  superpowers/
EOF
uv run mkdocs build --strict -f /tmp/mkdocs-4-2.yml -d /tmp/pyait-site-4-2
```

Then add the nav entry. In `mkdocs.yml`, replace:

```yaml
      - Hooks: guide/hooks.md
  - API Reference:
```

with:

```yaml
      - Hooks: guide/hooks.md
      - Classifier: guide/classifier.md
  - API Reference:
```

- [ ] **Step 2: Run the build to verify it fails (RED)**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
uv run mkdocs build --strict -d /tmp/pyait-site-4-2
```

Expected: FAIL with a WARNING like "A reference to 'guide/classifier.md' is included in the 'nav' configuration, which is not found in the documentation files" and "Aborted with 1 warnings in strict mode!".

Also run the content check, which must fail now because the file does not exist:

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
uv run python - <<'EOF'
import pathlib
p = pathlib.Path("docs/guide/classifier.md")
assert p.exists(), "classifier.md missing"
t = p.read_text()
required = [
    "pip install 'py-ai-toolkit[jev]'",
    "typesafe-sdk>=0.6.0",
    "CLASSIFIER_API_KEY", "CLASSIFIER_MODEL", "CLASSIFIER_BASE_URL", '"jev-latest"',
    "toolkit.classifier is None",
    "ClassifierConfig requires an api_key or CLASSIFIER_API_KEY.",
    "Classifier not configured: pass ClassifierConfig (or set CLASSIFIER_API_KEY) and install `py-ai-toolkit[jev]`.",
    "questions must not be empty.",
    "from py_ai_toolkit.core.domain.classifier import NoulCriteria",
    "NoulQuestion(", "ChoiceQuestion(", "ScoreQuestion(",
    "response.nouls[", "response.choices[", "response.scores[",
    '"none"', "__cause__", "retry_after_ms", "field_path",
    "before_classify", "after_classify", "(hooks.md)",
    "await toolkit.aclose()",
    "api.typesafe.ai", "sub-processor", "2026-09-15",
    "ImportError", "ValidationError", "ClassifierAdapterError",
]
missing = [r for r in required if r not in t]
assert not missing, missing
forbidden = ["max(p", "1-p", "1 - p", "rejects empty question names"]
present = [f for f in forbidden if f in t]
assert not present, present
print("PASS")
EOF
```

Expected: FAIL with `AssertionError: classifier.md missing`.

- [ ] **Step 3: Write the guide (GREEN)**

Create `docs/guide/classifier.md` with exactly this content:

````markdown
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
````

- [ ] **Step 4: Run the checks to verify they pass (GREEN)**

Re-run the content check from Step 2.

Expected: `PASS`.

Then run the Mkdocs build gate:

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
uv run mkdocs build --strict -d /tmp/pyait-site-4-2
```

Expected: PASS, no WARNING lines. (Use the Step 1 fallback command if the baseline required it.)

- [ ] **Step 5: Commit**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
git add docs/guide/classifier.md mkdocs.yml
git commit -m "docs: add classifier guide and nav entry"
```

---

### Task 2: Hooks guide (classify hooks, embed rows, count fix)

**Files:**
- Modify: `docs/guide/hooks.md:26-51` (Available Hooks and method tables), `:55-79` (Hooks container and usage), `:134-141` (after OnRetryContext), `:193-214` (Important Notes, All Imports)

**Interfaces:**
- Consumes: `py_ai_toolkit.core.hooks.Hooks` fields (eleven: `before_render`, `after_render`, `before_llm_call`, `after_llm_call`, `after_embed`, `after_embed_batch`, `before_validation`, `after_validation`, `on_retry`, `before_classify`, `after_classify`); `BeforeClassifyContext(state, questions, model)`; `AfterClassifyContext(response, model, elapsed_ms, usage)`.
- Produces: headings `### BeforeClassifyContext` and `### AfterClassifyContext` in `docs/guide/hooks.md` (Task 1's guide links to `hooks.md`).

- [ ] **Step 1: Write the RED check**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
uv run python - <<'EOF'
import dataclasses, pathlib, re
from py_ai_toolkit.core.hooks import AfterClassifyContext, BeforeClassifyContext, Hooks

text = pathlib.Path("docs/guide/hooks.md").read_text()

available = text.split("## Available Hooks", 1)[1].split("## Which Methods", 1)[0]
rows = set(re.findall(r"^\| `(\w+)` \|", available, re.M))
fields = {f.name for f in dataclasses.fields(Hooks)}
assert rows == fields, ("missing", sorted(fields - rows), "extra", sorted(rows - fields))
assert "eleven points" in available, "count sentence not fixed"
assert "seven points" not in text

methods = text.split("## Which Methods Support Which Hooks", 1)[1].split("## The Hooks Container", 1)[0]
assert "Classify hooks" in methods
assert re.search(r"^\| `classify\(\)` \| -- \| -- \| -- \| -- \| `before_classify`, `after_classify` \|$", methods, re.M)
for line in methods.splitlines():
    if line.startswith("| `"):
        assert line.count("|") == 7, line

for ctx in (BeforeClassifyContext, AfterClassifyContext):
    sec = text.split(f"### {ctx.__name__}", 1)
    assert len(sec) == 2, f"no section for {ctx.__name__}"
    body = sec[1].split("###", 1)[0].split("## ", 1)[0]
    documented = set(re.findall(r"ctx\.(\w+)", body))
    expected = {f.name for f in dataclasses.fields(ctx)}
    assert documented == expected, (ctx.__name__, documented, expected)

imports = text.split("## All Imports", 1)[1]
assert "BeforeClassifyContext," in imports and "AfterClassifyContext," in imports
notes = text.split("## Important Notes", 1)[1].split("## All Imports", 1)[0]
assert "before_classify" in notes and "after_classify" in notes
print("PASS")
EOF
```

- [ ] **Step 2: Run it to verify it fails**

Run the Step 1 command.

Expected: FAIL with `AssertionError: ('missing', ['after_classify', 'after_embed', 'after_embed_batch', 'before_classify'], 'extra', [])`.

- [ ] **Step 3: Edit `docs/guide/hooks.md` (GREEN)**

Edit A. Replace:

```markdown
The toolkit fires hooks at seven points in the pipeline:

| Hook | Fires when | Context type |
|---|---|---|
| `before_render` | Before Jinja2 template rendering | `BeforeRenderContext` |
| `after_render` | After template rendering | `AfterRenderContext` |
| `before_llm_call` | Before the LLM API call | `BeforeLLMCallContext` |
| `after_llm_call` | After the LLM response | `AfterLLMCallContext` |
| `before_validation` | Before a validation round | `BeforeValidationContext` |
| `after_validation` | After a validation round | `AfterValidationContext` |
| `on_retry` | When a retry is triggered | `OnRetryContext` |
```

with:

```markdown
The toolkit fires hooks at eleven points in the pipeline:

| Hook | Fires when | Context type |
|---|---|---|
| `before_render` | Before Jinja2 template rendering | `BeforeRenderContext` |
| `after_render` | After template rendering | `AfterRenderContext` |
| `before_llm_call` | Before the LLM API call | `BeforeLLMCallContext` |
| `after_llm_call` | After the LLM response | `AfterLLMCallContext` |
| `after_embed` | After an `embed()` response | `AfterEmbedContext` |
| `after_embed_batch` | After an `embed_batch()` response | `AfterEmbedBatchContext` |
| `before_validation` | Before a validation round | `BeforeValidationContext` |
| `after_validation` | After a validation round | `AfterValidationContext` |
| `on_retry` | When a retry is triggered | `OnRetryContext` |
| `before_classify` | Before the classifier call | `BeforeClassifyContext` |
| `after_classify` | After a successful classifier response | `AfterClassifyContext` |
```

Edit B. Replace:

```markdown
| Method | Render hooks | LLM hooks | Embed hooks | Validation/retry hooks |
|---|---|---|---|---|
| `chat()` | Yes | Yes | -- | -- |
| `stream()` | Yes | Yes | -- | -- |
| `asend()` | Yes | Yes | -- | -- |
| `run_task()` | Yes | Yes | -- | Yes |
| `embed()` | -- | -- | `after_embed` | -- |
| `embed_batch()` | -- | -- | `after_embed_batch` | -- |

Validation and retry hooks only fire in `run_task()` because that's where the validation loop lives.
```

with:

```markdown
| Method | Render hooks | LLM hooks | Embed hooks | Validation/retry hooks | Classify hooks |
|---|---|---|---|---|---|
| `chat()` | Yes | Yes | -- | -- | -- |
| `stream()` | Yes | Yes | -- | -- | -- |
| `asend()` | Yes | Yes | -- | -- | -- |
| `run_task()` | Yes | Yes | -- | Yes | -- |
| `embed()` | -- | -- | `after_embed` | -- | -- |
| `embed_batch()` | -- | -- | `after_embed_batch` | -- | -- |
| `classify()` | -- | -- | -- | -- | `before_classify`, `after_classify` |

Validation and retry hooks only fire in `run_task()` because that's where the validation loop lives. Classify hooks only fire in `classify()`; see the [Classifier guide](classifier.md).
```

Edit C. Replace:

```python
    on_retry=my_on_retry,
)
```

with:

```python
    on_retry=my_on_retry,
    before_classify=my_before_classify,
    after_classify=my_after_classify,
)
```

Edit D. Replace:

```python
await toolkit.run_task(template="...", response_model=MyModel, kwargs={}, hooks=hooks)
```

with:

```python
await toolkit.run_task(template="...", response_model=MyModel, kwargs={}, hooks=hooks)
await toolkit.classify(state="...", questions=questions, hooks=hooks)
```

Edit E. Replace:

````markdown
    print(ctx.evaluations)    # str - feedback string passed to next attempt
```

## Example: Token Usage Tracker
````

with:

````markdown
    print(ctx.evaluations)    # str - feedback string passed to next attempt
```

### BeforeClassifyContext

```python
async def on_before_classify(ctx: BeforeClassifyContext) -> None:
    print(ctx.state)      # str | dict[str, Any] | list[Any] - the content being classified
    print(ctx.questions)  # Mapping[str, Question] - question name to question
    print(ctx.model)      # str - classifier model name
```

### AfterClassifyContext

```python
async def on_after_classify(ctx: AfterClassifyContext) -> None:
    print(ctx.response)    # ClassifierResponse - the full response
    print(ctx.model)       # str - classifier model name
    print(ctx.elapsed_ms)  # float - classifier call duration in milliseconds
    print(ctx.usage)       # ClassifierUsage - input_tokens and output_tokens (int | None)
```

## Example: Token Usage Tracker
````

Edit F. Replace:

```markdown
- For `stream()`, the `after_llm_call` hook fires after the stream completes and receives the last chunk as the response.
```

with:

```markdown
- For `stream()`, the `after_llm_call` hook fires after the stream completes and receives the last chunk as the response.
- `before_classify` fires only after `classify()`'s guards pass: it does not fire when no classifier is configured or when `questions` is empty.
- `after_classify` fires on success only. If the classifier call raises, it does not fire.
- `elapsed_ms` in `AfterClassifyContext` measures the classifier call only.
```

Edit G. Replace:

```python
    OnRetryContext,
)
```

with:

```python
    OnRetryContext,
    BeforeClassifyContext,
    AfterClassifyContext,
)
```

- [ ] **Step 4: Run the checks to verify they pass**

Re-run the Step 1 command.

Expected: `PASS`.

Then the Mkdocs build gate:

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
uv run mkdocs build --strict -d /tmp/pyait-site-4-2
```

Expected: PASS, no WARNING lines.

- [ ] **Step 5: Commit**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
git add docs/guide/hooks.md
git commit -m "docs: document classify hooks and fix hook count in hooks guide"
```

---

### Task 3: API reference (constructor, classify, aclose, supporting classes)

**Files:**
- Modify: `docs/api/tools.md:5-35` (constructor), insert after `:184` (the `---` after `embed_batch()`), append after `:327` (end of Supporting Classes)

**Interfaces:**
- Consumes: `PyAIToolkit.__init__(main_model_config: LLMConfig | None = None, alternative_models_configs: list[LLMConfig] | None = None, classifier_config: ClassifierConfig | None = None)`; `PyAIToolkit.classify(state: str | dict | list, questions: Mapping[str, Question], *, hooks: Hooks | None = None) -> ClassifierResponse`; `PyAIToolkit.aclose() -> None`; the pydantic models in `py_ai_toolkit/core/domain/classifier.py`; `ClassifierAdapterError(Exception)` in `py_ai_toolkit/core/domain/errors.py`. Links to `../guide/classifier.md` (Task 1).
- Produces: headings `### classify()`, `### aclose()` and one `### <Class>` per supporting class.

- [ ] **Step 1: Write the RED check**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
uv run python - <<'EOF'
import pathlib, re
from py_ai_toolkit.core.domain import classifier as c

text = pathlib.Path("docs/api/tools.md").read_text()

ctor = text.split("## Constructor", 1)[1].split("## Methods", 1)[0]
assert "classifier_config: ClassifierConfig | None = None" in ctor
assert "CLASSIFIER_API_KEY" in ctor and "ValueError" in ctor and "ImportError" in ctor

methods = text.split("## Methods", 1)[1].split("## Supporting Classes", 1)[0]
order = [m.group(1) for m in re.finditer(r"^### (\w+)\(\)", methods, re.M)]
i = order.index("embed_batch")
assert order[i + 1 : i + 4] == ["classify", "aclose", "run_task"], order
assert "questions: Mapping[str, Question]" in methods
assert "hooks: Hooks | None = None" in methods
assert "-> ClassifierResponse" in methods
assert "async def aclose() -> None" in methods
assert "questions must not be empty." in methods

support = text.split("## Supporting Classes", 1)[1]
models = ["ClassifierConfig", "ClassifierResponse", "NoulQuestion", "ChoiceQuestion",
          "ScoreQuestion", "NoulCriteria", "NoulAnswer", "ChoiceAnswer", "ScoreAnswer",
          "ClassifierUsage"]
for name in models:
    assert f"### {name}\n" in support, f"no heading for {name}"
    block = re.search(rf"```python\nclass {name}\(BaseModel\):\n(.*?)```", support, re.S)
    assert block, f"no class block for {name}"
    documented = set(re.findall(r"^    (\w+):", block.group(1), re.M))
    expected = set(getattr(c, name).model_fields)
    assert documented == expected, (name, documented, expected)
for name in ("Question", "Answer", "ClassifierAdapterError"):
    assert f"### {name}\n" in support, f"no heading for {name}"
assert "from py_ai_toolkit.core.domain.classifier import NoulCriteria" in support
for prop in ("def nouls(self)", "def choices(self)", "def scores(self)"):
    assert prop in support, prop
print("PASS")
EOF
```

- [ ] **Step 2: Run it to verify it fails**

Run the Step 1 command.

Expected: FAIL with `AssertionError` on the first assert (`classifier_config: ClassifierConfig | None = None` not in the constructor section).

- [ ] **Step 3: Edit `docs/api/tools.md` (GREEN)**

Edit A (constructor). Replace:

````markdown
```python
PyAIToolkit(
    main_model_config: LLMConfig,
    alternative_models_configs: list[LLMConfig] | None = None
)
```

**Parameters:**

- `main_model_config` (LLMConfig): Primary LLM configuration
- `alternative_models_configs` (list[LLMConfig] | None): Optional list of alternative models for load balancing
````

with:

````markdown
```python
PyAIToolkit(
    main_model_config: LLMConfig | None = None,
    alternative_models_configs: list[LLMConfig] | None = None,
    classifier_config: ClassifierConfig | None = None
)
```

**Parameters:**

- `main_model_config` (LLMConfig | None): Primary LLM configuration
- `alternative_models_configs` (list[LLMConfig] | None): Optional list of alternative models for load balancing
- `classifier_config` (ClassifierConfig | None): Optional Jev classifier settings. Unset fields fall back to `CLASSIFIER_API_KEY`, `CLASSIFIER_MODEL` (default `"jev-latest"`) and `CLASSIFIER_BASE_URL`, read here at construction. A classifier is built only if this is passed or `CLASSIFIER_API_KEY` is set; otherwise `classifier` is `None`. See the [Classifier guide](../guide/classifier.md).

**Raises:**

- `ValueError`: `classifier_config` was passed but neither it nor `CLASSIFIER_API_KEY` provides an API key
- `ImportError`: a classifier would be built but the `jev` extra is not installed (`pip install 'py-ai-toolkit[jev]'`)
````

Edit B (methods). Replace:

````markdown
print(responses[0].usage.total_tokens)  # Aggregated usage across all inputs
```

---

### run_task()
````

with:

````markdown
print(responses[0].usage.total_tokens)  # Aggregated usage across all inputs
```

---

### classify()

Answer structured questions about a piece of content with the configured Jev classifier.

```python
async def classify(
    state: str | dict | list,
    questions: Mapping[str, Question],
    *,
    hooks: Hooks | None = None
) -> ClassifierResponse
```

**Parameters:**

- `state` (str | dict | list): The text or JSON-like content to classify
- `questions` (Mapping[str, Question]): Question name to question (`NoulQuestion`, `ChoiceQuestion` or `ScoreQuestion`)
- `hooks` (Hooks | None): Optional hooks (fires `before_classify` and `after_classify`)

**Returns:** `ClassifierResponse` with one raw answer per question name, unchanged

**Raises:**

- `ClassifierAdapterError`: no classifier is configured, or the SDK/API call failed (the original exception is on `__cause__`)
- `ValueError`: `questions` is empty (`questions must not be empty.`)

**Example:**

```python
from py_ai_toolkit import ChoiceQuestion, NoulQuestion

response = await ait.classify(
    state="I was charged twice for my March invoice.",
    questions={
        "is_refund_request": NoulQuestion(instructions="Is the customer asking for money back?"),
        "department": ChoiceQuestion(
            instructions="Which team should handle this?",
            criteria={"billing": "Payments and invoices.", "none": "None of the above."},
        ),
    },
)
print(response.nouls["is_refund_request"].noul)
print(response.choices["department"].choice)
```

---

### aclose()

Release the classifier's resources. A no-op when no classifier is configured.

```python
async def aclose() -> None
```

**Returns:** `None`

**Example:**

```python
await ait.aclose()
```

---

### run_task()
````

Edit C (supporting classes). Replace:

```markdown
- `completion`: Raw OpenAI completion object
- `content`: Text string or structured model instance
- `response_model`: Property for type-safe access to structured content
```

with:

````markdown
- `completion`: Raw OpenAI completion object
- `content`: Text string or structured model instance
- `response_model`: Property for type-safe access to structured content

### ClassifierConfig

Configuration for the Jev classifier.

```python
class ClassifierConfig(BaseModel):
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
```

Falls back to environment variables, field by field: `CLASSIFIER_API_KEY`, `CLASSIFIER_MODEL` (default `"jev-latest"`), `CLASSIFIER_BASE_URL`. The environment is read by `PyAIToolkit`, not by this class.

### ClassifierResponse

Response returned by `classify()`. Values are raw; nothing is normalized or derived.

```python
class ClassifierResponse(BaseModel):
    model: str
    answers: dict[str, Answer]
    usage: ClassifierUsage

    @property
    def nouls(self) -> dict[str, NoulAnswer]: ...

    @property
    def choices(self) -> dict[str, ChoiceAnswer]: ...

    @property
    def scores(self) -> dict[str, ScoreAnswer]: ...
```

**Attributes:**

- `model`: The classifier model that answered
- `answers`: Question name to answer; empty answer names fail validation
- `usage`: Token usage
- `nouls`, `choices`, `scores`: The answers of each type, keyed by question name

### ClassifierUsage

```python
class ClassifierUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
```

### NoulQuestion

A yes/no question.

```python
class NoulQuestion(BaseModel):
    type: Literal["noul"] = "noul"
    instructions: JSONContent | None = None
    criteria: NoulCriteria | None = None
```

`JSONContent` is `str | dict[str, Any] | list[Any]`.

### NoulCriteria

What counts as true and false for a `NoulQuestion`. Not exported from the package root:

```python
from py_ai_toolkit.core.domain.classifier import NoulCriteria
```

```python
class NoulCriteria(BaseModel):
    true: JSONContent | None = None
    false: JSONContent | None = None
```

### ChoiceQuestion

A single-select question. It always picks one option and cannot abstain.

```python
class ChoiceQuestion(BaseModel):
    type: Literal["choice"] = "choice"
    instructions: JSONContent | None = None
    criteria: dict[str, JSONContent | None]  # 1 to 255 entries
```

### ScoreQuestion

A question that places the state on a scale.

```python
class ScoreQuestion(BaseModel):
    type: Literal["score"] = "score"
    instructions: JSONContent | None = None
    criteria: list[JSONContent]  # 2 to 10 entries
```

### NoulAnswer

```python
class NoulAnswer(BaseModel):
    type: Literal["noul"] = "noul"
    noul: float
```

No confidence field: threshold `noul` directly.

### ChoiceAnswer

```python
class ChoiceAnswer(BaseModel):
    type: Literal["choice"] = "choice"
    choice: str
    probabilities: dict[str, float]
    confidence: float
```

### ScoreAnswer

```python
class ScoreAnswer(BaseModel):
    type: Literal["score"] = "score"
    score: float
    probabilities: dict[int, float]
    confidence: float
    legend: dict[int, JSONContent]
```

`probabilities` and `legend` are keyed by `int` level. `confidence` here is not comparable with `ChoiceAnswer.confidence`.

### Question

```python
Question = Annotated[
    NoulQuestion | ChoiceQuestion | ScoreQuestion, Field(discriminator="type")
]
```

### Answer

```python
Answer = Annotated[NoulAnswer | ChoiceAnswer | ScoreAnswer, Field(discriminator="type")]
```

### ClassifierAdapterError

```python
class ClassifierAdapterError(Exception): ...
```

Raised by `classify()` when no classifier is configured and for every SDK or API failure (authentication, unprocessable entity, rate limit, internal server error, connection or timeout, malformed response, any other `TypeSafeError`). The original SDK exception is on `__cause__`. Import it with `from py_ai_toolkit import ClassifierAdapterError`.
````

- [ ] **Step 4: Run the checks to verify they pass**

Re-run the Step 1 command.

Expected: `PASS`.

Then the Mkdocs build gate:

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
uv run mkdocs build --strict -d /tmp/pyait-site-4-2
```

Expected: PASS, no WARNING lines.

- [ ] **Step 5: Commit**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
git add docs/api/tools.md
git commit -m "docs: add classifier API reference to PyAIToolkit docs"
```

---

### Task 4: Whole-branch verification

**Files:**
- No edits. Verifies the three docs and `mkdocs.yml` together.

**Interfaces:**
- Consumes: `docs/guide/classifier.md` (Task 1), `docs/guide/hooks.md` (Task 2), `docs/api/tools.md` (Task 3), `mkdocs.yml` (Task 1).
- Produces: nothing.

- [ ] **Step 1: Mkdocs build gate**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
uv run mkdocs build --strict -d /tmp/pyait-site-4-2
```

Expected: PASS, no WARNING lines.

- [ ] **Step 2: Every documented import resolves**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
uv run python - <<'EOF'
import pathlib, re
docs = ["docs/guide/classifier.md", "docs/guide/hooks.md", "docs/api/tools.md"]
pattern = re.compile(r"^from (py_ai_toolkit[\w.]*) import (\([^)]*\)|[^\n]+)", re.M)
count = 0
for path in docs:
    for module, names in pattern.findall(pathlib.Path(path).read_text()):
        exec(f"from {module} import {names}", {})
        count += 1
assert count > 0
print(f"PASS: {count} import statements resolve")
EOF
```

Expected: `PASS: N import statements resolve` (N > 0). An `ImportError` here names the bad line; fix it in the owning doc, re-run this step, and commit the fix as `docs: fix classifier doc import` with only that doc staged.

- [ ] **Step 3: Repo verification commands**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
uv run pytest tests/ --ignore=tests/test_run_task.py
```

Expected: PASS (live tests skip without `CLASSIFIER_API_KEY`); same result as before this card since no Python changed.

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F --ignore E501
```

Expected: PASS ("All checks passed!" for the earlier subtasks' Python files on this stacked branch; this card adds none).

- [ ] **Step 4: Scope check**

```bash
cd /home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-4-2-docs-classifier-e4860d92
git diff --name-only m-classifier/task-4-1-test-live-jev-test-d00457fd...HEAD
git status --porcelain
```

Expected: the first command prints exactly these four lines (any order):

```text
docs/api/tools.md
docs/guide/classifier.md
docs/guide/hooks.md
mkdocs.yml
```

The second prints nothing: no stray `site/` changes (builds went to `/tmp/pyait-site-4-2`) and no uncommitted edits. If anything else appears, revert it with `git checkout -- <path>` (or `git rm --cached` plus delete for an accidentally added file) before finishing.
