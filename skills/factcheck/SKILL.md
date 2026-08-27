---
name: factcheck
description: >
  Audit external world claims in a Career Agent artifact against cited sources in both directions.
  Use when a result asserts a company, market, role, date, policy, or other externally checkable fact.
license: MIT
---

# factcheck — external claim audit

This is a source audit for external claims. Confirmed personal career evidence remains governed by
the Vault approval and provenance contracts rather than being reinterpreted here.

## Goal

Determine whether each material external claim is supported by an accessible, dated source and
whether an apparently obvious or implausible claim needs the opposite check. Leave uncertainty
visible when a source cannot be reached.

## Workflow

1. Enumerate claims presented as facts about the external world.
2. Locate the source, observation date, confidence, and provenance already attached to each claim.
3. Verify the claim against the source and check the reverse possibility when the claim is novel,
   implausible, or based only on intuition.
4. Report each claim as confirmed, contradicted, stale, low-confidence, or unknown.
5. Return the audit as a report; the Host or user decides whether to create a corrected artifact.

## Rules

- Do not invent sources, dates, quotations, market numbers, company culture, or legal conclusions.
- Do not turn a missing source into a pass or a score.
- Do not modify `events.jsonl`, `career-state.toml`, `data/pipeline.yml`, or a canonical profile.
- A blocked external source is `Unknown`, not evidence from memory.
- This Skill is read-only and never invokes another Skill.

## Gate D terminal semantics

- All material claims are acceptable and traceable → report `completed`.
- A material contradiction → report `blocked`; the incorrect artifact must not flow to `verify`.
- A required claim cannot be verified safely → report `needs_approval` when the user must decide how
  to proceed, or `blocked` when no safe continuation exists.
- A stale, low-confidence, or unknown claim is included in the summary so the next step receives the
  exact uncertainty rather than treating `completed` as a clean fact pass.

## Verification

Every verdict must name its source or explicitly say that verification was unavailable. Report
`blocked` or `failed` when a required claim cannot be safely checked; do not report an empty pass.

Adaptation notice: [`../../_shared/THIRD_PARTY_NOTICES.md`](../../_shared/THIRD_PARTY_NOTICES.md).
