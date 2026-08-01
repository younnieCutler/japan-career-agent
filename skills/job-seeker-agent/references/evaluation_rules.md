# Evaluation Rules (Cold Mode & Gap Analysis)

This document contains the strict evaluation guidelines for `job-seeker-agent`.

## 1. JD Requirements Gap Analysis (STEP 0)

Compare JD's 必須 (required) items against the candidate's current status. **First, identify Core Lead Tech** — the 1–3 non-negotiable skills that define the role (e.g., Spark/Airflow for DE, Swift for iOS, etc.).

```
🔍 Requirements Gap Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━
| Required Condition         | Candidate Status         | Verdict      |
|----------------------------|--------------------------|--------------|
| [Core Lead Tech] Spark     | No experience            | 🚫 F Match   |
| SQL 1yr+ hands-on          | SELECT-level, ~0.5yr     | ❌ Short     |
| Business-level Japanese    | N3 (conversational)      | ⚠️ Borderline |
```

**Verdict definitions:**
- `🚫 F Match` — Core Lead Tech absent. Screening odds are low regardless of other strengths.
- `❌ Short` — Required condition not yet met but bridgeable (skill exists at lower level).
- `⚠️ Borderline` — May pass or fail depending on interview; high uncertainty.
- `✅ Met` — Condition satisfied.

**Position re-targeting criteria:**
- Any `🚫 F Match` → **Stop and confirm before continuing** (see below). Present re-targeting options first.
- 0~1 `❌ Short`, no F Match → Can cover with resume improvements (proceed to STEP 1)
- 2 `❌ Short`, no F Match → Submit with supplementary plan (portfolio/study plan)
- 3+ `❌ Short`, no F Match → Same confirm-before-continuing handling as F Match.

**F Match handling — confirm, do not decide for the user:**

State the odds plainly, offer re-targeting, then ask. Do not refuse to continue.

```
🚫 F Match — [missing core skill]
This is the skill the role is built around. Screening odds are low and no resume
wording changes that.

Better-odds alternatives: [2–3 concrete roles/companies where the existing stack is core]

Apply anyway? Some candidates reach interviews on a partial stack, and a rejection via
an agent still returns a real reason. (y/n)
```

If the user proceeds, continue the full workflow — no degraded output, no repeated warnings —
and set `gate_override: true` on the pipeline entry.

Why this is a confirmation rather than a stop: this gate has never been scored. Nobody has data
on how often it blocked an application that would have succeeded, because blocked applications
produce no outcome to measure. `gate_override` plus `reached_stage` makes it measurable per user
after a few entries (`career-agent calibrate`). Until then, the gate advises and the user decides.

## 2. Portable Skills Scoring Principles & Conservatism Bias (STEP 3)

**General Principles:**
- **Default score = 2.** Start every skill at 2/5. Raise only when concrete evidence explicitly supports it. The burden of proof is on the evidence.
- **Base on actual experience only — mark absent experiences as 0 with "no experience".**
- **Score cannot appear in output without an inline citation.** Correct format: `Score X/5 — [evidence: "specific quote"]`.
- **What does NOT count as evidence:** Job title alone, self-reported intention ("공부 중"), vague verbs ("managed"), generic traits ("성실함").
- **再現性 (Reproducibility) bonus signal**: Recruit Agent's core concept. When evidence shows *how* (the process/method) and it is transferable, note explicitly: `[再現性 high]`.

**📛 Conservatism Bias Rules (Cold Mode — mandatory):**
- **Business impact gating:** If a result is not evidenced by measurable business impact (revenue ↑, cost ↓, productivity ↑, error rate ↓), the maximum score for that item is **3/5**.
  - A junior-level (under 2 years, or team of <3 people) process improvement without organisation-wide outcome = max 3/5. State: `[Junior-scope limit applied: max 3/5]`
- **Learning ≠ demonstrated skill.** Self-study, Udemy, or "学習中" can ONLY bump the **Drive** score. They contribute 0 to technical skills or other Portable Skills. State: `[Learning-only: counts for Drive, not this skill]`
- **Score inflation check:** Before finalising, ask: "Would a senior RA at Recruit Agent seeing this resume agree?" If uncertain, downgrade to 3/5.

## 3. Skill Ontology Mapping Rules (STEP 3)

Reflect skill levels realistically:
- "Python self-study" → entry-level automation scripts.
- "SQL SELECT-level" → basic data retrieval (JOIN/aggregation unavailable).

**🚨 Ontology Gap Penalty (Cold Mode — mandatory):**
- **Core Lead Tech gate:** Every target role has non-negotiable skills. If ANY core skill is absent:
  - Peripheral skills (SQL, Python basics, AWS, etc.) receive a weight cap of **0.2** in matching.
  - Output mandatory warning:
  ```
  ⛔ CORE LEAD TECH GAP DETECTED
  Target Role: [role]
  Missing:     [skill1], [skill2]
  Impact:      Peripheral skills capped at ×0.2 weight. Screening passage probability: < 15%.
  ⚠️ LLM estimate, not a statistic (±10pt or more). Low odds, not zero — see the F Match
     handling in §1: the user decides whether to apply.
  ```
- Do NOT output "bonus points" for peripheral skills when core lead tech is absent.

**🔀 Narrative Consistency Check:**
- If skills span 3+ unrelated domains (e.g., Front-end + Marketing + Low-code) with no integrating narrative = **fragmented profile**.
- A fragmented profile triggers a concrete screening risk warning regarding RA evaluation risk ("What is this person's core expertise?").

**🔬 DE vs SE Ontology Separation:**
- These are distinct capability domains. Cross-mapping is NOT permitted (e.g., API development ≠ data pipeline optimisation).
- When SE background targets a DE role, always output transfer distance explicitly (Estimated upskill time).
