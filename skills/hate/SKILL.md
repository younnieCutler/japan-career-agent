---
name: hate
disable-model-invocation: true
description: >
  User-invoked adversarial review of one consequential career plan or decision. Return the single
  load-bearing objection and the cheapest test that could falsify it.
license: MIT
---

# hate — adversarial decision review

This is deliberately user-invoked. A permanently automatic objection reflex would distort the
user's decision process and make every ordinary preparation task defensive.

## Goal

Attack one user-approved strategy or decision plan and reduce the result to one root objection plus
one cheap falsification test. The user still owns the decision.

## Workflow

1. Identify the exact decision and the assumptions it needs.
2. Check the strongest failure axes: false facts, unsupported inference, missing evidence, hidden
   trade-off, unsafe scope, or a result assumed before it exists.
3. Collapse related findings into one load-bearing root.
4. Name the cheapest test that could show the root matters or does not matter.
5. Return the objection and test for user review before the plan continues.

## Rules

- Run only after explicit user opt-in or an explicitly user-confirmed consequential-decision policy.
- Do not produce a total, hiring prediction, recommendation, or decision on the user's behalf.
- Do not average independent axes or hide a confirmed hard conflict.
 - One root and one test; no checklist expansion.
- This Skill is read-only and never invokes another Skill.

## Gate D terminal semantics

- No meaningful load-bearing objection survives → report `completed`.
- A load-bearing objection is found → report `needs_approval` with the `{root, first_nail}` summary;
  the plan must pause for the user's review before any dependent Quality Skill runs.
- Do not report an objection as `completed` merely because the analysis itself finished.

## Verification

Report `{root, first_nail}` with the evidence behind the objection. If no load-bearing objection
survives, say so and name the assumptions that remain Unknown.

Adaptation notice: [`../../_shared/THIRD_PARTY_NOTICES.md`](../../_shared/THIRD_PARTY_NOTICES.md).
