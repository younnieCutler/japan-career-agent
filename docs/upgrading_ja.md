# 互換性とアップグレード

🌐 [English](upgrading.md) · [한국어](upgrading_ko.md) · **日本語**

## リリースチャンネル

リリース準備中は、リポジトリのバージョンが stable marketplace チャンネルより先に進むことが
あります。stable チャンネルは実際に公開された最新の immutable `vX.Y.Z` タグだけを参照し、`main`
は追跡しません。

現在はソースメタデータが `3.0.1` である一方、stable marketplace ref は `v2.1.1` です。この
ソースに対するタグをリリース workflow がまだ公開していないためで、marketplace から入れると今日は
`2.1.1` が入ります。次のタグが公開されれば差は閉じます。

まだ公開されていないソースバージョンに届く方法は clone だけです。

> 上の段落の二つの数値は、それぞれを所有するファイル（`pyproject.toml`、
> `.agents/plugins/marketplace.json`）から
> [`scripts/check_release_consistency.py`](../scripts/check_release_consistency.py) が読み取って
> 突き合わせます。この節はビルドを失敗させずに古くなることはできません。

## ローカル fallback

ファイルを直接確認したり実行したりする場合は、リポジトリを clone します。

```bash
git clone https://github.com/younnieCutler/japan-career-agent.git
```

ワークスペースの状態は `./data/`（`evidence.yml`、`pipeline.yml`、`applications.yml`、`rules.yml`）に、
生成された書類は `./career-docs/` に保存されます。`JAPAN_CAREER_NO_UPDATE_CHECK=1` を設定すると、
24 時間ごとのマニフェストバージョン確認を無効にできます。
