# Evidence Review Rules

These rules implement the repository-wide decision contract for `job-seeker-agent`.

## 1. Requirement states

Use the exact JD wording where possible. For every requirement record candidate evidence, job
evidence, source, observed date, confidence, and provenance.

| State | Meaning |
|---|---|
| `Matched` | Candidate evidence and the JD requirement are both present and comparable. |
| `Missing` | The JD requirement is confirmed, but the candidate evidence does not demonstrate it. |
| `Unknown` | Either side is absent, stale, contradictory, or not comparable. |

For hard eligibility, a `Conflict` is a decision-level result only when both sides are confirmed and
disagree. A one-sided gap remains `Unknown` until the missing side is confirmed. Never replace an
unknown with `Borderline`, a default pass, or a numeric outcome estimate.

Example:

```text
Requirement: Spark in production
Candidate: no confirmed production evidence
JD: required, source=job_posting, observed_at=2026-08-03
State: Unknown until the candidate's production history is confirmed; if absent after confirmation,
       report Missing — importance: core.
Next question: Which production data-pipeline tools did you operate, and in what scope?
```

If a confirmed hard conflict exists, say:

> Confirmed hard conflict: [requirement]. Continuing is the user's choice; this requirement remains
> a material risk unless the hiring team confirms an exception.

## 2. Skill evidence

- Do not assign a default skill level.
- Job title, intention to learn, a course, or a keyword alone is not demonstrated experience.
- Record the exact action, context, scope, recency, result, and repeatable method when available.
- A missing core skill is not a reason to discount unrelated skills with a coefficient. Report the
  missing core evidence, its implication, and a possible retargeting or verification path.
- A legacy 1–5 `portable_skills` value is read-only history. Never reshape it into MHLW allocation.

## 3. Provenance and confidence

Use:

```yaml
source_type: user | job_posting | company_public_source | official_framework | observed | derived | heuristic | unknown
source_ref: "resume line, URL, note id, or conversation date"
observed_at: "YYYY-MM-DD"
confidence: high | medium | low | unknown
provenance: official_framework | job_posting | company_public_source | user | observed | derived | heuristic | synthetic | unknown
```

`heuristic` is a hypothesis. It cannot determine Eligibility, a requirement state, or Decision
Status. A stale or low-confidence item is surfaced as such rather than silently promoted.

## 4. User review and override

Present the evidence table before drafting. The user may correct, remove, or confirm each item. If
they choose to continue after a conflict, record the choice as `gate_override: true` or a user event;
the objective conflict remains unchanged.
