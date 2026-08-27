---
name: trim
disable-model-invocation: true
description: >
  User-invoked compression pass for an otherwise correct career artifact. Preserve every evidence
  claim, rule, source, uncertainty, and confidentiality boundary while cutting nonessential words.
license: MIT
---

# trim — load-bearing artifact compression

Use only when the user requests a shorter artifact or a real length constraint makes compression
necessary. A long document is not automatically bloated.

## Goal

Produce a new non-canonical artifact with the same supported meaning and less padding. The original
artifact remains untouched so the user can compare the change.

## Workflow

1. Read the complete artifact and identify the claims and rules every section must preserve.
2. Cut padding, repeated process prose, and empty qualifiers in place.
3. Preserve employer, period, role, action, individual contribution, team result, metric, source,
   uncertainty, confidentiality, and approval wording exactly in strength.
4. Write a new relative output only after confirming the input exists.
5. Hand the new artifact to the following `verify` check.

## Rules

- Never create or estimate a metric.
- Never turn `Unknown` into a claim, or `team_result` into `individual_contribution`.
- Never overwrite the source artifact or canonical Vault state.
- If the problem is stale content or duplicated sources, stop and report that `re0`/`ssotize` would
  be a different operation; neither is part of this plan.
- This Skill is user-invoked and never invokes another Skill.

## Verification

Report the input and new output paths, preserved claim categories, and the exact deterministic
check that must run next. If no genuine bloat exists, make no output and report why.

Adaptation notice: [`../../_shared/THIRD_PARTY_NOTICES.md`](../../_shared/THIRD_PARTY_NOTICES.md).
