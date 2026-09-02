# Maintainer runbook

Everything needed to verify, release and repair this repository, with the commands and what a
passing result looks like. Written so it can be followed by someone who has not read the commit
history.

`CONTRIBUTING.md` is the short form for contributors. This is the long form for whoever presses the
release button.

---

## 1. Local verification

```bash
python -m pip install --require-hashes -r requirements.lock
python -m pip install --require-hashes -r requirements-dev.lock
git fetch origin main            # feeds the version-bump gate; it skips cleanly without this
python scripts/run_all_checks.py
```

Expected: `All 95 repository checks passed.` and exit 0. The suite is fail-fast, so a failure names
the check and stops; everything after it is unrun, not passing.

That number is held to `len(CHECKS)` by `scripts/check_docs_drift.py`; adding a check to the matrix
and leaving this line alone fails the build rather than quietly going stale, which is how it came to
claim 70 while the matrix had grown to 90.

Install the hash-pinned locks, not `requirements.txt`. The loose `ruff` range there resolves a
different linter version than CI, so local and CI disagree for reasons unrelated to the change.

**Before pushing anything that touches a test, reproduce CI's tree.** Your working tree is not a
checkout: it has ignored files CI will not have, and CI has nothing else. Both directions have
caused real failures — a test asserting on `/data/pipeline.yml`, which is ignored working state,
passed locally and failed on all three runners; and `ruff` linting a plugin host's skills failed
locally while CI was clean.

```bash
git clone --local --no-hardlinks --branch <your-branch> . /tmp/cleanclone
cd /tmp/cleanclone && python scripts/run_all_checks.py
```

`--local` makes this a few seconds, and ignored files do not come along. If a test references a
repository file, `git ls-files <path>` first: an untracked path is a path CI does not have.

**If ruff fails on files you did not write.** `ruff check .` walks the working tree and honours
`.gitignore`. A plugin host that installs skills into `.agents/skills/` is ignored by name; a host
that installs somewhere else is not. Add the path to `.gitignore` rather than deleting the files.

**If `release integrity` fails with "release requires a clean working tree".** That check builds a
real release bundle, which requires a committed tree. Commit first; it is not a code failure.

**If `wheel install smoke` fails with `No module named build`.** The dev lock is not installed. See
the two `pip install` lines above.

## 2. Focused verification

Run the check that owns what you changed, then the full suite once before pushing.

| Changed | Run |
|---|---|
| `skills/career-agent/` module layout | `python scripts/check_career_agent_boundaries.py`, `python scripts/test_career_agent_boundaries.py`, `python skills/career-agent/test_boundary_imports.py` |
| Any CLI behaviour | `python skills/career-agent/test_golden_cli.py`, `python scripts/test_e2e_career_os.py` |
| `_shared/schemas.yml` or a canonical writer | `python scripts/check_schema_contract.py`, `python scripts/test_schema_contract.py` |
| User-facing wording | `python skills/career-agent/test_ux.py`, `python skills/career-agent/test_ux_regression_eval.py`, `python skills/career-agent/test_localization.py` |
| Any README | `python scripts/check_readme_consistency.py`, `python scripts/check_release_consistency.py` |
| `docs/CAPABILITY_MATRIX.md` | `python scripts/check_capability_matrix.py` |
| Packaging | `python scripts/test_pyproject_install.py`, `python scripts/test_npm_bootstrapper.py` |

## 3. CI matrix

`.github/workflows/test.yml` runs on every push and pull request: ubuntu/3.11, **windows/3.11**,
ubuntu/3.13. Each job installs both locks, runs `run_all_checks.py`, then builds a release bundle
and smoke-tests installing from it.

Windows is not a formality. Path handling, newline handling and file locking differ there, and it is
where a change to persistence or the Vault fails first.

`.github/workflows/canary.yml` runs weekly against an external endpoint with `continue-on-error`. A
red canary is information, not a broken build.

## 4. Version bump

A change to a non-test, non-`.md` file under `skills/`, `_shared/`, `scripts/` or `hooks/` — a bug
fix counts — requires a version bump. `scripts/check_version_bump.py` fails the build otherwise.

Bump **first**, at the start of the branch, so every intermediate commit is consistent rather than
only the last one.

`pyproject.toml` is the single source of truth. Everything else that names the version is a
generated copy: the two plugin manifests, the npm bootstrapper and `sbom.cdx.json` are all written
by `scripts/sync_version.py`, and nothing reads a version out of them. `build_release.py`,
`build_sbom.py`, `check_version_bump.py` and `release.yml` all go through
`sync_version.canonical_version()`.

Edit two files by hand, then run one command:

| File | What to change |
|---|---|
| `pyproject.toml` | `version` — the only version you type |
| `CHANGELOG.md` | a new `## [X.Y.Z] - YYYY-MM-DD` heading at the top |

```bash
python scripts/sync_version.py     # writes both plugin manifests, the npm package, and the SBOM
```

One prose paragraph still moves with a release: the release-channel section in `docs/upgrading.md`
and its `_ko` / `_ja` translations names both the source version and the marketplace ref. It is not
generated, because it explains the gap rather than restating a number — but
`check_release_consistency.py` reads both numbers from the files that own them, so it cannot go
stale silently.

The READMEs no longer carry a version at all; the release badges are dynamic.

`.agents/plugins/marketplace.json`'s `ref` is **not** bumped here. See §7.

Then:

```bash
python scripts/check_release_consistency.py     # expect: release consistency: vX.Y.Z
python scripts/sync_version.py --check          # expect: version sync: vX.Y.Z (copies agree)
```

## 5. Release dry run

```
Actions → release → Run workflow → dry_run: true
```

Runs the full suite, builds the bundle, verifies it, and smoke-tests the unpacked install — without
creating a tag, a GitHub Release, or publishing anything. Dispatching with neither `publish` nor
`dry_run` is a successful no-op, which is what lets stacked PRs keep version identities without
publishing every intermediate one.

## 6. Publish

Preconditions, all enforced by the workflow:

- the branch is `refs/heads/main`
- `HEAD` equals `origin/main`
- `run_all_checks.py` passes
- the `vX.Y.Z` tag either does not exist, or resolves to this exact commit

```
Actions → release → Run workflow → publish: true
```

In order: verify → build bundle → verify bundle → smoke-test bundle → upload artifact → create or
verify the annotated tag → `check_release_tag.py` → `check_release_consistency.py --require-tag` →
GitHub Release with generated notes → stage the verified wheel → PyPI via Trusted Publishing (OIDC,
`skip-existing: true`) → npm with provenance.

The npm step is skipped gracefully when `NPM_TOKEN` is absent, so PyPI can succeed alone. That is a
partial release; see §8.

The wheel that reaches PyPI is the one `verify_release.py` already checked, not a rebuild. A rebuild
would be a second artifact nobody verified.

## 7. Registry and marketplace verification

The workflow's `verify-published` job already does the substantive check: it installs the published
PyPI distribution, runs the same smoke as the local wheel check, asserts the installed tree carries
the GUI bundle and all eighteen Skill manifests, and then runs the README's own quick-start commands
against the published npm entry point. Read its log before doing anything by hand — that job exists
because a published wheel once shipped one Skill and no GUI while every repository check was green.

To confirm by hand, or to check a release published before that job existed:

```bash
python scripts/test_pyproject_install.py --pypi X.Y.Z   # the same assertions, on demand
npm view japan-career-agent version
gh release view vX.Y.Z --json tagName,assets
```

Then, and only then, move the stable marketplace channel:

```bash
# .agents/plugins/marketplace.json → plugins[0].source.ref → "vX.Y.Z"
python scripts/check_manifest_consistency.py    # the ref must be an immutable vX.Y.Z, never a branch
python scripts/check_release_consistency.py
```

The ref moves **after** publish, not with the version bump, because it points at a tag that does not
exist until the release workflow creates it. The release-channel section in `docs/upgrading.md` and
its `_ko` / `_ja` translations names both numbers — the source version and the current ref — and
`check_release_consistency.py` fails if either goes stale. While they differ, that section is what
tells a user which one they will get.

## 8. Failed publish recovery

The tag and the GitHub Release are created before publishing, so a registry failure leaves a real
tag pointing at a verified commit. Do not delete it and do not re-tag.

| Failure | What happened | Do |
|---|---|---|
| PyPI rejected the upload | Nothing published | Fix the cause, re-dispatch `publish` on the same commit. `skip-existing: true` makes this safe. |
| PyPI succeeded, npm failed | Half the release is live | Re-dispatch on the same commit. PyPI skips, npm retries. |
| Both succeeded, the artefact is wrong | Published and immutable | **Do not yank and reuse the version.** Fix forward with a new patch version. A version that ever resolved to one artefact must never resolve to another. |
| The tag exists on the wrong commit | The gate refuses to reuse it | Release a new patch version. Moving a published tag breaks every checksum anyone recorded. |
| The npm bootstrapper pins a version PyPI does not have | `npx` installs nothing | Publish the PyPI version, or patch `packaging/npm/package.json` and release again. `test_npm_bootstrapper.py` pins the two together. |

Verify any bundle, including one someone else downloaded:

```bash
python scripts/verify_release.py --manifest release-manifest.json --checksums SHA256SUMS \
    --artifact <bundle.zip> --sbom sbom.cdx.json
```

It accepts both `japan-career-agent` and the pre-2.1.0 `japan-recruit-ai-agent` product name,
permanently. A bundle someone already downloaded cannot be re-stamped, and a verifier that rejected
it would stop checking the releases still in circulation.

## 9. Compatibility policy

Three surfaces are permanent, not transitional:

- `verify_release.py` accepts both product names.
- `JAPAN_RECRUIT_NO_UPDATE_CHECK` still disables the update check alongside `JAPAN_CAREER_NO_UPDATE_CHECK`.
- The `wheel` key in a release manifest is optional, so 2.0.x bundles still verify.

`runtime.__all__` is the Python import surface. Removing a name from it is a breaking change; see
[`ARCHITECTURE_BOUNDARIES.md`](ARCHITECTURE_BOUNDARIES.md).

Deprecating anything: keep it working for one minor version with a `CHANGELOG.md` entry naming the
replacement, then remove it in the next minor with a second entry. Never in a patch.

## 10. Schema migration

`_shared/schemas.yml` feeds two validators built from one catalog. `validate_document` reads and
accepts unknown properties; `validate_new_write` writes and rejects them, using a strict schema
derived in code.

**Adding a field.** Add it to `$defs` under the object that owns it, and to the descriptive section
below for its meaning. Leave the type off unless every historical record already satisfies it — both
validators read one property list, so a type is also a new rejection on the read path. Add a
producer test to `scripts/test_schema_contract.py`.

**Freezing a field.** Add the name to `legacy_field_policy.fields`. It stays in `properties` so it
still reads; `validate_new_write` refuses it at any depth. Add a fixture to
`_shared/tests/fixtures/legacy/` with `writable: false`.

**Changing a shape.** Do not. Add the new shape beside the old one and let the reader accept both,
as `history` does with `id` and `event_id`. A migration cannot reach a file on someone else's disk.

Never edit a fixture in `_shared/tests/fixtures/legacy/` to make a test pass. The file on somebody's
disk did not change when the schema did.

Bump `schema_version` in `schemas.yml` when the shape a producer must write changes.

## 11. Security and private-data incidents

`scripts/check_private_data.py` runs early in the suite, deliberately: a leak that reaches a commit
is harder to undo than a failed build.

Install the guard, once per clone:

```bash
git config core.hooksPath .githooks
python scripts/check_private_data.py --staged
```

**If personal career data was committed but not pushed:** amend or reset, then re-run the check.

**If it was pushed:** the history is public. Rewriting it does not un-publish anything. Treat every
document in the commit as disclosed, tell whoever the data is about, and rotate anything credential
shaped. Then remove it from `main` and add the pattern to the guard so the same shape cannot return.

**If a secret was committed:** rotate it first. Removing the commit is the second step and does not
substitute for the first.

`docs/PRIVATE_CAREER_DATA_PRD.md` §13.3 has the store's own boundaries.

## 12. Restore-state semantics

`restore-state` is not undo. It replaces the current state snapshot and leaves `events.jsonl`,
`proposals.jsonl` and `data/pipeline.yml` exactly as they were, because the ledger is append-only:
a restore that also rewound it would delete history the user approved.

Tell users this in those words. "Rollback" invites them to expect the approvals to disappear too.
