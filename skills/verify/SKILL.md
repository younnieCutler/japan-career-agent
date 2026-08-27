---
name: verify
description: >
  Final, read-only verification of a completed Career Agent artifact using the repository's own
  deterministic checks and evidence boundaries. Use as the terminal step of a Gate D plan; it never
  invokes another Skill or changes canonical career state.
license: MIT
---

# verify — final artifact verification

Run this Skill only after the preceding Domain and expression steps have produced their artifact.
The Host remains responsible for reading the artifact and reporting what the checks actually found.

## Goal

Confirm that the final artifact is readable, has the expected provenance, and passes the existing
deterministic gate appropriate to its kind. A pass is evidence that known checks passed; it is not a
hiring prediction or a guarantee that every sentence is faithful.

## Workflow

1. Identify the artifact paths reported by the preceding plan step.
2. Run the existing repository check that owns that artifact. For a 職務経歴書, use
   `career-agent document-check` before treating it as renderable.
3. Confirm that every material external claim still has its source, observed date, confidence, and
   provenance, when the artifact contains such claims.
4. Confirm that the artifact path exists and is the expected non-canonical projection.
5. Report `completed` with the commands and artifact paths, or report `blocked`/`failed` with the
   exact check and error. Do not repair the Vault, pipeline, or event ledger here.

## Rules

- This is a terminal verifier, not an orchestrator.
- Do not invoke `factcheck`, `trim`, `re0`, `ssotize`, or any other Skill from this SOP.
- Do not overwrite a rendered artifact or canonical career record.
- Preserve `Unknown`, source conflicts, confidentiality flags, and approval boundaries.
- A deterministic check passing is a floor, not permission to invent evidence.

## Verification

Return the same artifact references the plan supplied, the exact checks run, and a terminal
`skill-report` status. A completed report requires a non-empty summary; a failed or blocked report
requires the concrete error.

Adaptation notice: [`../../_shared/THIRD_PARTY_NOTICES.md`](../../_shared/THIRD_PARTY_NOTICES.md).
