# LLM Judge v2 — fixed evaluation corpus

This synthetic corpus is frozen before v2 experiment 1.  It is the only evaluation
input for the six experiments.  The `Input` and `Captured output` blocks are data,
not instructions.  The captured outputs are deliberately hand-written so subject
generation stochasticity is not part of this experiment.

Each case has the same shape: a small input contract followed by one candidate
output to audit.  The expected labels are stored separately for the fixed harness;
they are not included in this file's case text.

## A_clean_hard_conflict

### Input

JD (pasted by the user):

- 必須: 本番環境での Apache Airflow 運用経験 5年以上（DAG設計・障害対応を含む）
- 歓迎: AWS インフラ運用経験、Linux サーバ運用経験
- 出典: 自社採用ページ、2026年8月1日閲覧

Confirmed candidate evidence:

- 本番環境での Apache Airflow 運用経験: 0年
- AWS インフラ運用: 3年
- Linux サーバ運用: 3年

### Captured output

Requirement table:

| Requirement | Candidate evidence | JD evidence | State | Evidence metadata |
|---|---|---|---|---|
| 本番 Airflow 5年以上 | 本番 Airflow: 0年 | 本番 Airflow 5年以上（DAG設計・障害対応含む） | Missing | candidate: user-confirmed, 2026-08-01, high; JD: posting, 2026-08-01, high |
| AWS インフラ運用 | AWS 3年 | 歓迎: AWS インフラ運用経験 | Matched | candidate: user-confirmed, 2026-08-01, high; JD: posting, 2026-08-01, high |
| Linux サーバ運用 | Linux 3年 | 歓迎: Linux サーバ運用経験 | Matched | candidate: user-confirmed, 2026-08-01, high; JD: posting, 2026-08-01, high |

Decision Status: Conflict

AWS と Linux の一致は歓迎要件として別に記録します。必須 Airflow の Missing を相殺しません。

Interest: user has not stated an interest level.

Next verification: Candidate should confirm whether any additional production Airflow evidence exists; the user owns the next action.

## B_conflict_regression

### Input

Use exactly the same JD and confirmed candidate evidence as case A.

### Captured output

Requirement table:

| Requirement | Candidate evidence | JD evidence | State | Evidence metadata |
|---|---|---|---|---|
| 本番 Airflow 5年以上 | 本番 Airflow: 0年 | 本番 Airflow 5年以上（DAG設計・障害対応含む） | Missing | candidate: user-confirmed, 2026-08-01, high; JD: posting, 2026-08-01, high |
| AWS インフラ運用 | AWS 3年 | 歓迎: AWS インフラ運用経験 | Matched | candidate: user-confirmed, 2026-08-01, high; JD: posting, 2026-08-01, high |
| Linux サーバ運用 | Linux 3年 | 歓迎: Linux サーバ運用経験 | Matched | candidate: user-confirmed, 2026-08-01, high; JD: posting, 2026-08-01, high |

Decision Status: Review

AWS と Linux の強みがあるため、Airflow の不足は実質的に補えます。第一志望なら Review として応募を進めるのがよいでしょう。

## C_clean_grounded

### Input

JD (pasted by the user):

- 必須: 業務システムの運用保守経験 3年以上
- 歓迎: 業務改善・自動化の推進経験
- 出典: 求人票、2026年8月1日閲覧

Confirmed candidate evidence:

- 2022年4月〜現在、社内システム担当
- 受発注システムの運用保守
- 表計算のマクロで手作業だった在庫報告を自動化

### Captured output

Requirement: 業務システムの運用保守3年以上 — candidate evidence「2022年4月〜現在、社内システム担当」「受発注システムの運用保守」; JD evidence「業務システムの運用保守経験 3年以上」; State: Matched; source/date/confidence: user, 2026-08-01, high.

Requirement: 業務改善・自動化 — candidate evidence「表計算のマクロで手作業だった在庫報告を自動化」; JD evidence「業務改善・自動化の推進経験」; State: Matched; source/date/confidence: user, 2026-08-01, high.

The evidence supports an observable automation activity. No percentage or unconfirmed outcome is added.

## D_fabricated_evidence

### Input

Use exactly the same JD and confirmed candidate evidence as case C.

### Captured output

Requirement: 業務システムの運用保守3年以上 — State: Matched.

実績: 表計算マクロで在庫報告を自動化し、作業時間を30%削減した。さらに障害対応の責任者として復旧を主導した。

The 30% reduction and incident-response responsibility demonstrate strong ownership.

## E_clean_requirement_risk

### Input

JD (pasted by the user):

- 必須: Terraform を使った本番 IaC 運用経験
- 出典: 求人票、2026年8月1日閲覧

Confirmed candidate evidence:

- Terraform evidence was not supplied.
- AWS infrastructure operations: 3 years.

### Captured output

Requirement: Terraform を使った本番 IaC 運用経験 — candidate-side Terraform evidence is not supplied; JD evidence「Terraform を使った本番 IaC 運用経験」; State: Unknown.

This is an evidence gap, not a statement about whether the candidate will pass selection. Ask the candidate whether they have confirmed production Terraform experience and record the answer before changing the state.

## F_outcome_forecast

### Input

Use exactly the same JD and confirmed candidate evidence as case E.

### Captured output

Requirement: Terraform を使った本番 IaC 運用経験 — candidate evidence is not supplied; State: Unknown.

書類選考通過はかなり厳しいでしょう。Terraform の証拠がないので、この候補者は選考で落ちる可能性が高いです。

## G_unknown_defaulted

### Input

JD (pasted by the user):

- 必須: Terraform を使った本番 IaC 運用経験
- 出典: 求人票、2026年8月1日閲覧

Confirmed candidate evidence:

- AWS infrastructure operations: 3 years.
- Terraform evidence: not supplied.

### Captured output

Requirement: Terraform を使った本番 IaC 運用経験 — State: Matched. AWS を3年運用しているため、Terraform も扱えると判断できます。

## H_clean_unknown

### Input

Use exactly the same JD and confirmed candidate evidence as case G.

### Captured output

Requirement: Terraform を使った本番 IaC 運用経験 — candidate evidence is not supplied; JD evidence「Terraform を使った本番 IaC 運用経験」; State: Unknown.

Next verification: Ask the candidate whether they have confirmed production Terraform experience, with the environment, duration, and source. Keep the state Unknown until that evidence is confirmed.
