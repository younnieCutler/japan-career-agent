# Gate D Quality Skill Renames

## Goal

Rename the five Gate D quality Skills to short, purpose-led canonical names.

## Approved mapping

| Current | New | Purpose |
|---|---|---|
| `debloat` | `trim` | Compress an artifact without changing supported meaning. |
| `factchk` | `factcheck` | Audit external facts against dated sources. |
| `hate` | `challenge` | Find one load-bearing objection to a consequential plan. |
| `readchk` | `intent` | Check that a costly request is understood correctly. |
| `sip` | `verify` | Perform final read-only artifact verification. |

## Scope

- Rename the five `skills/<name>/` directories and their frontmatter/headings.
- Replace the names in the runtime registry, Gate D policy, CLI-facing quality options, tests,
  packaging metadata, README tables, orchestration references, and third-party notices.
- Keep old spellings in historical changelog entries and append-only historical records; do not
  rewrite user Vault state or generated data.
- Use the new names for all newly generated plans and invocation records. No separate alias layer
  is added because this is an intentional canonical-name change.
- Bump the project release version and document the rename in the changelog; synchronize generated
  manifests and release metadata through the repository's existing version owner.

## Verification

- Add or update the smallest registry/plan tests that prove the new names are discoverable, old
  names are not canonical options, and each Gate D chain emits the new names in order.
- Run focused Career Agent tests, packaging/reference checks, `git diff --check`, and the full
  `scripts/run_all_checks.py` suite before reporting completion.
