# Platform Modifier Rules

Before running the matching algorithm, adjust how weights are distributed based on the `target_platform`.

## 1. Platform Modifier Table

| Platform | Primary weight boost | Secondary adjustment | Hard penalty triggers |
|---|---|---|---|
| **Recruit Agent** | `再現性 (Reproducibility)`: ×1.4 applied to Portable Skills scoring. Process description presence is checked separately. | SPI3 fit: standard (α=0.3) | Employment gap >3 months → overall score ×0.7; Short tenure (<1yr) flag → CA recommendation probability ×0.5 |
| **doda** | Portable Skills cosine similarity: weight ×1.3 | CA internal pre-screening modeled as 19~22% pass gate; only scores ≥70 clear this gate | Fragmented skill profile → Portable Skills score ×0.85 |
| **MyNavi Agent** | Age bracket match (<34): ×1.2 on overall | First-time job change bonus: +5pt | Age 35+: score cap at 75 (MyNavi Agent's limited senior inventory) |
| **Levtech** | Core tech stack match (Skill Sheet): weight ×1.5 | GitHub/portfolio presence: +8pt | Employment gap ≥2 months → score ×0.65; Core Lead Tech absent → F Match override (score = 0–20, not improvable) |
| **Green** | Culture Fit score: weight ×1.4; GitHub activity: +10pt | No CA pre-screening gate | Employment gap: no penalty (gap-tolerant); Fragmented profile: no penalty (startup flexibility) |
| **BizReach** | Profile completeness proxy (skill depth, achievement specificity): ×1.3 | Scout receipt rate simulated as primary metric | Registration screening gate: 94% pass (low bar); score reflects headhunter appeal, not CA routing |

| **Wantedly** | Culture Fit score: weight ×1.5; Mission/vision alignment signal weighted highly | No CA layer — direct apply only; salary data absent (by platform design) | No hard score penalties; platform is culture-first and gap-tolerant |
| **VISIONARY CAREER** | Visa sponsorship flag: ×1.3 bonus when `visa_sponsorship: true`; JLPT ≥N2 required | Niche agency specializing in foreign nationals in Japan; mid-career IT focus | JLPT N3 or below → block entirely; no sponsor intent → block |

Apply the modifier **before** running the per-platform algorithm scoring.
