# Japan career market flow

Use stages as a planning map, not as a prediction model. Company-specific progress lives in
`data/pipeline.yml`. No universal duration or pass rate is asserted here; time-sensitive external
claims belong in `_shared/career_claims.yml` and must be reverified.

| Stage | Evidence-based planning use | Skill |
|---|---|---|
| 0. 自己分析 | record confirmed values, preferences, and unknowns | `jiko-bunseki` |
| 1. 書類準備 | map 履歴書 and 職務経歴書 to dated posting evidence | `job-seeker-agent` |
| 2. 情報収集・企業研究 | keep company facts separate from hypotheses | `kigyou-bunseki`, `matching-simulator` |
| 3. 応募・書類選考 | record each application and actual response | `tenshoku-strategy` tracking |
| 4. 面接 | follow confirmed invitation and recruiter details | `job-seeker-agent`, `tenshoku-strategy` |
| 5. 内定・オファー | verify written conditions, deadline, negotiation channel, and start date | `tenshoku-strategy`, `company-battlecard` |
| 6. 退職・引き継ぎ | check applicable law, contract, work rules, and personal facts | `tenshoku-strategy` |
| 7. 入社 | verify authorization, tax, insurance, reference-check, and probation documents | `tenshoku-strategy` |

Stages can overlap. Typical skill chains are:

```
direction → documents → company research → evidence diagnosis → execution → offer comparison
resume-ready → company research → evidence diagnosis → execution → offer comparison
hiring-side JD → evidence diagnosis
```
