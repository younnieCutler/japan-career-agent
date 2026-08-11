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

## Personal data protection

Enable the tracked commit hook once per clone:

```bash
git config core.hooksPath .githooks
```

It runs `scripts/check_private_data.py --staged` and blocks a commit that stages a probable
personal career document — including one force-added with `git add -f`, which ignore rules cannot
stop. Enabling it is a manual step because Git cannot install a hook by being cloned: `.git/hooks`
is not tracked content.

The same check runs in CI over every tracked file, so a clone without the hook still fails the pull
request — but only after the document has reached the remote, which is what the hook prevents. Both
layers are required; neither is sufficient alone.

If the check flags a synthetic fixture, declare it rather than weakening the detector: use a
`.example.` infix in the filename, or put a synthetic marker in the content (`synthetic://...`,
`provenance: synthetic`, or a statement that the subject is not a real person).

Putting a file under `examples/`, `tests/`, or `mock/` does **not** exempt it. A directory name is
a convention, not a statement about the bytes inside, and exempting those paths would make them the
easiest place to leak real data. See `docs/PRIVATE_CAREER_DATA_PRD.md` section 13.3.

## Verification

Run the deterministic checks relevant to the change. For a repository-wide change, run the same
Ubuntu/Windows matrix used by CI:

```bash
python -m pip install --require-hashes -r requirements.lock
python -m pip install --require-hashes -r requirements-dev.lock
python scripts/run_all_checks.py
```

These are the hash-pinned commands CI actually runs. Installing `requirements.txt` with a loose
`ruff` range instead resolves a different linter version than CI, so local and CI results can
disagree for reasons unrelated to the change.

`run_all_checks.py` is the canonical repository verification path and mirrors the Ubuntu/Windows
CI matrix, including documentation and release-version consistency checks.

When changing a writer or schema, also run its focused tests and one lifecycle smoke test. Verify
Windows path handling and retry/idempotency behavior when applicable. Context-budget changes require
the reason and baseline evidence to be recorded; token reduction without semantic regression tests
is not acceptable.

## Reference

Three documents carry what is otherwise only in the checks and the commit history:

- [`docs/MAINTAINER_RUNBOOK.md`](docs/MAINTAINER_RUNBOOK.md) — verification, release, registry
  publish, marketplace ref, failure recovery, schema migration, private-data incidents.
- [`docs/ARCHITECTURE_BOUNDARIES.md`](docs/ARCHITECTURE_BOUNDARIES.md) — the module layers, what
  `check_career_agent_boundaries.py` enforces, and how to add a command.
- [`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md) — what works with no plugin host, what a
  host improves, and what only a host can do.

## Release lifecycle

The runbook has the full procedure, including recovery. In short: releases are manual —
dispatch `.github/workflows/release.yml` from the verified release-bearing
`main` commit and explicitly select either `publish` or `dry_run`. Ordinary pushes never create an
intermediate tag or GitHub Release. The workflow installs the verification dependencies, runs
`python scripts/run_all_checks.py`, and creates an annotated `vX.Y.Z` tag only when that tag is
absent. An existing tag must resolve to the same verified `main` commit; reusing a release version
for another commit fails. The local consistency check is:

```bash
python scripts/check_release_tag.py --tag vX.Y.Z --sha <verified-commit>
```

Dispatching without `publish` or `dry_run` is a successful no-op. This explicit gate lets stacked
PRs keep required internal version identities without publishing every intermediate version.

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
