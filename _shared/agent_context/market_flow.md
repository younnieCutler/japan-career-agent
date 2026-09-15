# Japan career market flow

Use stages as a planning map, not as a prediction model. The canonical chuto lifecycle labels are
also defined in `skills/career-agent/references/japan-career-flow.toml` and are regression-checked
against the runtime vocabulary. Company-specific progress lives in `data/pipeline.yml`.
No universal duration or pass rate is asserted here; time-sensitive external claims belong in
`_shared/career_claims.yml` and must be reverified.

`career-maintenance` is continuous and sits outside this linear planning map: recording work evidence
does not imply job-search intent.

| Pipeline stage | Canonical chuto stage | Evidence-based planning use | Primary Skill / handoff |
|---|---|---|---|
| 0 | 自己分析・転職軸 | recover/confirm career evidence, values, target direction, and unknowns | `career-tanaoroshi`, `jiko-bunseki`, `job-seeker-agent` target-role exploration |
| 1 | 応募基盤・職務経歴書 | prepare a reusable candidate profile and base documents | `job-seeker-agent` |
| 2 | 求人探索・候補整理 | discover current public opportunities and let the user choose which enter review | deterministic `career-agent discover` |
| 2 | 企業研究・JD分析 | keep company/JD facts separate from hypotheses and compare requirements with confirmed evidence | `kigyou-bunseki`, `matching-simulator` |
| 3 | 応募・書類選考 | tailor the target-specific package; once an application starts, track it through closure | `career-document`; `tenshoku-strategy` tracking is cross-cutting |
| 4 | 面接・選考 | prepare factual answers, practise against the actual invitation when known, and record outcomes/feedback | `job-seeker-agent`, `mock-interviewer`, `tenshoku-strategy` tracking |
| 5 | 内定・条件交渉 | verify written conditions, deadline, negotiation channel, role scope, and start date | `tenshoku-strategy`, `company-battlecard` |
| 6 | 退職・引き継ぎ | check applicable law, contract/work rules, handover, and transition administration | `tenshoku-strategy` |
| 7 | 入社準備・オンボーディング | verify joining documents, applicable authorization/tax/insurance handoffs, and probation/first-90-day facts | `tenshoku-strategy` |

The application-learning loop is not an end stage. It starts when an application is opened and may
run after every outcome through offer closure:

```
application opened
  → actual stage/outcome recorded
  → direct feedback / candidate observation / pre-application gaps kept separate
  → user-confirmed learning pattern, or Unknown
  → next opportunity/application
```

Stages can overlap. Typical skill chains are:

```
direction → base documents → opportunity discovery → company/JD analysis → target document → selection loop → offer → exit → onboarding
resume-ready → opportunity discovery → company/JD analysis → target document → selection loop → offer comparison
specific JD → company/JD analysis → matching diagnosis → target document
interview invitation → factual answer preparation → mock interview → actual outcome → learning loop
```
