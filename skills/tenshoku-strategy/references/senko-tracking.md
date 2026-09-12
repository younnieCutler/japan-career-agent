# 選考トラッキング — current state and application learning

`data/pipeline.yml` remains the workspace source of truth for the **current company-level kanban**.
Use `scripts/pipeline.py` for ordinary current-state writes and do not edit action-item `checked`
values from a skill.

Application history is different from current company state. When the user wants to learn across
applications, load `job-search-learning-loop.md` and use `data/applications.yml` through the shipped
`job_search_learning.py` CLI. One company can have multiple application ids over time; an older
outcome must not be overwritten by a later application.

## Current pipeline fields

For ordinary current-state tracking, record the company slug, channel, stage, status, deadline,
source, and user-owned next action. The historical fields below remain readable for existing
workspaces:

- `reached_stage`;
- `feedback_obtained`;
- `agent_feedback`;
- `root_cause`;
- `demo_slot`;
- `gate_override`.

`root_cause`, `agent_feedback`, and `feedback_obtained` are legacy coarse learning fields. Do not use
them as the canonical evidence model for new Job Search Learning Loop records. New learning evidence
belongs in `data/applications.yml` as typed observations and user-confirmed classifications.

Do not infer a cause from silence, a template rejection, a company stereotype, nationality, channel,
or stage. Absence of feedback is `Unknown`, not a negative signal.

## New deterministic learning analysis

Run:

```bash
python skills/tenshoku-strategy/job_search_learning.py --workspace "$CAREER_WORKSPACE" report
```

The report keeps separate:

1. repeated direct employer/recruiter feedback;
2. recurring pre-application matching gaps;
3. repeated candidate self-observations;
4. descriptive reached-stage observations;
5. missing or unclassified feedback evidence.

A repeated matching gap is not a rejection cause. A candidate self-observation is not employer
feedback. An LLM-proposed theme is not counted until the user confirms it. Repeated direct feedback
requires at least two **distinct employers**, not merely two applications to the same employer.

The v3 `Decision Status` is not measured against a hiring outcome. `Proceed`, `Review`, and
`Conflict` remain diagnostic states. No workflow table turns them into a rate, rank, or grade.

## Legacy calibration compatibility

`scripts/calibrate.py` remains available for old `pipeline.yml` workspaces and its historical
`root_cause` / `rules.yml` flow. Do not feed new structured learning evidence into that global rule
promotion path. Job Search Learning Loop V1 stops at `eligible_for_review`; it never writes
`rules.yml` automatically.

The separate `legacy_v1` tier viewer remains opt-in only through:

```bash
python scripts/legacy_calibrate.py --legacy-experimental
```

## Output template

```markdown
# 選考学習 — [date]

## Repeated direct feedback
[theme + distinct employers + application ids + observed scope]

## Recurring diagnostic gaps
[gap + application ids + any direct-feedback support + causal conclusion: Unknown]

## Repeated self-observations
[theme + application ids; employer confirmation shown separately]

## Reached-stage observations
[descriptive counts only when the sample floor is met]

## Unknown / unclassified
[applications with no direct reason or no user-confirmed theme]
```

Always preserve evidence provenance and dates. Do not recommend stopping an application from one
pattern; show what is confirmed, what remains unknown, and what the user may choose to verify in the
next application batch.
