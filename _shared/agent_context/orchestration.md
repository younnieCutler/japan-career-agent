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
results into the plan: `plan-next` and `plan-status` expose a read projection of the immediate
dependency's summary, error, artifacts, evidence, tools, and signals.

Each step declares its output contract. Artifact-producing steps must report at least one artifact;
`sip` must report an artifact reference. A completed invocation that violates its step contract
blocks the plan even though the original invocation row remains append-only and auditable.

The first plan policy is the flat `career-document → humanize-japanese-career → sip` chain. A
Quality Skill never invokes another Skill; Gate D owns ordering. Existing unplanned `skill-open` /
`skill-report` callers continue to work unchanged.
