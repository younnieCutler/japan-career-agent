# ドキュメント

🌐 [English](README.md) · [한국어](README_ko.md) · **日本語**

[プロジェクト README](../README_ja.md) に載っていないものすべて。はじめてなら上から順に、後半は
リファレンスと記録です。

翻訳があるドキュメントには言語を併記しています。それ以外は英語の原文のみです。

## はじめに

| ドキュメント | 扱う内容 |
|---|---|
| [`OUTCOMES.md`](OUTCOMES.md)（英語） | 匿名化された実際の内定獲得事例と活用スキルチェーン |
| [`upgrading_ja.md`](upgrading_ja.md) | marketplace が入れるバージョン、ローカル fallback、ワークスペース構成 |

## 概念と契約

| ドキュメント | 扱う内容 |
|---|---|
| [`_shared/decision_philosophy.md`](../_shared/decision_philosophy.md)（英語） | 根拠・`Unknown`・確認済み conflict がその挙動である理由 |
| [`_shared/schemas.yml`](../_shared/schemas.yml) | canonical な profile・pipeline・rules スキーマ |
| [`_shared/career_claims.yml`](../_shared/career_claims.yml) | 時点で変わる外部 claim と失効 |

## アーキテクチャ

| ドキュメント | 扱う内容 |
|---|---|
| [`ARCHITECTURE_BOUNDARIES.md`](ARCHITECTURE_BOUNDARIES.md)（英語） | スキル、共有モジュール、決定的なスクリプトの責務境界 |
| [`AGENT_OBSERVATION_PACK.md`](AGENT_OBSERVATION_PACK.md)（英語） | コーディングエージェントが長いローカルコマンド出力を圧縮し、正確な根拠を保持する方法 |

## メンテナ

- [キャリア知識のメンテナンス](CAREER_KNOWLEDGE.md)（英語）: 出典レビュー、トピック検索、候補の昇格。
- [日本キャリア市場リサーチ](research/japan-career-market-2026.md)（英語）: 検証済み出典と残課題。

| ドキュメント | 扱う内容 |
|---|---|
| [`MAINTAINER_RUNBOOK.md`](MAINTAINER_RUNBOOK.md)（英語） | 検証、リリース、marketplace ref の移動、失敗からの復旧 |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md)（英語） | リポジトリを変更する前に読むもの |
| [`CHANGELOG.md`](../CHANGELOG.md) | リリース履歴 |

標準のローカル検証コマンドは次です。

```bash
python scripts/run_all_checks.py
```

リリース guard は [`scripts/check_version_bump.py`](../scripts/check_version_bump.py) です。リリース
バージョンは `pyproject.toml` が所有し、plugin manifest と SBOM には
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
