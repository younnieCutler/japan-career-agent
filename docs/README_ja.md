# ドキュメント

🌐 [English](README.md) · [한국어](README_ko.md) · **日本語**

[プロジェクト README](../README_ja.md) に載っていないものすべて。はじめてなら上から順に、後半は
リファレンスと記録です。

翻訳があるドキュメントには言語を併記しています。それ以外は英語の原文のみです。

## はじめに

| ドキュメント | 扱う内容 |
|---|---|
| [`cli-reference_ja.md`](cli-reference_ja.md) | ローカルのコマンド: setup、guided menu、過去の経験の復元、職務経歴書の生成と出力、GUI の起動 |
| [`upgrading_ja.md`](upgrading_ja.md) | marketplace が入れるバージョン、ローカル fallback、旧名 `japan-recruit-ai-agent` の 2.0.x からの移行 |

## 概念と契約

| ドキュメント | 扱う内容 |
|---|---|
| [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md)（英語） | host 無しで動くもの、host が改善するもの、host が必要なもの |
| [`FOUR_SKILL_EVOLUTION_DECISIONS.md`](FOUR_SKILL_EVOLUTION_DECISIONS.md)（英語） | 4-skill 分割の run identity と routing 判断ルール |
| [`HUMAN_OVERSIGHT.md`](HUMAN_OVERSIGHT.md)（英語） | Judgment と Approval を分離する理由、L0-L3 影響度モデル、Human-first reveal 契約 |
| [`_shared/decision_philosophy.md`](../_shared/decision_philosophy.md)（英語） | 根拠・`Unknown`・確認済み conflict がその挙動である理由 |
| [`_shared/schemas.yml`](../_shared/schemas.yml) | canonical な profile・pipeline・rules スキーマ |
| [`_shared/career_claims.yml`](../_shared/career_claims.yml) | 時点で変わる外部 claim と失効 |

## GUI

| ドキュメント | 扱う内容 |
|---|---|
| [`GUI_DESIGN_DECISIONS.md`](GUI_DESIGN_DECISIONS.md)（英語） | 設計の source of truth と UI 実装契約 |
| [`GUI_REQUIREMENT_TRACE.md`](GUI_REQUIREMENT_TRACE.md)（英語） | Capture → Review → Confirm の受け入れ記録 |
| [`GUI_MUTATION_COMPLETENESS.md`](GUI_MUTATION_COMPLETENESS.md)（英語） | どの GUI mutation が完了しているか、どのリビジョン基準か |

## アーキテクチャ

| ドキュメント | 扱う内容 |
|---|---|
| [`ARCHITECTURE_BOUNDARIES.md`](ARCHITECTURE_BOUNDARIES.md)（英語） | boundary チェックが強制する module-layer 規則と、コマンドの追加方法 |
| [`PRIVATE_CAREER_DATA_PRD.md`](PRIVATE_CAREER_DATA_PRD.md)（英語） | private career data store、personal timeline、fresh-context の設計 |

## メンテナ

| ドキュメント | 扱う内容 |
|---|---|
| [`MAINTAINER_RUNBOOK.md`](MAINTAINER_RUNBOOK.md)（英語） | 検証、リリース、レジストリ公開、marketplace ref の移動、失敗からの復旧 |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md)（英語） | リポジトリを変更する前に読むもの |
| [`CHANGELOG.md`](../CHANGELOG.md) | リリース履歴 |

標準のローカル検証コマンドは次です。

```bash
python scripts/run_all_checks.py
```

リリース guard は [`scripts/check_version_bump.py`](../scripts/check_version_bump.py) です。リリース
バージョンは `pyproject.toml` が所有し、plugin と npm の manifest には
[`scripts/sync_version.py`](../scripts/sync_version.py) が書き込みます。それ以外のファイルを手で
直す必要はありません。コードから導出できるドキュメントの事実は
[`scripts/check_docs_drift.py`](../scripts/check_docs_drift.py) が固定します。

## 記録と実験

すでに終わった作業の記録です。コードからは復元できない判断の理由を残すためのもので、現在の挙動を
説明するものではありません。

| ドキュメント | 扱う内容 |
|---|---|
| [`LLM_JUDGE_PILOT.md`](LLM_JUDGE_PILOT.md)（韓国語） | `job-seeker-agent` の LLM-as-judge パイロットと、採用しなかった理由 |
| [`LLM_JUDGE_V2_AUTORESEARCH.md`](LLM_JUDGE_V2_AUTORESEARCH.md)（韓国語） | v2 固定コーパス judge 実験と暫定的な結果 |
| [`ROUTING_AUTORESEARCH.md`](ROUTING_AUTORESEARCH.md)（英語） | phase 0–2 routing-autoresearch の実装記録 |
| [`routing-autoresearch-program.md`](routing-autoresearch-program.md)（英語） | リサーチエージェントに与えた運用指示 |
| [`routing-autoresearch-results.tsv`](routing-autoresearch-results.tsv) | append-only の実験ログ |
| [`UX_REGRESSION_EVAL.md`](UX_REGRESSION_EVAL.md)（英語） | 合成会話出力に対する P2 UX 評価契約 |