# CLI リファレンス

🌐 [English](cli-reference.md) · [한국어](cli-reference_ko.md) · **日本語**

ローカルruntimeでは、個人のCareer Vaultをcanonical stateとして管理し、会社ごとのworkflow状態を
`./data/pipeline.yml` にprojectionします。

このページの内容はすべて、plugin と `npx`/`uvx` の入口が実行するのと同じプログラムです。host は
必要ありません。

## setup と guided menu

明示的なlocal setupとguided menuを使う場合:

```bash
VAULT=/path/to/career-agent-vault
python skills/career-agent/career_agent.py setup --vault "$VAULT" --track chuto --target-role "Platform Engineer"
python skills/career-agent/career_agent.py guided --vault "$VAULT" --format human
```

`guided` は setup 状態、pending proposal、`Unknown` と `Conflict` の数、workspace metadata、実行
できる次の操作を表示します。スクリプトでは `--choice <id-or-number>` を使えます。書き込みを行う
操作には `--confirm` が必要です。guided mode がproposalを自動承認したり、private noteの本文を
読んだりすることはありません。

## 過去の経験を復元し、応募先ごとに書類を作る

Vault が空の場合は `readiness` がそれを明示し、そこから何も推測しません。

```bash
python skills/career-agent/career_agent.py readiness --vault "$VAULT"      # bootstrap_suggested
python skills/career-agent/career_agent.py add-context "○○大学" --kind university --vault "$VAULT"
python skills/career-agent/career_agent.py experiences --vault "$VAULT"    # Context → Experience → Evidence
```

Context は経験が起きた場所であり、勤務先とは限りません。`--kind` は会社・大学・インターン・
アルバイト先・サークル・ボランティア・個人活動・オープンソースを含みます。Experience も
プロジェクトとは限りません。仕事以外の経験は `run --mode chat --non-work` で記録し、学業が
職務経歴として扱われないようにします。

根拠がたまったら、応募先ごとに書類を組み立て、出力前に検査します。

```bash
python skills/career-agent/career_agent.py document-model <company-slug> --vault "$VAULT" > model.json
python skills/career-agent/career_agent.py document-check --model model.json --draft draft.json
python skills/career-agent/career_agent.py document-render --model model.json --draft draft.json \
    --template standard-chuto --out ./career-docs
```

検査は deterministic です。記録にない数値、既存の数値の丸め、`支援` を `主導` と書く表現、使って
いない技術として提示された求人キーワード、チームの成果を個人の成果として書いた文、
`external_label` があるのに露出した社内プロジェクト名を拒否します。通過は
**既知の protected claim 違反がない** という意味であり、日本語が事実と一致すると証明したわけでは
ありません。送る前にご自身で読む理由がここにあります。

出力は A4 の print CSS を含む HTML で、PDF はブラウザの印刷から作成します。書類が上書きされる
ことはありません。ファイル名に根拠・求人・template・文面の digest が含まれるため、変更後に
再生成すると新しいファイルが作られ、既存のものはそのまま残ります。`./career-docs/` は Git の
追跡対象外です。

## ローカル GUI を起動する

GUI も同じ runtime のコマンドの一つです。loopback の空きポートに bind し、使い捨ての token を含む
URL を出力します。`--no-browser` を付けるとブラウザを開かずにその URL だけを出力します。

```bash
python skills/career-agent/career_agent.py ui --vault "$VAULT" --port 0
python skills/career-agent/career_agent.py sessions --vault "$VAULT" --format human
```

サーバーを起動すること自体は何も書き込みません。GUI が保存する draft・case・artifact metadata は、
承認するまで canonical ledger には入りません。`sessions` は同じ resumable session の保存先を
ターミナルから読みます。どちらの entry point もその保存先を所有しません。

設計上の判断と UI 実装契約は [`GUI_DESIGN_DECISIONS.md`](GUI_DESIGN_DECISIONS.md) にあります。

## Skill の実行記録

Skill を選ぶことと実際に実行することは別です。`run --mode chat` と `skills` はこの要求がどの
Skill を使うかを示すだけで、実際に実行したという記録は `skill-open` と `skill-report` で host が
残します。host が必要な Skill なのに使える host がないときは、実行したかのように答える代わりに
`unsupported` を返します。

## 完全な契約

このページはよく使うコマンドを扱います。すべての subcommand・フラグ・exit code・出力形式を含む
完全な CLI 契約は [`skills/career-agent/SKILL.md`](../skills/career-agent/SKILL.md) にあります。
