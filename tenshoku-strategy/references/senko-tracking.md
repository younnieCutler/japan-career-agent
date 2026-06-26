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

## 1. Tracker file (career-docs/applications.md)

Run it as a single markdown table following the existing `career-docs/` convention. Append one row per application.

```markdown
# 応募トラッカー

| # | 日付 | 企業 | 職種 | プラットフォーム | スコア | ステータス | 求人真正性 | メモ |
|---|------|------|------|----------------|--------|-----------|-----------|------|
| 1 | 2026-06-26 | A社 | DE | doda | 78 | 一次 | 信頼度高 | 中途比率45% |
```

- **スコア:** the `matching-simulator` result (0–100), or blank if not run.
- **求人真正性:** the `kigyou-bunseki` 求人の真正性 tier (信頼度高/要注意/要確認).
- If the file is missing, create it at the workspace root under `career-docs/`. Tell the user the path after saving.

---

## 2. ステータス state machine (fixed 8+ states)

career-ops's 8 states mapped to the Japanese job-change flow. Use this order/naming as fixed.

| ステータス | Meaning | outcome class |
|-----------|---------|---------------|
| `評価済` | only matching/battlecard done (not applied) | Pending (no action) |
| `応募` | documents submitted | Positive |
| `書類通過` | passed document screening | Positive |
| `一次` / `二次` / `最終` | each interview stage | Positive |
| `内定` | offer received | Positive |
| `内定辞退` | you declined (→ `naitei-taiou.md`) | Self-filtered |
| `お見送り` | the company rejected | Negative |
| `見送り(自己)` | you did not apply / withdrew | Self-filtered |

**outcome classes (for analysis):** Positive = 応募~内定 / Negative = お見送り / Self-filtered = 辞退·自己見送り /
Pending = 評価済.

---

## 3. Pattern analysis (on-demand at ≥5 entries)

If `career-docs/applications.md` has **5+ confirmed-outcome entries** (excluding 評価済), analysis is possible.
If fewer:
> "Not enough data — only {N}/5 have moved past evaluation. Apply more and I'll analyze when there's more."
then exit.

Aggregation is **done by the LLM reading the table directly** (no Node script). Add a "±approximate, sample {N}"
disclaimer to every figure.

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
| Blocker | Count | % of all |

## 4. Top-3 recommendations (with reasoning)
```

### Japan-specific blocker categories

career-ops's geo-restriction/onsite/stack mapped to the Japanese job-change context:

| Blocker | Signal | Response |
|---------|--------|----------|
| **ビザ** | 在留資格 × 職種カテゴリ mismatch, renewal imminent | `matching-simulator` visa risk + VISIONARY CAREER routing |
| **日本語要件 (JLPT)** | N3 or below, non-engineer | `platforms.md` JLPT routing (foreign-capital / Korean firms) |
| **県外/東京onsite** | full on-site + residence mismatch | re-target full-remote / regional hubs |
| **35歳の壁 / age** | 40s+ outside management | strengthen specialization/management appeal |
| **スキルマッチ (Core Lead Tech)** | repeated F Match (`evaluation_rules.md`) | skillset shift or re-target role |
| **短期離職懸念** | repeated job changes under 1 year | route to direct-apply (Green/BizReach), address 定着 head-on |

### Analysis tone rules
- No comfort like "losing X isn't a big deal." Data only: "geo blocker is X% of the sample → recommend stopping that type."
- Recommendations are **action + reason + impact estimate**. e.g., "県外onsite 0% conversion (7/24) → filter onsite postings."

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
