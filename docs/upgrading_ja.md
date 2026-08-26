# 互換性とアップグレード

🌐 [English](upgrading.md) · [한국어](upgrading_ko.md) · **日本語**

## リリースチャンネル

リリース準備中は、リポジトリのバージョンが stable marketplace チャンネルより先に進むことが
あります。stable チャンネルは実際に公開された最新の immutable `vX.Y.Z` タグだけを参照し、`main`
は追跡しません。

現在はソースメタデータが `2.16.0` である一方、stable marketplace ref はまだ `v2.1.1` です。この
ソースに対するタグをリリース workflow がまだ公開していないためで、marketplace から入れると今日は
`2.1.1` が入ります。次のタグが公開されれば差は閉じます。`uvx` と `npx` はこの ref ではなく公開済み
パッケージのバージョンを解決するので、どちらの場合も影響を受けません。

> 上の段落の二つの数値は、それぞれを所有するファイル（`pyproject.toml`、
> `.agents/plugins/marketplace.json`）から
> [`scripts/check_release_consistency.py`](../scripts/check_release_consistency.py) が読み取って
> 突き合わせます。この節はビルドを失敗させずに古くなることはできません。

## ローカル fallback

ファイルを直接確認したり実行したりする場合は、リポジトリを clone します。

```bash
git clone https://github.com/younnieCutler/japan-career-agent.git
```

## 2.0.x からの移行 — 旧名は `japan-recruit-ai-agent`

2.1.0 で名称を変更しました。GitHub が旧リポジトリ URL を redirect するため既存の clone と remote は
そのまま動きますが、marketplace の項目は名前で識別されるため追加し直す必要があります。

```bash
claude plugin marketplace remove japan-recruit-ai-agent
claude plugin marketplace add younnieCutler/japan-career-agent
claude plugin install japan-career-agent@japan-career-agent
```

Career Vault は何も変わりません。vault のパス、event ledger、生成済みの書類はいずれも名称変更の
影響を受けません。`JAPAN_RECRUIT_NO_UPDATE_CHECK=1` も引き続き update check を無効にするため、既存の
設定は新しい `JAPAN_CAREER_NO_UPDATE_CHECK` と併せてそのまま有効です。旧名で公開されたリリース
バンドルも [`scripts/verify_release.py`](../scripts/verify_release.py) で検証できます。
