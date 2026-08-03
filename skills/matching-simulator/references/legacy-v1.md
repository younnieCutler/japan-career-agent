# legacy_v1 — the retired heuristic scorer

> Experimental heuristic. Not an official Recruit/Persol model,
> not calibrated, and not a hiring-probability estimate.

Everything on this page is **off by default**. The default diagnosis is
`evidence_based_v3` (`../../_shared/matching_v3.py`). This page exists so that scores already
written to `data/match_history.md` and `data/pipeline.yml` remain readable, and so that a user
who explicitly asks for the old numbers gets them correctly labelled.

## Why it was retired

| Problem | What it caused |
|---|---|
| The names `Recruit-style` / `Persol-style` | Read as published company formulas. They never were. |
| `α=0.3`, `β=0.2`, `+5`, `×10`, platform multipliers | No validation data behind a single coefficient. |
| One 0–100 total | Ability, conditions, culture and interest were summed into one number, so a condition conflict could be offset by a skill strength. |
| Missing values scored as 50 / neutral | Absence of information became evidence of fit. |
| `Culture Fit = 100 − Σdiff × 10` | Four ordinal preference ratings rendered as a percentage. |

## Current state of each piece

| Piece | State |
|---|---|
| `recruit_style()` | legacy_v1, opt-in only |
| `persol_style()` | legacy_v1, opt-in only |
| `culture_fit()` | **discontinued** — raises `DiscontinuedError`. Historical values stay on disk; no new one is computed. |
| Platform modifier table (below) | legacy_v1, opt-in only |
| `match_score` in `data/pipeline.yml` | frozen. Existing values preserved, never rewritten; the pipeline CLI refuses new writes. |
| `predicted_tier` | frozen. `scripts/legacy_calibrate.py --legacy-experimental` displays existing ones, labelled legacy_v1. |

## Running it anyway

Only when the user explicitly asks for the legacy numbers. The opt-in flag is mandatory:

```bash
echo '{"recruit": {...}, "persol": {...}}' \
  | python3 "${CLAUDE_PLUGIN_ROOT:-.}/_shared/legacy_experimental.py" --legacy-experimental
```

Every result carries `model_version: legacy_v1` and the warning above. Reproduce both verbatim
in the output.

**Two hard rules when legacy output is shown:**

1. Never place a legacy score and a v3 result in the same table, ranking, or sort order. They
   measure different things and one of them was never validated against anything.
2. Never describe a legacy score as a Recruit, doda, or Persol result, as a pass probability, or
   as an 内定確率.

## Platform modifier table (legacy_v1 — multipliers, no validation)

These multipliers only ever adjusted a legacy 0–100 score. They have no role in v3, which has
no total to multiply. Kept here to explain historical entries.

| Platform | Primary weight boost | Secondary adjustment | Hard penalty triggers |
|---|---|---|---|
| **Recruit Agent** | `再現性`: ×1.4 on Portable Skills scoring | SPI3 fit: standard (α=0.3) | Employment gap >3 months → ×0.7; Short tenure (<1yr) → CA recommendation probability ×0.5 |
| **doda** | Portable Skills cosine similarity: ×1.3 | CA internal pre-screening modelled as a 19–22% pass gate | Fragmented skill profile → ×0.85 |
| **MyNavi Agent** | Age bracket match (<34): ×1.2 | First-time job change: +5pt | Age 35+: score cap at 75 |
| **Levtech** | Core tech stack match: ×1.5 | GitHub/portfolio presence: +8pt | Employment gap ≥2 months → ×0.65; Core Lead Tech absent → F Match override |
| **Green** | Culture Fit: ×1.4; GitHub activity: +10pt | No CA pre-screening gate | Gap-tolerant; no fragmentation penalty |
| **BizReach** | Profile completeness proxy: ×1.3 | Scout receipt rate as primary metric | Registration gate: 94% pass |
| **Wantedly** | Culture Fit: ×1.5 | No CA layer; salary data absent by design | No hard penalties |
| **VISIONARY CAREER** | Visa sponsorship flag: ×1.3 | Foreign-national IT specialist agency | JLPT N3 or below → block; no sponsor intent → block |

⚠️ The age and age-bracket rows are a second reason this table is retired: v3 principle **P5**
excludes protected and sensitive attributes (age, gender, nationality, family status) from fit
calculation entirely. Legal work eligibility is handled as an eligibility **fact**, never scored.

## What replaced what

| legacy_v1 | evidence_based_v3 |
|---|---|
| `recruit_style` total | Required Skill & Experience — matched / missing / unknown, plus confirmed-only coverage |
| `persol_style` cosine + transfer bonus | Skill mapping with an explicit `mapping_basis` per item |
| `culture_fit` 0–100 | Career Values & Conditions — aligned / tradeoff / conflict / unknown, per item, never totalled |
| Portable Skills 1–5 distance | MHLW 29-point composition distance (`mhlw-portable-skill.md`) |
| `overall_score` / `overall_grade` | `decision_status`: proceed / review / conflict |
| Behavioural signal proxy (`B_behavioral`) | Employer Signals — observed events only, no probability |
