<!-- task-pipeline: validated -->
# Task 2.1 — chore: `jev` optional extra and SDK compatibility check (card e6f3dce5)

Parent: Story 2 "Jev adapter and jev extra" (e01d0be7), milestone e3bd09dc. Source design: `docs/superpowers/specs/2026-10-01-classifier-port-design.md` (gitignored; read it from the main checkout at `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/`), sections "Packaging" and "Open questions".

## Scope

This card only changes packaging. It touches no Python code.

1. `pyproject.toml`: add `jev = ["typesafe-sdk>=<floor>"]` under `[project.optional-dependencies]`, next to the existing `dev` and `docs` entries. Do not change core `dependencies`, do not change `requires-python` (`>=3.11`), and do not change `version` (it stays `0.7.0`; the bump to `0.8.0` belongs to a later card).
2. `.github/workflows/test.yml`: change the install step from `pip install -e ".[dev]"` to `pip install -e ".[dev,jev]"` so the adapter tests from later cards run in CI. Do not add `typesafe-sdk` to `dev`. Leave the test step unchanged.
3. `uv.lock`: it is git-tracked and records optional dependencies per extra, so run `uv lock` after the `pyproject.toml` edit and commit the result (it adds `typesafe-sdk`, its transitive deps such as `httpx2`, and the `jev` extra). The lock's recorded `py-ai-toolkit` version is stale (0.6.1 vs 0.7.0); `uv lock` will refresh it, which is acceptable and not a version bump. If `uv lock` changes any pinned version of an existing package, STOP and treat it as a conflict under "Error path" unless the change is only the `py-ai-toolkit` self-version. Lockfile updates are expected to be additive.
4. `MANIFEST.in`: confirm that it needs no change, because there is no new non-Python package data. Do not edit it.

Replace `<floor>` in item 1 with the version chosen under Open question 1 (a bare `>=X.Y.Z` lower bound, no ceiling).

Out of scope, because sibling cards or later stories own it: `adapters/jev_adapter.py`, any change to `adapters/__init__.py`, any test file, factories, docs, the version bump, and the live test. Do not commit the unrelated uncommitted `.gitignore` change (`*.code-workspace`).

## Open question 1: the version floor

The floor is the oldest `typesafe-sdk` release that has `AsyncTypeSafeClient.system_one` and `SystemOneResponse` with `nouls`, `choices` and `scores`, and that has the `Score.criteria` shape the adapter will target. That shape is an ordered sequence, introduced in 0.6.0, which made 0.6.0 a breaking release. The known releases are 0.5.7, 0.6.0, 0.7.0, 0.7.1 and 0.7.2.

Determine the floor by experiment. Install 0.6.0 (and 0.5.7 for contrast) in throwaway venvs. For each, inspect `typesafe_sdk.AsyncTypeSafeClient.system_one` and the fields of `SystemOneResponse` and `Score`.

- Expected result: `>=0.6.0`.
- Conservative alternative: `>=0.7.0`, the first pydantic-based release, which also adds `response_model`. Choose it if 0.6.0 lacks a required attribute or exposes models in a way the adapter cannot map with the same code.

Record the chosen floor and why in the commit message.

## Open question 2: resolver compatibility

In a clean venv (`uv venv` then `uv pip install -e ".[jev]"`, or the pip equivalent), install the package with the extra. It must resolve with no conflict against `openai`, `instructor`, `pydantic>=2.12.4` and `httpx`. Note that `typesafe-sdk` depends on `httpx2`, which is a separate distribution from `httpx`. Also confirm that the SDK's `requires_python` (`>=3.10`) admits `>=3.11`, so no higher floor needs documenting. Record the outcome in the commit message: no `httpx2` conflict, and Python `>=3.11` confirmed.

## Error path

If the install hits a real resolver conflict, or no released SDK version exposes the required API: STOP. Report the conflict or the gap. Do not pin around it, do not add ceilings, and do not edit core dependencies.

## Observable behavior

- `pip install "py-ai-toolkit[jev]"` installs `typesafe-sdk` at or above the floor.
- A plain `pip install py-ai-toolkit` installs nothing new.
- CI installs `dev` and `jev`.
- `import py_ai_toolkit` behaves exactly as before.

## Tests

No new tests. This is a packaging-only card. Under the design's Testing section (the repo's only test-placement rule), every planned test belongs to the feature cards: `tests/unit/test_classifier.py`, `tests/unit/test_jev_adapter.py`, `tests/unit/test_hooks.py` and `tests/live/test_jev_live.py`. None of them covers packaging. This card is proven by:

- The clean-env `[jev]` install succeeding, recorded in the commit message.
- The existing unit suite (`tests/unit/`, tier: unit) staying green under the verification command `uv run pytest tests/ --ignore=tests/test_run_task.py`. Optionally, also run it with the extra present (`uv run --extra dev --extra jev pytest tests/ --ignore=tests/test_run_task.py`) to show that installing the SDK breaks nothing.
- Lint (`ruff check --select E,F` on changed `.py` files) being vacuous, because no `.py` files change.

## Commit message must include

- The chosen floor and the evidence for it (the API inspected per version, and the `Score.criteria` shape).
- The clean-env install result (no conflict with `httpx2`, `openai` or `instructor`).
- Python `>=3.11` confirmed against the SDK's `requires_python`.
- Confirmation that `MANIFEST.in` needs no change.

---

# `jev` Optional Extra Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `jev` optional extra (`typesafe-sdk>=<floor>`) to `py-ai-toolkit`, choose the floor by experiment, lock it, install it in CI, and record the compatibility evidence in the commit message, without touching any Python code.

**Architecture:** Packaging-only change. Task 1 is a throwaway-venv experiment in `/tmp` that picks the floor and proves resolver compatibility, and commits nothing. Task 2 edits `pyproject.toml`, regenerates `uv.lock` additively, changes the CI install line, confirms `MANIFEST.in` is untouched, runs the verification gate, and makes one commit whose message carries the Task 1 evidence.

**Tech Stack:** setuptools `pyproject.toml`, `uv` (venv / pip / lock / run), GitHub Actions, pytest.

**Spec:** `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-1-chore-jev-optional-e6f3dce5/docs/superpowers/specs/task-2-1-chore-jev-optional-e6f3dce5-design.md` (reproduced verbatim above). Source design: `/home/mtts/Code/libs/py-ai-toolkit/docs/superpowers/specs/2026-10-01-classifier-port-design.md`, sections "Packaging" and "Open questions".

Worktree (all relative paths below are relative to it): `/home/mtts/Code/libs/py-ai-toolkit/.claude/worktrees/m-classifier/task-2-1-chore-jev-optional-e6f3dce5`, branch `m-classifier/task-2-1-chore-jev-optional-e6f3dce5`. Do not assume any sibling card's code (`jev_adapter.py`, `test_jev_adapter.py`) exists on this branch. It does not.

## Global Constraints

- The extra is `jev = ["typesafe-sdk>=X.Y.Z"]`: a bare lower bound, no ceiling.
- Core `dependencies` are unchanged: `grafo>=0.2.36`, `instructor>=1.13.0`, `openai>=1.104.2`, `pydantic>=2.12.4`, `python-dotenv>=1.2.1`, `pyyaml>=6.0.2`.
- `requires-python = ">=3.11"` is unchanged.
- `version = "0.7.0"` is unchanged.
- `typesafe-sdk` is NOT added to `dev`.
- `uv.lock` changes are additive. The only allowed changed existing pin is the `py-ai-toolkit` self-version (0.6.1 to 0.7.0).
- `MANIFEST.in` is not edited.
- No `.py` file and no test file is created or changed.
- The uncommitted `.gitignore` change (`*.code-workspace`) is never staged or committed.
- On a real resolver conflict, or if no released SDK exposes the required API: STOP and report. Do not pin around it, do not add ceilings, and do not edit core dependencies.
- Verification commands, run unchanged: `uv run pytest tests/ --ignore=tests/test_run_task.py` and `git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F`.

## Review Focus

- A plain `pip install py-ai-toolkit` (no extra) must not pull in `typesafe-sdk` or `httpx2`. Task 1 Step 5 installs without the extra and asserts that neither is present.
- `uv lock` must not silently bump any existing pin such as `openai`, `instructor`, `httpx` or `pydantic`. Task 2 Step 5 diffs the old and new lock package versions and fails on any change other than `py-ai-toolkit`.
- `import py_ai_toolkit` must behave exactly as before, even when the SDK is installed. It must not import `typesafe_sdk` as a side effect. Task 1 Step 6 asserts that `typesafe_sdk` is not in `sys.modules` after `import py_ai_toolkit` in the `[jev]` env.
- The floor must not admit a release whose `Score.criteria` is the old int-keyed dict. Task 1 Steps 2 and 3 inspect 0.5.7 and 0.6.0, and the decision rule in Step 4 rejects any version whose `criteria` annotation admits an int-keyed mapping.
- The existing suite must stay green with the SDK present, not only without it. Task 2 Step 8 runs the suite with `--extra dev --extra jev` in addition to the unchanged verification command.

---

### Task 1: Choose the floor and prove resolver compatibility (experiment, no commit)

**Files:**
- Create (throwaway, outside the repo): `/tmp/jev-probe.py`, venvs `/tmp/jev-057`, `/tmp/jev-060`, `/tmp/jev-070`, `/tmp/jev-clean`, `/tmp/jev-plain`
- No repo files change in this task.

**Interfaces:**
- Consumes: nothing.
- Produces: the floor `X.Y.Z` that Task 2 writes into `pyproject.toml`, plus the probe and install output lines that Task 2's commit message quotes.

- [ ] **Step 1: Write the probe script**

Write `/tmp/jev-probe.py`. It prints the installed version, `Requires-Python`, the declared requirements, the `system_one` signature, the `SystemOneResponse` fields and the `Score.criteria` annotation. It handles both the pre-0.7 msgspec structs and the 0.7+ pydantic models. `nouls`, `choices` and `scores` are `cached_property` accessors on `SystemOneResponse` (the real fields are `model`, `usage`, `answers`), so they are checked with `hasattr`. It exits non-zero if a required name is missing or `Score.criteria` still admits an int-keyed dict.

```python
import importlib
import importlib.metadata as md
import inspect
import pkgutil
import sys
import typing

import typesafe_sdk

print("version:", md.version("typesafe-sdk"))
print("requires_python:", md.metadata("typesafe-sdk")["Requires-Python"])
print("requires:", md.requires("typesafe-sdk"))


def find(name):
    obj = getattr(typesafe_sdk, name, None)
    if obj is not None:
        return obj
    for mod in pkgutil.walk_packages(typesafe_sdk.__path__, "typesafe_sdk."):
        try:
            m = importlib.import_module(mod.name)
        except Exception:
            continue
        if hasattr(m, name):
            print(f"  ({name} found in {mod.name}, not top-level)")
            return getattr(m, name)
    return None


def fields(cls):
    for attr in ("model_fields", "__struct_fields__"):
        f = getattr(cls, attr, None)
        if f:
            return list(f)
    return list(typing.get_type_hints(cls))


missing = []

client = find("AsyncTypeSafeClient")
if client is None or not hasattr(client, "system_one"):
    missing.append("AsyncTypeSafeClient.system_one")
else:
    print("system_one:", inspect.signature(client.system_one))

resp = find("SystemOneResponse")
if resp is None:
    missing.append("SystemOneResponse")
else:
    rf = fields(resp)
    print("SystemOneResponse fields:", rf)
    # nouls/choices/scores are cached_property accessors over `answers`, not struct/model fields
    for f in ("nouls", "choices", "scores"):
        if not hasattr(resp, f):
            missing.append(f"SystemOneResponse.{f}")

score = find("Score")
if score is None:
    missing.append("Score")
else:
    print("Score fields:", fields(score))
    hints = typing.get_type_hints(score)
    crit = hints.get("criteria")
    print("Score.criteria annotation:", crit)
    print("Score.criteria origin:", typing.get_origin(crit))
    if crit is None:
        missing.append("Score.criteria")
    else:
        # 0.5.7 annotates criteria as a union that includes an int-keyed dict; 0.6.0+ is a plain Sequence
        legacy = "dict[int" in str(crit) or "Mapping[int" in str(crit)
        print("Score.criteria int-keyed mapping accepted:", legacy)
        if legacy:
            missing.append("Score.criteria is legacy (int-keyed dict)")

print("MISSING:", missing)
sys.exit(1 if missing else 0)
```

- [ ] **Step 2: Probe 0.5.7 (contrast)**

Run:
```bash
uv venv /tmp/jev-057 --python 3.11
uv pip install --python /tmp/jev-057/bin/python "typesafe-sdk==0.5.7"
/tmp/jev-057/bin/python /tmp/jev-probe.py
```
Expected: the `Score.criteria` annotation is a union (origin `types.UnionType`/`typing.Union`, not `dict`) that contains `dict[int, ...]`; the probe prints `int-keyed mapping accepted: True` and exits 1 with `MISSING: ['Score.criteria is legacy (int-keyed dict)']`. Verified: 0.5.7 does have `system_one` and the three accessors, so the criteria shape is the only differentiator. Save the full output for the commit message.

- [ ] **Step 3: Probe 0.6.0 (expected floor)**

Run:
```bash
uv venv /tmp/jev-060 --python 3.11
uv pip install --python /tmp/jev-060/bin/python "typesafe-sdk==0.6.0"
/tmp/jev-060/bin/python /tmp/jev-probe.py
```
Expected: exit 0, `MISSING: []`, `SystemOneResponse fields` lists `model`, `usage`, `answers` (the three accessors are verified via `hasattr`), and `Score.criteria origin` is `collections.abc.Sequence` with `int-keyed mapping accepted: False`. Save the full output.

- [ ] **Step 4: Decide the floor**

Apply this rule to the Step 3 output:
- If Step 3 exits 0 and `Score.criteria` is a sequence, the floor is `0.6.0`.
- Otherwise, probe 0.7.0 with the commands below. If it exits 0 with a sequence `criteria`, the floor is `0.7.0`. Record which attribute 0.6.0 lacked.
- If 0.7.0 also fails, STOP. Report the missing names from `MISSING:` and do not continue to Task 2.

```bash
uv venv /tmp/jev-070 --python 3.11
uv pip install --python /tmp/jev-070/bin/python "typesafe-sdk==0.7.0"
/tmp/jev-070/bin/python /tmp/jev-probe.py
```

- [ ] **Step 5: Clean-env install with the extra and without it**

The extra does not exist in `pyproject.toml` yet, so this step installs the SDK alongside the package explicitly, using the chosen floor (shown for `0.6.0`; use `0.7.0` if Step 4 chose it). This proves the same resolution that `[jev]` will request.

Run, from the worktree root:
```bash
uv venv /tmp/jev-clean --python 3.11
uv pip install --python /tmp/jev-clean/bin/python -e ".[dev]" "typesafe-sdk>=0.6.0"
uv pip check --python /tmp/jev-clean/bin/python
uv pip list --python /tmp/jev-clean/bin/python | grep -Ei '^(typesafe-sdk|httpx|httpx2|openai|instructor|pydantic|pydantic-core) '
```
Expected: the install resolves, `uv pip check` prints `All installed packages are compatible` (or the equivalent no-conflict message), and the list shows `httpx` and `httpx2` side by side with `typesafe-sdk` at the newest release. If the install or the check reports a conflict, STOP and report it (Error path).

Then confirm that a plain install pulls in nothing new:
```bash
uv venv /tmp/jev-plain --python 3.11
uv pip install --python /tmp/jev-plain/bin/python -e .
uv pip list --python /tmp/jev-plain/bin/python | grep -Ei '^(typesafe-sdk|httpx2) ' && echo "UNEXPECTED" || echo "plain install clean"
```
Expected: `plain install clean`.

- [ ] **Step 6: Confirm import behavior and the suite in the clean env**

Run, from the worktree root:
```bash
/tmp/jev-clean/bin/python -c "import sys, py_ai_toolkit; assert 'typesafe_sdk' not in sys.modules, 'py_ai_toolkit imported typesafe_sdk'; print('import ok, sdk not loaded')"
/tmp/jev-clean/bin/python -c "import importlib.metadata as md; print('requires_python:', md.metadata('typesafe-sdk')['Requires-Python'])"
/tmp/jev-clean/bin/python -m pytest tests/ --ignore=tests/test_run_task.py -q
```
Expected: `import ok, sdk not loaded`; `requires_python: >=3.10` (which admits `>=3.11`; if it is higher than `>=3.11`, STOP and report, because the spec expects no higher floor); the suite passes with the same count as on the base branch.

---

### Task 2: Add the `jev` extra, lock it, install it in CI, and commit with the evidence

**Files:**
- Modify: `pyproject.toml:39-41` (append `jev` after the `docs` entry)
- Modify: `.github/workflows/test.yml:23` (install line)
- Modify: `uv.lock` (regenerated by `uv lock`)
- Verify unchanged: `MANIFEST.in`

**Interfaces:**
- Consumes: the floor `X.Y.Z` and the saved output from Task 1.
- Produces: the `jev` extra that sibling card 2.2 (`tests/unit/test_jev_adapter.py` with `pytest.importorskip("typesafe_sdk")`) relies on in CI and under `uv run --extra jev`.

- [ ] **Step 1: Write the failing check**

There is no test file for this card (spec "Tests"). The RED check is a shell assertion against the packaging files. Run, from the worktree root:
```bash
python3 - <<'EOF'
import tomllib
d = tomllib.load(open("pyproject.toml", "rb"))
extras = d["project"]["optional-dependencies"]
assert "jev" in extras, "no jev extra"
assert extras["jev"] == ["typesafe-sdk>=0.6.0"], extras["jev"]
assert not any("typesafe" in r for r in extras["dev"]), "sdk leaked into dev"
assert d["project"]["version"] == "0.7.0"
assert d["project"]["requires-python"] == ">=3.11"
print("pyproject ok")
EOF
grep -qF 'pip install -e ".[dev,jev]"' .github/workflows/test.yml && echo "ci ok" || { echo "ci missing jev"; exit 1; }
```
If Task 1 chose `0.7.0`, use `"typesafe-sdk>=0.7.0"` in the assertion (and in Step 3).

- [ ] **Step 2: Run it to verify it fails**

Expected: `AssertionError: no jev extra`.

- [ ] **Step 3: Add the extra to `pyproject.toml`**

Replace:
```toml
docs = [
    "mkdocs",
]
```
with:
```toml
docs = [
    "mkdocs",
]
jev = [
    "typesafe-sdk>=0.6.0",
]
```

- [ ] **Step 4: Change the CI install line**

In `.github/workflows/test.yml`, replace:
```yaml
        pip install -e ".[dev]"
```
with:
```yaml
        pip install -e ".[dev,jev]"
```
Leave the `Run tests` step unchanged.

- [ ] **Step 5: Regenerate the lock and verify it is additive**

Run, from the worktree root:
```bash
git ls-files --error-unmatch uv.lock
uv lock
python3 - <<'EOF'
import subprocess, tomllib
old = tomllib.loads(subprocess.run(["git", "show", "HEAD:uv.lock"], capture_output=True, text=True, check=True).stdout)
new = tomllib.load(open("uv.lock", "rb"))
o = {p["name"]: p["version"] for p in old["package"] if "version" in p}
n = {p["name"]: p["version"] for p in new["package"] if "version" in p}
changed = {k: (o[k], n[k]) for k in o if k in n and o[k] != n[k]}
removed = sorted(set(o) - set(n))
added = sorted(set(n) - set(o))
print("changed:", changed)
print("removed:", removed)
print("added:", added)
assert set(changed) <= {"py-ai-toolkit"}, f"existing pins changed: {changed}"
assert not removed, f"packages removed: {removed}"
assert "typesafe-sdk" in added and "httpx2" in added, added
EOF
grep -n 'provides-extras' uv.lock
```
Expected: `git ls-files` prints `uv.lock`; the script prints `changed: {'py-ai-toolkit': ('0.6.1', '0.7.0')}` (or `{}`), `removed: []`, and `added` includes `typesafe-sdk` and `httpx2`; `provides-extras` lists `"dev", "docs", "jev"`. If the assertion fails on `changed`, STOP and report it as a conflict (Error path). Do not hand-edit the lock.

- [ ] **Step 6: Run the check to verify it passes**

Re-run the Step 1 commands.
Expected: `pyproject ok` and `ci ok`.

- [ ] **Step 7: Confirm `MANIFEST.in` and the staging scope**

Run:
```bash
git diff --quiet HEAD -- MANIFEST.in && echo "MANIFEST.in unchanged"
git status --porcelain
```
Expected: `MANIFEST.in unchanged`. It holds only legacy `include`/`recursive-include` lines for README/LICENSE/tests and the old `ait` package, and the extra adds no package data, so it needs no change. `git status` shows only `pyproject.toml`, `.github/workflows/test.yml`, `uv.lock` (plus `.gitignore` if present, which must stay unstaged).

- [ ] **Step 8: Run the verification gate**

Run, from the worktree root:
```bash
uv run pytest tests/ --ignore=tests/test_run_task.py
uv run --extra dev --extra jev pytest tests/ --ignore=tests/test_run_task.py
git diff --name-only --diff-filter=d main...HEAD -- '*.py' | xargs -r ruff check --select E,F
```
Expected: both pytest runs pass with the same count as Task 1 Step 6. The lint command produces no output because no `.py` files change.

- [ ] **Step 9: Commit**

Stage only the three packaging files. Paste the probe and install lines saved in Task 1 into the Evidence section verbatim. If Task 1 chose `0.7.0`, change the floor line and the rationale to say which attribute 0.6.0 lacked.

```bash
git add pyproject.toml .github/workflows/test.yml uv.lock
git commit -F - <<'EOF'
chore: add jev optional extra (typesafe-sdk>=0.6.0)

Add `jev = ["typesafe-sdk>=0.6.0"]` to [project.optional-dependencies]
and install `.[dev,jev]` in CI so the Jev adapter tests from later
cards run there. Core dependencies, requires-python (>=3.11) and the
version (0.7.0) are unchanged. uv.lock regenerated additively: it adds
typesafe-sdk, its transitive deps (httpx2, tenacity, ...) and the jev
extra, and refreshes the stale py-ai-toolkit self-version
0.6.1 -> 0.7.0. No existing pin changed.

Floor rationale:
- 0.5.7: Score.criteria is an int-keyed dict (pre-0.6.0 shape), which
  the adapter does not target.
- 0.6.0: AsyncTypeSafeClient.system_one present; SystemOneResponse has
  nouls, choices, scores; Score.criteria is an ordered sequence. This is
  the oldest release with the shape the adapter maps, so the floor is
  >=0.6.0 (no ceiling).

Resolver compatibility: a clean venv (Python 3.11) with `.[dev]` plus
typesafe-sdk>=0.6.0 resolves with no conflict; `uv pip check` is clean.
httpx2 installs alongside httpx with no conflict against openai or
instructor. A plain install (no extra) pulls in neither typesafe-sdk nor
httpx2, and `import py_ai_toolkit` does not load typesafe_sdk.

Python: typesafe-sdk declares Requires-Python >=3.10, which admits our
>=3.11. No higher floor needs documenting.

MANIFEST.in needs no change: no new non-Python package data.

Evidence:
<paste the Task 1 Step 2, 3 and 5 output lines here>
EOF
git show --stat HEAD
```
Expected: the commit lists exactly `pyproject.toml`, `.github/workflows/test.yml` and `uv.lock`. Before running, replace the `<paste ...>` line with the actual saved output. Do not commit with that line still in place.
