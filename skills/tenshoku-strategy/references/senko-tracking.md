# 選考トラッキング + パターン分析 (Application Tracker + Funnel Analysis)

> Track multiple applications, and once 5+ accumulate, analyze the **selection funnel and rejection patterns**
> to show, with data, "what passes and what wastes time." A **longitudinal learning** layer, not a single-shot
> diagnosis.
>
> Adapted from career-ops (MIT, github/santifer/career-ops): `modes/tracker.md`, `modes/patterns.md`,
> `templates/states.yml`. Localized to Japanese job-change process / blockers. **Prompt-driven aggregation, no
> script** (LLM approximation).

**Core Principle:** Tracking is a record of facts; analysis is evidence-based. No praise or encouragement. Do
not invent results that are not there.

---

## 1. Storage: `data/pipeline.yml` (source of truth) + `career-docs/applications.md` (rendered view)

The tracker's source of truth is **`data/pipeline.yml`** — the suite-wide per-company state hub
(PIPELINE schema in `_shared/schemas.yml`). One entry per company, keyed by `slug` (same slug as
`data/company_profiles/{slug}.yml`). Other skills also write it: kigyou-bunseki (entry +
`kyujin_legitimacy`), matching-simulator (`match_score`), company-battlecard (history events).
This STEP owns stage transitions, `history` events, `next_action`, `deadline`, `closed`,
`closed_reason`, and `agent_feedback` (verbatim お見送り reason on agent/scout channels — see §2).

Upsert rules: read the whole file → modify → rewrite. Match by `slug`. Never delete an entry —
set `closed: true` + `closed_reason` instead (closed entries feed the funnel analysis below).
Both files follow the Output Contract (Rule C): CWD-relative, create folders if missing, print the
absolute path after every write and confirm the file exists.

`career-docs/applications.md` is a **rendered view** — regenerate the whole table from pipeline.yml
after every tracking session (do not hand-edit rows; the yml is authoritative):

```markdown
# 応募トラッカー (rendered from data/pipeline.yml — do not edit by hand)

| # | 日付 | 企業 | 職種 | プラットフォーム | スコア | ステータス | 求人真正性 | メモ |
|---|------|------|------|----------------|--------|-----------|-----------|------|
| 1 | 2026-06-26 | A社 | DE | doda | 78 | 一次 | 信頼度高 | 中途比率45% |
```

- **日付:** first `history` event date. **スコア:** `match_score` (blank if null).
- **ステータス:** from the state machine below. **求人真正性:** `kyujin_legitimacy` tier.

---

## 2. ステータス state machine (fixed 8+ states)

career-ops's 8 states mapped to the Japanese job-change flow. Use this order/naming as fixed.
Each state maps onto the pipeline entry's `stage` (CLAUDE.md Market Stage Map, 0–7) and `closed` flag —
record the state name itself as a `history` event and in `status`.

| ステータス | Meaning | pipeline mapping | outcome class |
|-----------|---------|-----------------|---------------|
| `評価済` | only matching/battlecard done (not applied) | stage 2, closed: false | Pending (no action) |
| `応募` | documents submitted | stage 3 | Positive |
| `書類通過` | passed document screening | stage 3 → 4 | Positive |
| `一次` / `二次` / `最終` | each interview stage | stage 4 (round in `status`) | Positive |
| `内定` | offer received | stage 5 (deadline = 回答期限) | Positive |
| `内定辞退` | you declined (→ `naitei-taiou.md`) | closed: true, reason 内定辞退 | Self-filtered |
| `お見送り` | the company rejected | closed: true, reason お見送り | Negative |
| `見送り(自己)` | you did not apply / withdrew | closed: true, reason 自己見送り | Self-filtered |

**outcome classes (for analysis):** Positive = 応募~内定 / Negative = お見送り / Self-filtered = 辞退·自己見送り /
Pending = 評価済.

### Capturing the rejection reason (お見送り)

When an entry closes as `お見送り`, the reason you can record depends on the `channel`:

- **`channel: agent | scout`** — a real CA/RA relays the company's actual feedback. **Ask the user for
  the verbatim text** ("エージェントからのお見送り理由の原文をそのまま貼ってください") and store it in the
  entry's `agent_feedback` field, **unedited, in its original language**. Do not paraphrase or soften — the
  wording is the data. This feeds the 面接遂行品質 tier in §3.
- **`channel: site | referral`** — direct applications almost always return a 定型 お祈りメール with no real
  reason. Leave `agent_feedback: null`. Do not invent a reason; the candidate's own hunch goes in `status`,
  not `agent_feedback`.

`closed_reason` stays the coarse label (`お見送り`); `agent_feedback` holds the verbatim quote.

---

## 3. Pattern analysis (on-demand at ≥5 entries)

If `data/pipeline.yml` has **5+ confirmed-outcome entries** (excluding 評価済), analysis is possible.
If fewer:
> "Not enough data — only {N}/5 have moved past evaluation. Apply more and I'll analyze when there's more."
then exit.

Aggregation is **done by the LLM reading pipeline.yml directly** — entries plus their `history` event
logs and any `agent_feedback` quotes (no Node script). Add a "±approximate, sample {N}" disclaimer to
every figure.

### Output structure (career-docs/pattern-analysis-[YYYYMMDD].md)

```markdown
# 選考パターン分析 — {YYYY-MM-DD} (sample {N}, ±approximate)

## 1. Conversion funnel
| Stage | Count | % |
| 応募 → 書類通過 → 一次 → 二次 → 最終 → 内定 | … | … |

## 2. Score vs outcome
| outcome | avg score | min | max | count |
| Positive / Negative / Self-filtered | … |

## 3. Blocker frequency (お見送り·自己見送り reasons)
### 3a. Tier A — 属性ミスマッチ
| Blocker | Count | % of all |
### 3b. Tier B — 面接遂行品質 (from agent_feedback quotes; blank if no agent-channel feedback yet)
| Blocker | Count | 原文 evidence (社名) |

## 4. Top-3 recommendations (with reasoning)
```

### Blocker categories — two tiers

Blockers split into two kinds. **Tier A** is inferred from candidate-attribute × outcome correlation
(structured data, available for every closed entry). **Tier B** is extracted from the verbatim
`agent_feedback` text and is only available for entries where that field is populated (channel =
agent | scout). Run both; label each blocker with its tier so the reader knows attribute vs execution.

**Tier A — 属性ミスマッチ (attribute mismatch)** — career-ops's geo/onsite/stack mapped to the Japanese context:

| Blocker | Signal | Response |
|---------|--------|----------|
| **ビザ** | 在留資格 × 職種カテゴリ mismatch, renewal imminent | `matching-simulator` visa risk + VISIONARY CAREER routing |
| **日本語要件 (JLPT)** | N3 or below, non-engineer | `platforms.md` JLPT routing (foreign-capital / Korean firms) |
| **県外/東京onsite** | full on-site + residence mismatch | re-target full-remote / regional hubs |
| **35歳の壁 / age** | 40s+ outside management | strengthen specialization/management appeal |
| **スキルマッチ (Core Lead Tech)** | repeated F Match (`evaluation_rules.md`) | skillset shift or re-target role |
| **短期離職懸念** | repeated job changes under 1 year | route to direct-apply (Green/BizReach), address 定着 head-on |

**Tier B — 面接遂行品質 (interview execution quality)** — read every `agent_feedback` verbatim quote and
classify it against the signals below. These are *how the candidate answered*, not *who they are* — the same
person keeps losing offers until the delivery changes, so a repeat here is the highest-leverage fix. A single
feedback quote can hit more than one row.

| Blocker | Signal in `agent_feedback` (原文) | Response |
|---------|-----------------------------------|----------|
| **数値なしエピソード** | 「成果が見えにくい」「特出したエピソードが少ない」「具体性に欠ける」 — vague-impact language | `matching-simulator` STEP 4 STAR+R (fill the **R** column with 実績数値 + 比較基準), or `shokumu-review` for the 職務経歴書 |
| **PREP構造欠如** | 「会話の整理に課題」「話が長い」「要点が伝わりにくい」 — answers ramble, no 結論ファースト | `job-seeker-agent` interview-content prep — drill 結論→理由→具体例→結論 (PREP) on the top questions |
| **自己弱点の自白** | candidate's own words quoted back as the concern: 「ソフトスキルが大変」「苦手分野で集中が難しい」「長時間働いて対応」 | ban-list those self-disclosures; reframe 高負荷対応 as 優先順位設計・生産性・分散. `mensetsu-manner.md` + job-seeker-agent |
| **企業理解不足** | 「志望動機が浅い」「他社でも良いのでは」「事業理解が弱い」 | `kigyou-bunseki` 企業カルテ before the next round; rebuild 志望動機 3-part structure in job-seeker-agent |

Tier B needs qualitative reading, so state sample size honestly: with 1–2 feedback quotes, report the
signal as an "observation," not a pattern. A Tier B blocker seen **twice across different companies** is a
confirmed execution gap — flag it as the #1 recommendation regardless of raw frequency, because it is
fully within the candidate's control to fix before the next interview.

### Analysis tone rules
- No comfort like "losing X isn't a big deal." Data only: "geo blocker is X% of the sample → recommend stopping that type."
- Recommendations are **action + reason + impact estimate**. e.g., "県外onsite 0% conversion (7/24) → filter onsite postings."
- For Tier B, quote the 原文 fragment as the evidence, then name the fix. e.g., "『会話の整理に課題』(AMBL)
  → PREP未実行。job-seeker-agent で結論ファースト10問ドリル。" Never generalize a Tier B blocker without its source quote.

---

## 4. Post-analysis action suggestions

> "Want me to apply any of these?
> - Pre-filter [blocker] type at the kigyou-bunseki / application stage
> - Set a score threshold (e.g., hold applications below 70)
> - Adjust targeting toward better-converting roles/company types (`_shared/frameworks.md §7`)"

Apply only after user approval. No arbitrary changes.

---

## Honesty Gate
- Do not fill missing results with inference. Leave the unconfirmed blank.
- With a small sample (<10), do not assert a pattern — present "direction" only.
- State that every conversion rate/average is an LLM approximation (count manually to verify if precision is needed).
