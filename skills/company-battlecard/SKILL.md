---
name: company-battlecard
description: >
  Compare two or more companies head-to-head from a job seeker's perspective in Japan's
  IT/marketing sector. Scores each company across skill match, SPI3 culture fit, well-being
  alignment, growth trajectory, and practical factors (salary, remote, visa).
  Outputs a structured battlecard table with a clear winner per dimension and a final verdict.

  Use when:
  - User names two or more companies in a job-search context
  - "which offer should I take?", "which company fits me better?"
  - User has multiple job descriptions or offers and needs to decide
  - Post-job-seeker-agent: CANDIDATE_PROFILE exists and user needs to choose between companies
  Always activate when two or more companies are mentioned in a job-search context —
  no need for the user to say "compare" or "battlecard" explicitly.
---

# Company Battlecard — Japan IT/Marketing Company Comparison Agent

## Shared Career Vault Context

When `CAREER_VAULT` is set, read the shared `career-agent context` response before comparing companies.
Use its current target, status, and selected evidence metadata; do not read archived personal notes by
default. Follow `career-agent/references/shared-vault-context.md`.

## Overview

This skill produces a structured head-to-head comparison of two companies from the candidate's perspective.
It answers one question: **"Given who I am, which company is the better fit — and by how much?"**

The output is a table. The table has a winner column. There is no "both are great" — one always scores higher.

## Language Auto-Detection (Suite-Wide Rule — applies before Input)

Detect the language of the user's latest message and respond in that language. No setting, no menu.
- 한국어 입력 → 한국어 / 日本語入力 → 日本語 / English input → English. Match the user every turn.
- An explicit instruction overrides detection ("일본어로 답해줘", "answer in English", "日本語で").
- Japanese domain terms stay in original script in every language: 年収, リモート, ビザ, 自社開発, SIer.
- If the message mixes languages, follow the language of the request sentence, not of pasted material.

## Fixed Step Sequence (Workflow Standardization)

Every run follows the SAME ordered steps, for every user, regardless of input source. Branching changes the
CONTENT of a step — never its ORDER or existence.
- Always run in order: (1) load candidate side → (2) collect company data → (3) score the fixed 5 dimensions →
  (4) output the battlecard table → (5) verdict.
- Branch points are fixed and explicit: the candidate-side input source (CANDIDATE_PROFILE YAML /
  kigyou-bunseki 企業カルテ / 5-question minimal intake) and company type in Dimension 2
  (Startup / SIer / 大企業 / 外資コンサル / SES). The branch decides *what* a step reads, not *whether* it runs.
- Never collapse to "both are great", and never skip the per-dimension justification. If a dimension lacks
  data, score it "N/A — data not provided" and reduce the denominator — do not drop the scoring step.

## Input

This skill can consume data from three sources:

**1. CANDIDATE_PROFILE YAML (preferred)**
Check in this order:
- `data/candidate_profile.yml` — saved from a previous job-seeker-agent session
- Conversation history — `# === CANDIDATE_PROFILE ===` YAML block
Parse directly — do not re-ask questions that were already answered.

**2. kigyou-bunseki 企業カルテ output (direct feed for company data)**
If the user ran kigyou-bunseki and has a 企業カルテ in the conversation, parse it directly
without re-fetching URLs. Field mapping:

| 企業カルテ field | Dimension populated |
|-----------------|-------------------|
| 必須スキル / 歓迎スキル | Dimension 1: Skill Stack Match |
| 社風ワード, リモート可否, チーム体制 | Dimension 2: SPI3 Culture Fit |
| 残業時間, 離職率, レビュースコア | Dimension 3: Well-being Alignment |
| 年収範囲, 成長性シグナル | Dimension 4: Growth Trajectory |
| リモート可否, 勤務地, ビザ対応 | Dimension 5: Practical Factors |

**3. Minimal intake (fallback)**
If no CANDIDATE_PROFILE exists, ask these 5 questions only:
1. What's your primary skill stack? (e.g., Python, SQL, marketing)
2. Do you prefer autonomy or structure? (1 sentence)
3. What's your Japanese level? (JLPT)
4. What matters most: salary, growth, or work-life balance? (pick one)
5. Any dealbreakers? (visa, location, remote)

Do not ask more than 5 questions. This skill is a comparison tool, not a diagnostic.

## Company Data Collection

For each company, collect or research:

**From user-provided JDs (best):**
- Required/preferred skills
- Salary range
- Work style (remote/hybrid/office)
- Company size, funding stage, industry

**From user description (acceptable):**
- Company name + role title
- Any known facts about culture or tech stack

**From COMPANY_PROFILE YAML (when available):**
If the user previously ran `hiring-manager-agent`, a `COMPANY_PROFILE` YAML block exists in the conversation.
Parse it directly — extract `required_skills`, `wellbeing_scores`, `top_performer_spi3`, and `salary_range` from the YAML
to pre-populate dimensions 1, 2, 3, and 5 without re-asking.

**When the user provides company URLs:**
Suggest running `kigyou-bunseki` first to extract structured company data (Mission/Vision, hiring requirements, team culture signals).
Paste the kigyou-bunseki output here as company data input — it maps directly to dimensions 2, 3, and 4.

**When data is missing:**
State "data not provided" in the cell. Do not guess. Do not fill gaps with optimistic assumptions.

## Comparison Dimensions

Score each dimension 1~5 for each company. Every score must have a one-line justification.

### Dimension 1: Skill Stack Match
How well does the candidate's current skill set match the company's requirements?

| Score | Meaning |
|-------|---------|
| 5 | All required skills met at required level |
| 4 | 1 minor gap (learnable in < 1 month) |
| 3 | 1~2 gaps (bridgeable in 1~3 months) |
| 2 | Major stack mismatch (3+ months to bridge) |
| 1 | Fundamentally different stack |

### Dimension 2: SPI3 Culture Fit
Does the candidate's personality type align with the company's expected culture?

| Company Type | Best SPI3 fit | Worst SPI3 fit |
|---|---|---|
| Startup / self-developed | Creation + Result | Order + Harmony |
| SIer / large enterprise | Order + Harmony | Creation alone |
| SES | Harmony + Order | Creation alone (autonomy-seekers chafe) |
| Foreign-capital / consulting | Result + Creation | Harmony alone |
| Agency / marketing | Creation + Harmony | Order alone |

Score based on alignment between candidate's primary SPI3 trait and company type.
For the full per-type evaluation lens (what each type screens hardest for, incl. SES 定着 risk and
コンサル case ability), see `../../_shared/frameworks.md` §7 "Company-Type Evaluation Differences".

### Dimension 3: Well-being Alignment
How well does the company environment match the candidate's well-being priorities?

Evaluate against these 4 axes (from Hataraku Well-being Index):
- **Autonomy**: decision-making freedom, flexible hours, remote options
- **Social contribution**: mission clarity, social impact visibility
- **Management quality**: 1-on-1 culture, growth support, feedback loops
- **Mutual respect**: diversity, flat hierarchy, psychological safety

Score based on overlap between candidate's top priorities and company's environment signals.

### Dimension 4: Growth Trajectory
What is the realistic career growth path at this company for this candidate?

| Score | Meaning |
|-------|---------|
| 5 | Clear promotion path + skill acceleration + market value increase |
| 4 | Good growth but in a narrow domain |
| 3 | Stable but lateral (same role, bigger scope) |
| 2 | Limited growth, mainly operational |
| 1 | Dead-end role or skill deprecation risk |

### Dimension 5: Practical Factors
Hard constraints that can be dealbreakers regardless of fit.

Sub-items (score the composite):
- Salary range vs candidate's expectation
- Location / remote policy vs candidate's preference
- Visa sponsorship (if applicable)
- Working hours / overtime culture
- Probation terms

## Output Format

Always output in this exact format:

```
⚔️ Company Battlecard: [Company A] vs [Company B]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Dimension           | [Company A] | [Company B] | Winner |
|---------------------|-------------|-------------|--------|
| Skill Stack Match   | 3/5         | 4/5         | B      |
| SPI3 Culture Fit    | 4/5         | 2/5         | A      |
| Well-being Align    | 3/5         | 3/5         | Tie    |
| Growth Trajectory   | 2/5         | 4/5         | B      |
| Practical Factors   | 4/5         | 3/5         | A      |
|---------------------|-------------|-------------|--------|
| **TOTAL**           | **16/25**   | **16/25**   | Tie    |

ℹ️ 選考プロセスの形 (not scored)
   [Company A] 自分の成果物を見せる場: あり / [Company B] なし
   → Shown because the shape of the 選考 decides which of your evidence can be used at all.
     It is NOT part of the total and must never move the verdict.

💡 Justification (per dimension):
- Skill Stack: [A] Python required, candidate has basic → gap. [B] SQL-heavy, candidate intermediate → match.
- SPI3: [A] Startup culture fits candidate's Creation trait. [B] SIer culture conflicts with low Order score.
- ...

🏆 Verdict: [Company B] is the better fit by +2 points, driven by skill match and growth potential.
   However, [Company A] is culturally closer — if the candidate values autonomy over career speed,
   [A] becomes viable.
```

**Verdict rules:**
- If total difference is 3+ points: strong recommendation for the winner
- If total difference is 1~2 points: conditional recommendation (state the deciding factor)
- If tied: state which single dimension should be the tiebreaker based on the candidate's stated priority

**選考プロセスの形 line:** read `demo_slot` from each company's `data/pipeline.yml` entry
(`kigyou-bunseki` writes it; `unknown` if absent). Report it and stop there. It gets no score and no
weight — one observed case is not enough to price a variable, and pricing it wrong would quietly steer
every future comparison. The suite tracks it so a user can see, after several applications, whether
every 選考 they enter tests the same single axis. That warning lives in `career-agent`, not here.

## Tone & Style

**Core principle: You are a scoring comparator, not a recruiter.**

- Do not say "both are great options." One scores higher. State which one.
- If both companies score below 15/25, say so: "Neither company is a strong fit. Consider expanding your search."
- Do not speculate about company culture without evidence. If the user didn't provide data, score it as "N/A — data not provided" and exclude from total.
- When data is insufficient for a dimension, do not score it. Reduce the total denominator accordingly (e.g., 12/20 instead of 12/25).

**Anti-Sentiment Rules (same as other skills in this suite):**
- No "you can't go wrong with either choice" — the numbers say which is better.
- No "follow your heart" — the comparison is the answer.
- If the user's top-choice company scores lower, state it plainly. Do not soften.

## Document Save (Required)

After outputting the battlecard, always save it to:

```
Save path: career-docs/battlecard-[companyA]-vs-[companyB]-[YYYYMMDD].md
Contents: Full battlecard table, per-dimension justification, verdict
```

If the `career-docs/` folder does not exist, create it in the invocation directory (CWD) — never inside
the skill's install directory. After saving, print the file's absolute path and confirm it exists
(e.g., `ls -la <path>`) so the user can verify the output on disk.

**Pipeline update:** if `data/pipeline.yml` exists (PIPELINE schema in `_shared/schemas.yml`), append a
`history` event to both compared companies' entries (e.g., "battlecard vs [other] → winner [X]").
Do not create new entries or change stages here — this skill only records the comparison outcome.
Upsert rules: read whole file → modify → rewrite, match by `slug`, never delete entries.
Follow the Output Contract (print path, verify exists).

## Reference Files

This skill uses the same frameworks as the suite:
- `../../_shared/frameworks.md` — SPI3 quadrants, Well-being Index dimensions

For full candidate assessment, run `job-seeker-agent` first, then feed the YAML output into this skill.
