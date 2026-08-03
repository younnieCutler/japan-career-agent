# 選考トラッキング — workflow observations

`data/pipeline.yml` is the workspace source of truth. Use `scripts/pipeline.py` for writes and keep
closed entries for historical review. Do not edit action-item `checked` values from a skill.

## Fields

Record the company slug, role, channel, stage, status, deadline, source, and user-owned next action.
When a result is available, record:

- `reached_stage`: the furthest stage actually reached, or `Unknown`/null;
- `feedback_obtained`: whether a direct reason was received;
- `agent_feedback`: recruiter text verbatim when the route supplies it;
- `root_cause`: only when the user can support it with feedback or a confirmed observation;
- `demo_slot`: `yes`, `company_test`, `no`, or `unknown`;
- `gate_override`: whether the user chose to continue after a warning.

Do not infer a cause from silence, a template rejection, or a company stereotype. A direct route's
absence of feedback is `Observed: no feedback`, not a negative signal.

## Deterministic workflow analysis

Run `python scripts/calibrate.py` before interpretation. It can report:

1. route → feedback capture observations;
2. repeated feedback causes, with source slugs;
3. user overrides and the stage they reached;
4. preparation actions recorded before a stage;
5. the separate `legacy_v1` history viewer only when explicitly invoked with
   `scripts/legacy_calibrate.py --legacy-experimental`.

The v3 `Decision Status` is not measured against a hiring outcome. `Proceed`, `Review`, and
`Conflict` remain diagnostic states. No workflow table turns them into a rate, rank, or grade.

Below the sample floor, print `Insufficient Data`. A cause supported by one company remains an
observation; promotion requires two distinct entries and explicit user approval through the existing
rules path.

## Output template

```markdown
# 選考パターン分析 — [date]

## Observed funnel
| Stage | Count | Evidence scope |
|---|---:|---|
| 応募 | [n] | closed/open entries with dates |

## Route and feedback
| Route | Entries | Feedback obtained | Missing |
|---|---:|---:|---:|

## Repeated feedback observations
| Cause | Supporting companies | Verbatim evidence |
|---|---|---|

## Overrides and preparation
[what the user chose and what actions were completed before the stage]

## Unknowns
[fields or company responses still needed]
```

Always cite the source and date. Do not recommend stopping an application; explain the confirmed
risk and let the user choose the next action.
