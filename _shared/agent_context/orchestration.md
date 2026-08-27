# Host-coordinated execution plans

Gate D is a bounded host-driven state machine, not a Python agent loop. The runtime creates a
linear plan, opens one linked Skill invocation, and returns the next step after the Host reports a
terminal result. Python never calls Claude/Codex or executes a Skill's SOP.

Use the existing lifecycle:

```text
plan → plan-next → skill-open(plan_id, step_id) → Host SOP → skill-report → plan-next
```

Plan snapshots are workflow state under `02-state/execution-plans/`. Career facts remain in the
approval-gated event ledger, company state remains in `data/pipeline.yml`, and invocation results
remain in `02-state/invocations.jsonl`. Do not create a second invocation ledger or copy terminal
results into the plan: `plan-next` and `plan-status` expose `dependency_result` for the immediate
dependency and `artifact_context` for the closest upstream non-empty artifact, each projected from
the invocation ledger with summary, error, artifacts, evidence, tools, and signals.

Each step declares its output contract. Artifact-producing steps must report at least one artifact;
`verify` must report an artifact reference. A report that violates its contract is rejected before it
is appended, so the Host can submit a valid report for the still-open invocation.

`needs_input` resumes by rerunning the same Skill. `needs_approval` is different: `plan-next
--approval continue|abort` records a workflow resolution in the plan snapshot and never changes or
reruns the terminal invocation that requested approval. This is not Career evidence approval.

The policy is bounded and conditional. Gate D currently accepts only these Domain roots:
`career-document`, `kigyou-bunseki`, `jiko-bunseki`, and `tenshoku-strategy`; every other Skill
must be handled by its existing single-Skill workflow until a policy is explicitly added.

```text
career-document → humanize → trim? → factcheck? → verify
kigyou-bunseki → factcheck → verify
strategy → challenge? → trim? → factcheck? → verify?
```

`intent` is an explicit first step for high-cost or ambiguous requests. `factcheck` requires the
Host signal `external_claims_present`; generic `verify` requires `substantial_artifact`. `challenge` and
`trim` require explicit `--quality` opt-in. A Quality Skill never invokes another Skill; Gate D
owns ordering. Existing unplanned `skill-open` / `skill-report` callers continue to work unchanged.
