# 面接ラウンド別・相手別 対策 (Audience-Segmented Interview Prep)

Prep that segments each interview round by **who is in the room** — because the same answer that
lands with a 現場マネージャー can sink you with 人事, and vice versa. Research the process, classify each
round to an audience, then prepare an audience-specific answer pack.

> Adapted from career-ops (MIT, github/santifer/career-ops): `modes/interview-prep.md`,
> `modes/heuristics/recruiter-side.md`. Japan-localized: audiences, research sources, evaluation axes.
> This is interview **content/answer strategy**. Interview **manner** (入室/服装/退室) lives in
> `tenshoku-strategy/references/mensetsu-manner.md`.

**Anti-fabrication gate (suite rule):** Never invent interview questions and attribute them to a source.
Tag every question: `[sourced: OpenWork/転職会議/口コミ + date]` for crowd-sourced, `[inferred from JD]` for
questions derived from the posting. If round structure is unknown, write "不明 — データ不足", do not guess.
Answer drafts must trace to the candidate's real `職務経歴` (reuse `shokumukeireki-saigensei.md` 再現性 evidence).

---

## Step 1 — Research the process (per audience)

Run searches and extract structured facts with citations. Group by the audience each fact informs.
Japan sources replace US ones (no Glassdoor/Levels/Blind — use the list below).

| Audience | JP research sources | What to extract |
|---|---|---|
| **人事スクリーン (recruiter)** | OpenWork 選考体験記, 転職会議, 企業採用ページ, ビズリーチ | 選考フロー・所要日数, 年収レンジ, 勤務地/リモート/ビザ方針, よく聞かれる動機系質問 |
| **現場マネージャー (hiring manager)** | 企業技術ブログ, プレスリリース(直近12ヶ月), 事業/採用ページ | チームの直近の取組み・課題, 募集背景, 求める役割スコープ |
| **技術/ケース面接 (peer/tech)** | OpenWork/転職会議 面接体験記, Geekly·GeeklyReview(IT/Web/ゲーム), Findy(エンジニア) | 実際の出題, 難易度, ラウンド数, 技術スタック, ケース設問の型 |
| **最終/役員 (exec)** | 統合報告書/IR, 社長・役員インタビュー, MVV(ミッション・バリュー) | バリュー(評価軸), 経営の方向性, カルチャーキーワード |

If the company is small/obscure and yields little, broaden to同業・同規模 and mark intel as sparse. Always
run the recruiter-screen sources — 年収/選考フロー data exists for almost any company.

> IT/Web/ゲーム職の場合、Geekly Media(`geekly.co.jp/column`)と GeeklyReview(`geeklyreview.com`)が
> 職種解説・選考情報の補助ソースになる。記事本文は引用時に出典明記、未確認の主張は作らない。

---

## Step 2 — Audience Map (classify every round)

Classify each round into exactly ONE audience. The audience drives Steps 3–4.

| Audience | Typical Japan round | Primary evaluation |
|---|---|---|
| `casual` | **カジュアル面談** (選考前, 30–45min, 現場 or 人事) | 相互理解・志望度の醸成。**選考に影響しうる**ことを忘れない |
| `jinji-screen` | **一次面接** (人事/採用担当, 30–45min) | 適合ゲート: 転職理由, 志望動機の芯, 年収, 勤務地/ビザ, 時期 |
| `genba-manager` | **二次面接** (現場マネージャー/部長, 45min) | なぜこの役割, スコープ適合, 即戦力性, 再現性 |
| `peer-tech` | **技術面接 / ケース面接** (現場メンバー) | 実スタックでの深さ・協働, ケースの論理整合 |
| `exec-final` | **最終面接** (役員/社長) | バリューFIT, キャラクター, 意思決定の一貫性, キャリアビジョン, オーナーシップ |

**Inference rule:** if `面接官の役職` is unknown, infer cautiously from round position/duration and tag
`[inferred]`. Round 1 short → almost always `jinji-screen`. 二次 → don't default; `peer-tech` if described
as 技術/ケース, `genba-manager` if a現場/マネジメント conversation. 最終 → `exec-final`.

> 最終面接で約5割が不合格という公開データもある(sincereed `UdjQxAtAUUI`)。最終は能力試験ではなく
> バリュー/キャラクター/意思決定一貫性/キャリアビジョン/オーナーシップの確認。Step 4 の `exec-final` で重点対策。

---

## Step 3 — Round-by-round breakdown

For each round found in Step 1:

```markdown
### {N}次面接: {型} — audience: `{audience}`
- 所要: {X}分 / 面接官: {人事 / 現場 / 役員 — 既知なら}
- 評価対象: {具体スキル・資質}
- 報告された質問:
  - {質問} — [sourced: 転職会議 (URL/日付)]
  - {質問} — [inferred from JD]
- 対策: {1–2の具体アクション。詳細は Step 4 の相手別パック}
```

---

## Step 4 — Likely questions, per audience (with answer frames)

Group questions by **who asks**, not by type. Draft answers from the candidate's real materials. Use
**結論ファースト** framing: ① 結論/成果 → ② なぜ重要(事業/チーム) → ③ 制約/工夫 → ④ 具体の自分の動き.

### `casual` — カジュアル面談
- 目的は相互理解だが**評価は始まっている**。逆質問の質が志望度シグナル(下記 §逆質問)。
- 志望動機は**仮**でよいが、`shibo-doki.md` の ① 会社理解 を1つは具体で持参。
- 年収・条件の重い交渉は持ち込まない(`naitei-taiou.md`/オファー面談へ)。

### `jinji-screen` — 一次(人事)
適合ゲート。ここでの取りこぼし(曖昧な動機・年収・勤務条件)は技術シグナルに届く前に終わる。最低限:
- **転職理由 → 志望動機の接続** — `tenshoku-strategy/taishoku-riyu-reframing.md` の前向き変換を、
  `shibo-doki.md` の **4-WHY 一貫性チェーン**(なぜ転職/なぜこの会社/なぜこの職種/なぜ今)で矛盾なく。
- **希望年収** — Step 1 のレンジに基づく具体。レバレッジが薄ければ「市場・等級に合わせたい、レンジを教えてほしい」と委ねる(`nenshu-koushou.md`)。
- **勤務地/リモート/ビザ/時期** — 数字で。`platforms.md` の JLPT/ビザ方針と整合。

### `genba-manager` — 二次(現場)
動機 + スコープ適合。ロジ面は人事が通した前提。所有して働けるかを見る:
- **「なぜこの役割・なぜ今」** — 直近1–2の経歴 + `shibo-doki.md` 転職軸を、Step 1 のチーム課題に接続。
- **「入社後の最初の90日」** — JD スコープ + チームの直近の取組みから。
- **再現性の提示** — `shokumukeireki-saigensei.md` の 役割/工夫/成果/再現性。成果は捏造せず実績から。

### `peer-tech` — 技術 / ケース面接
深さと協働。スタック/ドメインの実地。
- **技術質問**(設計/コーディング/ドメイン): 各々 出題・出典・この候補者の強い回答角度(CV proof 参照)。
- **ケース面接**(コンサル系): 論理整合・客観性・構造化。結論→根拠→打ち手の型。前提確認を省かない。
- **逆質問**: オンコール, コードレビュー文化, デプロイ頻度, 入社して驚いたこと。

### `exec-final` — 最終(役員)
バリューFIT中心。落ちる典型: バリュー不一致 / キャラクターが見えない / 人生の意思決定が曖昧 /
キャリアビジョン不在 / オーナーシップ不足。対策:
- 4-WHY を**自分の言葉の物語**として一貫提示(`shibo-doki.md`)。
- キャリアビジョン = 貢献フェーズ + 自己実現フェーズの両方(sincereed `lck8gribTVc`)。
- 企業のバリュー用語を使う(MVV から)。一次〜最終で**年収・時期・志望度を矛盾させない**(面接官は情報共有する)。

---

## Step 5 — 想定質問 × 自分の実績 マッピング

Map per-audience questions to the candidate's STAR/再現性 stories. Same story can map differently per
audience — keep the table segmented to avoid cross-audience drift.

| # | Audience | 想定質問/論点 | 使う実績(再現性) | 適合 | ギャップ? |
|---|---|---|---|---|---|
| 1 | jinji-screen | 転職理由 | … | 強/部分/なし | |
| 2 | genba-manager | 90日プラン | … | … | |
| 3 | peer-tech | {技術設問} | … | … | |

- **ギャップがある質問**は「{論点}の実績が弱い → `職務経歴` の{経験}を STAR で言語化できないか」を提案。
  実体験がなければ作らない(別の角度に切替)。

---

## Step 6 — 同じ proof を使い回さない (mixed/連続面接)

- 同一 proof point を複数ラウンドで**同じ言い回し**で出すと「台本」に見える。角度を変える:
  人事には成果の見出し、現場には事業インパクト、技術には実装の判断。
- 連続面接(最終ループ)では、最も深さを問う枠(通常 peer-tech)に最良の素材を温存。

---

## Output

Save to `career-docs/mensetsu-[company]-[role]-[YYYYMMDD].md`:

```markdown
# 面接インテリジェンス: {会社} — {役割}
**選考フロー:** {N次, ~X日}
**Audiences:** {casual / jinji-screen / genba-manager / peer-tech / exec-final}
**求人の真正性:** {kigyou-bunseki の `求人の真正性` tier, なければ "不明"}
**Sources:** {N件 OpenWork, N件 転職会議, その他}
```

## Rules
- 質問を発明して出典を付けない。推測は `[inferred from JD]`。統計/口コミ数値を捏造しない。
- すべての質問・統計・主張に出典 or `[inferred]` タグ。
- 応答言語は SKILL.md の Language Auto-Detection に従う。ドメイン用語は日本語原文。
- 励まし禁止。これは作業用の対策資料であって応援メッセージではない。
