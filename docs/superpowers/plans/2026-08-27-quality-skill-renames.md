# Gate D Quality Skill Renames Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the five Gate D quality Skills to `trim`, `factcheck`, `challenge`, `intent`, and `verify` everywhere the current repository treats their names as canonical.

**Architecture:** Keep the existing flat Skill registry and bounded Gate D state machine. Rename the five Skill directories and frontmatter, then update every executable registry/plan reference, test fixture, package inclusion, and human-facing reference. Historical Changelog text and append-only user data remain unchanged.

**Tech Stack:** Markdown Skill manifests, Python runtime/tests, TOML packaging metadata, JSON plugin manifests, Markdown documentation, Git.

---

### Task 1: Prove the new canonical names in tests

**Files:**
- Modify: `skills/career-agent/test_skill_invocation.py`
- Modify: `skills/career-agent/test_execution_plans.py`

- [ ] **Step 1: Replace quality-name expectations and paths in the focused tests.**

Use these exact replacements in test-only references:

```text
debloat -> trim
factchk -> factcheck
hate -> challenge
readchk -> intent
sip -> verify
```

Update the registry set, plan step assertions, quality option arguments, manifest paths, and SOP
content assertions. Keep the test that imports the quality option set aligned with the approved
new names.

- [ ] **Step 2: Run the focused tests and confirm the expected RED result.**

Run:

```bash
python -m unittest -v skills/career-agent/test_skill_invocation.py skills/career-agent/test_execution_plans.py
```

Expected: failure because the current registry and five old Skill directories still expose the old
names.

### Task 2: Rename manifests and update executable contracts

**Files:**
- Rename: `skills/debloat/` → `skills/trim/`
- Rename: `skills/factchk/` → `skills/factcheck/`
- Rename: `skills/hate/` → `skills/challenge/`
- Rename: `skills/readchk/` → `skills/intent/`
- Rename: `skills/sip/` → `skills/verify/`
- Modify: `skills/career-agent/models.py`
- Modify: `skills/career-agent/execution_plans.py`
- Modify: `skills/career-agent/test_skill_invocation.py`
- Modify: `skills/career-agent/test_execution_plans.py`

- [ ] **Step 1: Rename the five Skill directories with Git.**

```bash
git mv skills/debloat skills/trim
git mv skills/factchk skills/factcheck
git mv skills/hate skills/challenge
git mv skills/readchk skills/intent
git mv skills/sip skills/verify
```

- [ ] **Step 2: Update each manifest's frontmatter, heading, and cross-references.**

Set each `SKILL.md` frontmatter `name` and title to its new name. Change the `trim` handoff to
`verify`, and change the `verify` forbidden-name list to use `factcheck` and `trim`.

- [ ] **Step 3: Update the runtime registry and Gate D plan policy.**

In `models.py`, replace the five keys in `SKILL_EXECUTION` and replace
`PLAN_QUALITY_OPTIONS` with:

```python
PLAN_QUALITY_OPTIONS = frozenset({"intent", "challenge", "trim"})
```

In `execution_plans.py`, replace `_QUALITY_SKILLS` and every quality-name membership, emitted step
name, error message, and lookup with the approved names. Preserve the existing step IDs
(`read`, `challenge`, `debloat`, `factcheck`, `verify`) unless they are the Skill key itself; only
the `debloat` step ID becomes `trim` so the persisted step identity matches the new Skill.

- [ ] **Step 4: Run the focused tests and confirm GREEN.**

```bash
python -m unittest -v skills/career-agent/test_skill_invocation.py skills/career-agent/test_execution_plans.py
```

Expected: PASS with the new five names discoverable and emitted by the Gate D plans.

### Task 3: Update package and human-facing references

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `README_ko.md`
- Modify: `README_ja.md`
- Modify: `_shared/agent_context/orchestration.md`
- Modify: `_shared/THIRD_PARTY_NOTICES.md`
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.codex-plugin/plugin.json`

- [ ] **Step 1: Replace current-name references outside historical Changelog entries.**

Update package inclusion paths, README skill tables, orchestration chains, third-party notices,
and current release documentation. Leave the existing `2.14.0` and `2.15.0` Changelog entries
unchanged so released history remains accurate.

- [ ] **Step 2: Bump the release version and add a current Changelog entry.**

Change the canonical `pyproject.toml` version from `2.18.0` to `2.19.0`, add a concise `2.19.0`
entry dated `2026-08-27` describing the five canonical name changes, then run the repository's
version synchronizer to update generated manifests and SBOM data.

```bash
python scripts/sync_version.py
```

- [ ] **Step 3: Check that only historical old-name references remain.**

```bash
rg -n -i '\b(debloat|factchk|hate|readchk|sip)\b' --glob '!data/**' --glob '!*.jsonl' .
```

Expected: only the intentional historical Changelog entries and any explicit migration/history
wording remain; executable code, current docs, tests, and package paths use the new names.

### Task 4: Verify the release

**Files:**
- Test: repository checks below

- [ ] **Step 1: Run focused checks.**

```bash
python -m unittest -v skills/career-agent/test_skill_invocation.py skills/career-agent/test_execution_plans.py
python scripts/check_reference_paths.py
git diff --check
```

- [ ] **Step 2: Run the full repository check suite.**

```bash
python scripts/run_all_checks.py
```

Expected: exit code 0 with registry, packaging, documentation, version, and focused Career Agent
checks passing.

- [ ] **Step 3: Review the final diff.**

```bash
git status --short
git diff --stat
git diff --name-status
```

Confirm that only the approved five Skill names, their direct references, release metadata, and
the two design/plan documents changed. Do not modify user Vault data or generated personal output.
