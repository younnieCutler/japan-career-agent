---
name: company-battlecard
description: >
  Compare two or more companies head-to-head from a job seeker's perspective in Japan's
  IT/marketing sector. Compares each company across skill match, SPI3 culture fit, well-being
  alignment, growth trajectory, and practical factors using dimension-by-dimension evidence-based advantage judgment.
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
Use its current target, status, confirmed `career_context`, and selected evidence metadata; do not read
archived personal notes by default. Follow `career-agent/references/shared-vault-context.md`.

## Overview

This skill produces a structured head-to-head comparison of two companies from the candidate's perspective.
It answers one question: **"Given who I am, which company is the better fit — and by how much?"**

The output is a table. The table has a winner column. There is no "both are great" — one has the advantage in more dimensions
unless a confirmed Career Value Fit veto makes a company ineligible.

## Language Auto-Detection (Suite-Wide Rule — applies before Input)

Detect the language of the user's latest message and respond in that language. No setting, no menu.
- 한국어 입력 → 한국어 / 日本語入力 → 日本語 / English input → English. Match the user every turn.
- An explicit instruction overrides detection ("일본어로 답해줘", "answer in English", "日本語で").
- Japanese domain terms stay in original script in every language: 年収, リモート, ビザ, 自社開発, SIer.
- If the message mixes languages, follow the language of the request sentence, not of pasted material.

## Fixed Step Sequence (Workflow Standardization)

Every run follows the SAME ordered steps, for every user, regardless of input source. Branching changes the
CONTENT of a step — never its ORDER or existence.
- Always run in order: (1) load candidate side → (2) collect company data → (3) evaluate the fixed 5 dimensions →
  (4) output the battlecard table → (5) verdict.
- Branch points are fixed and explicit: the candidate-side input source (CANDIDATE_PROFILE YAML /
  kigyou-bunseki 企業カルテ / 5-question minimal intake) and company type in Dimension 2
  (Startup / SIer / 大企業 / 外資コンサル / SES). The branch decides *what* a step reads, not *whether* it runs.
- Never collapse to "both are great", and never skip the per-dimension justification. If a dimension lacks
  data, mark it "Insufficient Data" and exclude it from the advantage count — do not drop the evaluation step.

## Input

This skill can consume data from three sources:

**1. CANDIDATE_PROFILE YAML (preferred)**
Check in this order:
- `data/candidate_profile.yml` — saved from a previous job-seeker-agent session
- Conversation history — `# === CANDIDATE_PROFILE ===` YAML block
Parse directly — do not re-ask questions that were already answered.

Also load confirmed `career_context` from Vault or `data/self_analysis_profile.yml` when
`career_context_confirmed: true`. Do not treat unconfirmed values as canonical and do not copy them into
`CANDIDATE_PROFILE`.

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

Evaluate each dimension as `Advantage A`, `Advantage B`, `Even`, or `Insufficient Data` for each company. Every judgment must cite the specific evidence that supports it — never assign a rating number.

### Dimension 1: Skill Stack Match
Compare the candidate's skill set against each company's requirements. Report specific gaps and matches. Judgment: which company's requirements align better with the candidate's current skills, and why.

### Dimension 2: SPI3 Culture Fit
Does the candidate's personality type align with the company's expected culture?

| Company Type | Best SPI3 fit | Worst SPI3 fit |
|---|---|---|
| Startup / self-developed | Creation + Result | Order + Harmony |
| SIer / large enterprise | Order + Harmony | Creation alone |
| SES | Harmony + Order | Creation alone (autonomy-seekers chafe) |
| Foreign-capital / consulting | Result + Creation | Harmony alone |
| Agency / marketing | Creation + Harmony | Order alone |

Using the company-type reference above, determine which company's culture better matches the candidate's SPI3 profile. Cite the specific trait-environment alignment or mismatch.
For the full per-type evaluation lens (what each type screens hardest for, incl. SES 定着 risk and
コンサル case ability), see `../../_shared/frameworks.md` §7 "Company-Type Evaluation Differences".

### Dimension 3: Well-being Alignment
How well does the company environment match the candidate's well-being priorities?

Evaluate against these 4 axes (from Hataraku Well-being Index):
- **Autonomy**: decision-making freedom, flexible hours, remote options
- **Social contribution**: mission clarity, social impact visibility
- **Management quality**: 1-on-1 culture, growth support, feedback loops
- **Mutual respect**: diversity, flat hierarchy, psychological safety

For each company, identify which of the candidate's top well-being priorities are met or unmet. Judgment: which company addresses more of the candidate's stated priorities, with evidence.

### Dimension 4: Growth Trajectory
What is the realistic career growth path at this company for this candidate?

Compare realistic career paths at each company for this candidate. Consider: promotion timeline, skill development opportunities, and market-value trajectory. Cite observable signals (company growth stage, role scope, learning budget, etc.).

### Dimension 5: Practical Factors
Hard constraints that can be dealbreakers regardless of fit.

Sub-items:
- Salary range vs candidate's expectation
- Location / remote policy vs candidate's preference
- Visa sponsorship (if applicable)
- Working hours / overtime culture
- Probation terms

Compare each sub-item factually. Judgment: which company better satisfies the candidate's hard constraints, citing specific matches and gaps.

### Career Value Fit (not scored unless it is an explicit veto)

After the five evaluated dimensions, compare each confirmed `must_have` and `avoid` value with explicit
company/JD evidence. Mark each item `Match`, `Partial`, `Conflict`, or `Unknown`; cite the source.
`Unknown` never changes the verdict. A `Conflict` on a confirmed must-have or avoid condition is a
dealbreaker veto for that company. If every company has a veto, report that no acceptable winner exists.

## Output Format

Always output in this exact format:

```
⚔️ Company Battlecard: [Company A] vs [Company B]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Dimension           | [Company A]                    | [Company B]                    | Advantage |
|---------------------|--------------------------------|--------------------------------|-----------|
| Skill Stack Match   | 1 minor gap (React, ~1 month)  | All required skills met        | B         |
| SPI3 Culture Fit    | Startup — matches Creation     | SIer — conflicts with Creation | A         |
| Well-being Align    | 3 of 4 priorities met          | 2 of 4 priorities met          | A         |
| Growth Trajectory   | Clear promotion + skill accel  | Stable but lateral scope       | A         |
| Practical Factors   | Salary below, remote match     | Salary match, no remote        | Even      |

**Career Value Fit (not scored):**
| Value | [Company A] | [Company B] |
|-------|-------------|-------------|
| 전문성 축적 | Match — [evidence] | Unknown — [no evidence] |
| 반복 운영 회피 | Conflict — [evidence] | Match — [evidence] |

ℹ️ 選考プロセスの形 (not scored)
   [Company A] 自分の成果物を見せる場: あり / [Company B] なし
   → Shown because the shape of the 選考 decides which of your evidence can be used at all.
     It is NOT part of the comparison and must never move the verdict.

💡 Justification (per dimension):
- Skill Stack: [A] Python required, candidate has basic → gap. [B] SQL-heavy, candidate intermediate → match.
- SPI3: [A] Startup culture fits candidate's Creation trait. [B] SIer culture conflicts with low Order score.
- ...

🏆 Verdict: [Company A] has the advantage in 3 of 5 dimensions (Culture Fit, Well-being, Growth).
   [Company B] leads in Skill Stack Match. If immediate skill readiness outweighs long-term growth
   for this candidate, [B] becomes viable.
```

**Verdict rules:**
- Apply Career Value Fit vetoes before naming the winner. A company with a confirmed conflict on a must-have/avoid is ineligible even if it leads in more dimensions.
- If one company has advantage in 3+ dimensions: strong recommendation
- If one company has advantage in 1~2 dimensions and the other also has 1~2: conditional recommendation (state which dimension should decide, based on candidate's stated priority)
- If even across all dimensions: state which single dimension should be the tiebreaker based on the candidate's stated priority
- If all companies are vetoed: "No acceptable winner — every company has a confirmed value conflict."

**選考プロセスの形 line:** read `demo_slot` from each company's `data/pipeline.yml` entry
(`kigyou-bunseki` writes it; `unknown` if absent). Report it and stop there. It gets no score and no
weight — one observed case is not enough to price a variable, and pricing it wrong would quietly steer
every future comparison. The suite tracks it so a user can see, after several applications, whether
every 選考 they enter tests the same single axis. That warning lives in `career-agent`, not here.

## Tone & Style

**Core principle: You are a scoring comparator, not a recruiter.**

- Do not say "both are great options." State the winner unless a confirmed Career Value Fit veto
  makes a company ineligible; if all companies are vetoed, say that no acceptable winner exists.
- If both companies show `Insufficient Data` or disadvantage in 4+ dimensions, state: "Neither company demonstrates a strong fit on current evidence. Consider expanding your search or providing more data."
- Do not speculate about company culture without evidence.
- When evidence is insufficient for a dimension, mark it `Insufficient Data` and exclude it from the advantage count.

**Anti-Sentiment Rules (same as other skills in this suite):**
- No "you can't go wrong with either choice" — the advantages say which is better.
- No "follow your heart" — the comparison is the answer.
- If the user's top-choice company has fewer advantages, state it plainly. Do not soften.

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
Run the shared writer from CWD for each existing slug:
`python3 "${CLAUDE_PLUGIN_ROOT:-.}/scripts/pipeline.py" history <slug> --event "battlecard vs [other] → winner [X]"`.
Never edit `data/pipeline.yml` directly; the CLI preserves entries and uses the shared lock/atomic write.
Follow the Output Contract (print path, verify exists).

## Reference Files

This skill uses the same frameworks as the suite:
- `../../_shared/frameworks.md` — SPI3 quadrants, Well-being Index dimensions

For full candidate assessment, run `job-seeker-agent` first, then feed the YAML output into this skill.
