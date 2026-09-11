# Evidence-safe experience elicitation

Use this reference only when an experience is hard to unpack or the user explicitly wants a structured framework. It is a question-generation lens inside the existing `Context -> Experience -> Evidence` workflow, never a replacement data model.

## 3C4P as an internal lens

3C4P is not treated as a Japanese hiring standard and is not presented as superior to STAR. It is useful only for generating concrete questions:

- Customer: who received the work or was affected?
- Company: what team, business, operational, or organizational constraint existed?
- Competitor / alternative: what other approach, baseline, or alternative was relevant? If none is known, leave it `Unknown`.
- Product: what concrete output, service, change, or responsibility was involved?
- Price: what cost, effort, risk, resource, or trade-off mattered? Do not force a money figure.
- Place: where in the process or workflow did the issue occur?
- Promotion: how was the change communicated, adopted, coordinated, or rolled out?

Map the useful answers back to canonical evidence fields such as problem, constraint, decision, individual contribution, team result, stakeholder coordination, artifact, and metric. Do not persist the 3C4P labels themselves unless the user explicitly wants them in a note.

## Evidence-safe result branch

Ask whether the result was actually measured.

If measured:
- record only the original confirmed number and its source;
- preserve baseline, period, denominator, and whether the figure is individual or team-level when known.

If not measured:
- describe the observable change, scope, frequency, responsibility, process, or artifact;
- leave the number `Unknown`;
- never create an estimate, range, rounded KPI, or plausible percentage.

`改善したが数値は測っていない` is complete evidence. It is preferable to an approximate number.

## Minimal question sequence

Ask at most three questions at a time and stop when the relevant canonical fields are filled:

1. What situation or constraint made the work necessary?
2. What did you personally decide or do, separate from the team?
3. What changed, and how do you know? Was it measured or only observed?

Optional follow-ups should target only missing high-value evidence: comparison/alternative, stakeholder adoption, trade-off, artifact, or learning.

## Prohibited transformations

- team result -> individual result
- role title -> responsibility
- qualitative improvement -> invented percentage
- user memory uncertainty -> polished certainty
- 3C4P completion -> proof that the story is strong

The framework improves questions. It never increases the strength of the evidence by itself.
