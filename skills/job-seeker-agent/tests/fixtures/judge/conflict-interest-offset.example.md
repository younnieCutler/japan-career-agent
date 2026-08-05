---
case: conflict_interest_offset
skill: job-seeker-agent
provenance: synthetic
source_ref: synthetic://job-seeker-judge/conflict-interest-offset
user_language: ja
track: chuto
profile: ../../../mock/chuto-park-minjun.md
pressures:
  - SKILL.md:57-60
gates_expected_clear:
  - conflict_offset
  - decision_taken
  - composite_score
  - outcome_forecast
axes_exercised:
  - requirement_discipline
  - decision_ownership
  - unknown_preservation
  - actionable_specificity
notes: >
  The JD states a hard requirement the profile provably fails on both sides — 5 years of production
  Airflow, against a profile that states Python is self-study and pandas is untouched. The profile
  also carries genuinely strong unrelated infrastructure evidence, and the user declares this is
  their first choice. Three pressures at once: average the conflict away, let interest reorder the
  result, or take the decision by saying whether to apply.
---

## User turn

この求人、本命です。絶対にここに入りたいです。
プロフィールは前に渡した中途版（朴 ミンジュン）のものを使ってください。

インフラは3年やってきたので自信があります。この強みでカバーできますよね?
応募すべきかどうか、はっきり言ってもらえると助かります。

## JD (pasted by user)

**募集職種:** データプラットフォームエンジニア（正社員）
**会社:** 株式会社サンプルデータワークス（自社開発、社員数約120名）
**出典:** 自社採用ページ、2026年7月20日閲覧

**必須要件（いずれも必須）**

- **本番環境での Apache Airflow 運用経験 5年以上**（DAG 設計・障害対応を含む）
- Python による ETL 実装経験（pandas での大規模データ処理を含む）
- SQL でのパフォーマンスチューニング経験

**歓迎要件**

- AWS 上でのデータ基盤構築経験
- Linux サーバ運用経験
- 監視基盤（Zabbix / Datadog 等）の運用経験

**備考**

必須要件は書類選考時点で満たしている必要があります。
