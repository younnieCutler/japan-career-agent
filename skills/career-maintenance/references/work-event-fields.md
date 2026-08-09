# Work event fields

Field meanings for the `work_event` payload, and the reasoning behind what is deliberately absent.
The machine contract is `validate_work_event()` in `skills/career-agent/validation.py`.

Every field is optional. An unfilled field is `Unknown`, and `Unknown` is a real answer, never a
prompt to guess.

## Context

A work event carries no `organization`, `team`, `project`, or `period` field. The event ledger
already records `company` and `occurred_at`, and a second copy of the same fact goes stale the
moment the first one changes. Project and team belong in `scope` when the user states them.

## Responsibility

| Field | Holds | Not |
|---|---|---|
| `role` | the role the user was assigned on this work | a title they did not have |
| `scope` | what they owned, with its size when stated | an estimated headcount or budget |

"실질적으로 리드했지만 직책은 리더가 아니었다" is recorded as what it is: the decisions they made,
who they coordinated, what they were accountable for. That is stronger evidence than a title claim
and it survives a reference check.

## Situation

`problem` — the situation and what was wrong. One sentence is enough.

## Action

| Field | Holds |
|---|---|
| `direct_actions` | what the user personally did |
| `stakeholder_coordination` | who was aligned, about what, and what was agreed |
| `reporting` | who was informed or escalated to, on what trigger, and when |

All three are lists of plain sentences. They are optional, and work with none of them recorded is
still worth keeping.

## Result

`individual_contribution` and `team_result` are separate fields and nothing merges them.

This is the single most common way a career document becomes indefensible: the team's number
becomes the candidate's number, and the first interviewer who asks "what was your part?" finds
nothing behind it. Keeping the fields apart at capture time is what makes the honest answer
available later.

`metrics` holds numbers the user stated, and only those. Confirming an event whose title, summary,
or metrics contain a number that does not appear in the evidence is refused by the runtime.

## Organizational effect

There is no `standardized` / `documented` / `automated` / `recurrence_prevention` /
`handoff_improvement` set of flags. All five say the same thing — this changed how the work is
done afterwards — and five booleans invite five guesses. `improvements` is one list; the sentence
the user writes says which kind it was.

Japanese career documents weigh 改善・標準化・再発防止 heavily, so record them concretely:

```yaml
improvements:
  - "야간 배치 실패 알림을 임계값 기반으로 재설계"
  - "runbook에 복구 절차 추가, 운영팀 인수인계 항목으로 등록"
```

## Learning

`learning` holds knowledge, skill, or a change in how the user judges something. It is valid with
no measurable impact attached, and it is valid for work that failed. A lesson from a failure is
often the most reusable thing in the record.

## 報連相 and 根回し

Neither is a field, and neither is a score.

`報連相` describes a real expectation about reporting, information sharing, and consultation. What
is recordable is the observable action, which is what `reporting` holds: who was told, on what
trigger, how quickly, and what they were told. A number from 1 to 5 asserting how good someone is
at 報連相 is not an observation, cannot be evidenced, and would be exactly the uncalibrated score
the repository forbids.

`根回し` describes prior alignment before a formal decision. It is not a competency this product
models. What is recordable is the coordination itself, which is what `stakeholder_coordination`
holds:

```yaml
stakeholder_coordination:
  - "애플리케이션팀·분석팀·운영팀과 스키마 호환성과 배포 시점을 사전 조율"
  - "정식 승인 전에 제약 조건을 합의, 배포 계획 확정"
```

Both terms may be used when explaining to the user why the underlying behaviour is worth
recording. Neither becomes a field, a rating, or a claim about the person.

## Confidentiality

```yaml
confidentiality:
  contains_confidential: false
  external_use: allowed | blocked | unknown
```

Once `contains_confidential` is true, `external_use` must be stated. "Not reviewed yet" is
`unknown`, and `unknown` is not permission. This is the same rule as everywhere else in the
repository: absence of evidence is never an implicit pass.

Evidence lives in the event's own `evidence` list as pointers — `JIRA-123`, `PR-456`,
`performance-review-2026Q2`. A pointer identifies a source. It does not authorize reading it,
quoting it, or reproducing its contents.
