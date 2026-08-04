# Contributing

This repository is an evidence-based, local-first career decision-support system. Keep changes
within the requested scope and preserve `Unknown`, confirmed conflicts, independent interest, and
legacy read-only compatibility.

## Before opening a change

- Read `AGENTS.md` and the relevant `_shared/agent_context/` reference.
- Do not add candidate-outcome percentages, composite scores, proprietary recruiter-algorithm
  claims, fabricated evidence, or automatic application/message actions.
- Keep external claims dated, sourced, confidence-labelled, and freshness-checkable.
- Do not include personal resumes, Vault files, pipeline data, or secrets.

## Verification

Run the deterministic checks relevant to the change. For a repository-wide change, run the same
Ubuntu/Windows matrix used by CI:

```bash
python -m pip install -r requirements.txt
python -m pip install "ruff>=0.8,<1"
python scripts/run_all_checks.py
```

`run_all_checks.py` is the canonical repository verification path and mirrors the Ubuntu/Windows
CI matrix, including documentation and release-version consistency checks.

When changing a writer or schema, also run its focused tests and one lifecycle smoke test. Verify
Windows path handling and retry/idempotency behavior when applicable. Context-budget changes require
the reason and baseline evidence to be recorded; token reduction without semantic regression tests
is not acceptable.

## Release lifecycle

Pushes to `main` run `.github/workflows/release.yml`. The workflow installs the verification
dependencies, runs `python scripts/run_all_checks.py`, then reads the current release identity and
creates an annotated `vX.Y.Z` tag only when that tag is absent. An existing tag must resolve to the
same verified `main` commit; reusing a release version for another commit fails. The workflow then
creates the GitHub Release when it does not already exist. The local consistency check is:

```bash
python scripts/check_release_tag.py --tag vX.Y.Z --sha <verified-commit>
```

## Version and release docs

Any behavior change or bug fix under `skills/`, `_shared/`, `scripts/`, or `hooks/` (a fix counts —
this is not only for new features) bumps the version in **both** `.claude-plugin/plugin.json` and
`.codex-plugin/plugin.json`, adds a `CHANGELOG.md` entry, and updates the `Current release` line in
all three READMEs. `scripts/check_version_bump.py` enforces this: it diffs the PR against
`origin/main` and fails if a substantive (non-`test_*`, non-`.md`) file changed under those
directories with no version change. It skips cleanly for a genuinely docs/test-only PR, and skips
locally when `origin/main` hasn't been fetched — `git fetch origin main` before running
`run_all_checks.py` if you want the same signal CI gets. Do not check the PR template's "versions
are consistent" box by leaving the version untouched; consistency is checked only after the bump.

## Pull requests

Describe the decision or contract changed, list files touched, include regression tests, and state
any remaining limitation. Keep unrelated cleanup in a separate change. A maintainer reviews and
merges; the author should still perform the self-review checklist in the pull-request template.
