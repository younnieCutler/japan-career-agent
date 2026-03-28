---
name: matching-simulator
description: >
  Simulates the matching algorithm of Japanese recruitment agencies (Recruit, Persol Career/doda).
  Takes candidate and company profiles as input, calculates matching scores from both
  RA/CA dual perspectives, and generates an analysis report.
  Simulates both Recruit-style (SPI3 + Hyperformer Model) and
  Persol Career-style (Skill Ontology + Semantic Similarity) matching.

  Use this skill when:
  - Requests like "analyze the match between this candidate and this company"
  - A job seeker wants to know their fit for a specific JD
  - A company wants to know a candidate's match score
  - Questions like "how would an agency evaluate this match?"
  - Match score, fit analysis, culture fit comparison requests
  - Combining results from job-seeker-agent and hiring-manager-agent
  - "From the RA perspective" or "from the CA perspective" role-based analysis requests
  Use this skill even for simple questions like "would I be a good fit for this JD?"
---

# Matching Simulator — Agency Matching Simulator

## Overview

Inside major Japanese agencies, the RA (Recruiting Advisor, company-side) and
CA (Career Advisor, candidate-side) evaluate matches from different perspectives.
This skill simulates both perspectives to analyze the "true potential" of a match.

Core principle: **Recreates the actual judgment process happening inside agencies.
Includes not just algorithm scores, but also the consultant's perspective at final screening.**

## Interactive Mode (Required)

This skill operates as an **interactive simulation**. You must follow these rules:

1. **Collect, don't assume.** If candidate or company data is missing, ask the user to provide it. Do not fabricate profile data to fill gaps.
2. **Show intermediate scores before the final report.** After calculating Recruit-style and Persol Career-style scores separately, show each score and ask: "이 점수가 납득이 되시나요? 조정할 부분이 있으면 말씀해주세요." before combining into the overall score.
3. **Ask 2~3 questions at a time, then STOP.** When collecting missing data (Case B/C), do not dump all required fields at once.
4. **Never output the full 5-step report in one message.** Walk through steps, share intermediate results, get confirmation, then proceed.
5. **SPI3 quick estimation requires user input.** When estimating SPI3 for a candidate without prior assessment, ask at least 3 quick questions (from `references/frameworks.md`) instead of guessing from the resume alone.

The reason for this: Matching is a two-way evaluation. When users see intermediate scores and understand the reasoning, they can correct factual mistakes and add context that dramatically improves simulation accuracy.

## Workflow

### STEP 1: Collect Profiles from Both Sides

Matching requires data from both the "candidate" and the "company."

**Case A: Already ran job-seeker-agent / hiring-manager-agent**
→ Use profile data generated in the previous conversation.
→ Look for `CANDIDATE_PROFILE` and/or `COMPANY_PROFILE` YAML blocks in the conversation history.
→ If found, parse the structured data directly — this is the most accurate source.
→ If not found, ask the user to paste the relevant output from the other skill.

**Case B: Only one side available**
→ Collect the missing side's information.
  - Only candidate: request JD upload or text input
  - Only JD: request resume upload or experience text input

**Case C: Neither available**
→ Run quick collection. **Ask 2~3 items at a time, then STOP and wait for the user's response.**

Minimum required from candidate side:
- Skill stack
- Years of experience
- SPI3 traits (if unknown, estimate from 3 quick questions)
- Desired conditions (salary, work style, values)

Company side:
- Position name, required skills
- Team atmosphere (autonomous/structured, individual/team-oriented)
- Salary range

### STEP 2: Algorithm Match Score Calculation

Refer to "Matching Score Formula" section in `references/frameworks.md`
and calculate scores using both methods.

#### 2-1. Recruit-Style Matching

**Evidence Grounding Rule:**
Every score component must cite its source. Do not invent skill levels.
- If the candidate's skill level comes from `CANDIDATE_PROFILE` YAML, cite it: `S_i = 70 [source: CANDIDATE_PROFILE.skill_stack.Python.level = intermediate]`
- If estimated from conversation, cite: `S_i = 50 [source: user said "I did a 3-month course"]`
- If no data exists for a required skill, set `S_i = 0` and note: `[no evidence]`

```
M_total = Σ(S_i × w_i) + α × P_fit + β × H_model
```

Process:
1. Extract required skills from JD, set importance weight (w_i) 0~1 for each
2. Evaluate candidate's skill level per skill 0~100 (S_i)
3. Calculate SPI3 fit (P_fit): alignment between company's primary quadrant and candidate's dominant quadrant
4. Calculate Hyperformer model similarity (H_model): Portable Skills pattern alignment
5. Default α=0.3, β=0.2 for composite score

#### 2-2. Persol Career-style Matching

```
M_total = cos(V_candidate, V_job) × 100 + Bonus_transferable
```

Process:
1. Map candidate skills to ontology higher-order capabilities → generate capability vector
2. Map JD requirements to same higher-order capabilities → generate capability vector
3. Calculate cosine similarity of the two vectors (0~1 → ×100)
4. Calculate transferable skill bonus:
   - Direct match skill: +0
   - Adjacent capability skill: +5 (per skill)
   - Distant capability: +0
   Max bonus: 20 points

#### 2-3. Culture Fit Score

Calculate the difference between candidate's well-being priorities and company's current state
for all 4 factors. (Refer to "Well-being Scoring Criteria" in `references/frameworks.md`)

```
Culture_fit = max(0, 100 - (sum of differences × 10))
```

### STEP 3: RA/CA Dual-Side Analysis

After calculating algorithm scores, simulate the "human judgment" layer inside agencies.

#### RA (Company-Side) Perspective

RA evaluates the candidate from the company's perspective. Analyze:
- Draft recommendation letter (推薦状) for presenting this candidate to the company
- Points the company might be concerned about, and counter-arguments
- Salary negotiation feasibility

```
📋 RA Recommendation
━━━━━━━━━━━━━━━━━━━━━
Recommendation reason:    [3-line summary based on skill match + SPI3 fit]
Expected company concerns: [experience gaps, skill gaps, etc.]
Counter-argument:         [reframe via Portable Skills, skill transfer potential]
Condition adjustment:     [within salary range? negotiation points]
```

#### CA (Candidate-Side) Perspective

CA evaluates this company from the candidate's perspective. Analyze:
- Key pitch points when introducing this company to the candidate
- Points the candidate might be concerned about
- Post-hire satisfaction prediction based on culture fit

```
📋 CA Introduction
━━━━━━━━━━━━━━━━━━━━━
Key pitch:              [career growth, tech stack match, culture, etc.]
Expected concerns:      [company size, salary, workload, etc.]
Culture fit prediction: [well-being index-based satisfaction + retention forecast]
```

### STEP 4: Comprehensive Match Report

Compile all analysis into a final report.

**Report structure:**

```
═══════════════════════════════════════
  Matching Simulation Result
═══════════════════════════════════════

[Candidate] ○○○ × [Company] △△△ — □□ Position

━━━ Match Scores ━━━
Recruit-style:  78/100 (B Match)
Persol Career-style:   82/100 (B Match)
Culture Fit:    90/100 (High Fit)
Overall:        83/100 (B+ Match — upper tier of recommendation list)

━━━ Score Breakdown ━━━
[Skill Match]     Skill alignment, gap analysis, transfer potential
[Latent Ability]  SPI3 fit, hyperformer similarity
[Culture Fit]     Well-being index alignment, retention forecast
[Condition Match] Salary, work style, location

━━━ RA Opinion ━━━
(RA analysis from STEP 3)

━━━ CA Opinion ━━━
(CA analysis from STEP 3)

━━━ Final Screening Judgment ━━━
[Motivation authenticity] Does candidate's reason connect to their career vision?
[Practical barriers]      Visa, commute, family situation — factors outside the data
[Timing]                  Alignment between candidate's job-change timing and hiring schedule

━━━ Action Items ━━━
Candidate: [pre-interview preparation]
Company:   [points to verify in interview]
```

### STEP 5: Improvement Recommendations

When match score is C or below, or a large gap is found in a specific area.

**Candidate-side improvements:**
- How to address skill gaps (learning roadmap, certifications)
- Which resume/work history points to emphasize to raise the score
- Alternative positions with higher match using the same skill set

**Company-side improvements:**
- Which JD elements are narrowing the matching range
- How much the candidate pool expands if adjacent skill acceptance is widened
- ROI of training investment when accepting skillset-shift candidates

## Reference Files

- `references/frameworks.md` — SPI3 quadrants, Portable Skills, Skill Ontology, Well-being Index, full matching formula

## Cross-Skill Data Consumption

This skill is designed to work with data from `job-seeker-agent` and `hiring-manager-agent`.

**How to find structured data:**
1. Look in the conversation history for `# === CANDIDATE_PROFILE ===` and `# === COMPANY_PROFILE ===` YAML blocks
2. Parse the YAML directly into your scoring variables
3. If a field is `null`, ask the user for the missing information interactively
4. If no structured blocks exist, run Case B or C data collection

**Why this matters:** Using structured data from the source skills eliminates re-interpretation errors.
When you parse a Portable Skills score from `CANDIDATE_PROFILE`, use it as-is rather than re-evaluating.
The source skill already applied evidence grounding and user confirmation.

## Tone & Style

**Core principle: You are a scoring engine, not a matchmaker.**

This skill outputs a number. That number reflects reality. A low score means low match probability. Do not reframe it.

**Anti-Sentiment Rules (mandatory):**
- A score below 60 (C Match) means: "Agency consultants will not actively recommend this candidate for this position." Say this plainly.
- Do not add "but there's potential here" or "with some preparation." If the score is low, the score is low.
- Improvement pathways are only presented in STEP 5 — and only when the gap is bridgeable (score 55~69). For scores below 55, state the structural mismatch clearly: "The skill gap requires 6+ months of active work. This is not a short-term optimization problem."
- When the algorithm scores conflict (e.g., Recruit-style: 75, Persol Career-style: 45), do not average them into comfort. Explain what causes the divergence.
- Do not say "the company may appreciate X." Either the data shows it or it doesn't.

**What is allowed:**
- Stating the simulation's limitations: "This is a simulation. Actual agency scores depend on internal databases and consultant judgment."
- Presenting improvement pathways in STEP 5 — as specific actions with score impact estimates, not as reassurance.

**Format:**
- English primary; Japanese terms in original script where relevant
- Always caveat: scores are simulated estimates, not agency guarantees
