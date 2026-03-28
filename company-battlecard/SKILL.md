---
name: company-battlecard
description: >
  Compare two (or more) companies head-to-head from a job seeker's perspective in Japan's
  IT/marketing sector. Scores each company across SPI3 culture fit, skill stack match,
  well-being alignment, growth trajectory, and practical factors (salary, remote, visa).
  Outputs a structured battlecard table with a clear winner per dimension.

  Use this skill when:
  - User says "A사 vs B사 어디가 나을까?", "which company should I apply to?"
  - User has multiple offers or JDs and wants to compare them
  - User asks "이 회사 분위기 어때?", "회사 비교해줘", "どっちがいい?"
  - Keywords: "비교", "compare", "battlecard", "vs", "어디가 나을까"
  - User is deciding between two companies after running job-seeker-agent
  Use this skill proactively when a user mentions multiple company names in a
  job search context, even without explicitly asking to compare.
---

# Company Battlecard — Japan IT/Marketing Company Comparison Agent

## Overview

This skill produces a structured head-to-head comparison of two companies from the candidate's perspective.
It answers one question: **"Given who I am, which company is the better fit — and by how much?"**

The output is a table. The table has a winner column. There is no "both are great" — one always scores higher.

## Input

This skill can consume data from two sources:

**1. CANDIDATE_PROFILE YAML (preferred)**
If the user previously ran `job-seeker-agent`, a `CANDIDATE_PROFILE` YAML block exists in the conversation.
Parse it directly — do not re-ask questions that were already answered.

**2. Minimal intake (fallback)**
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
| Foreign-capital / consulting | Result + Creation | Harmony alone |
| Agency / marketing | Creation + Harmony | Order alone |

Score based on alignment between candidate's primary SPI3 trait and company type.

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

## Reference Files

This skill uses the same frameworks as the suite:
- `references/frameworks.md` — SPI3 quadrants, Well-being Index dimensions

For full candidate assessment, run `job-seeker-agent` first, then feed the YAML output into this skill.
