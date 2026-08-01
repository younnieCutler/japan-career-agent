# Japanese Recruitment Agency Framework Reference Data

This file contains common framework definitions referenced by the 3 recruitment agent skills.
Legal figures and market data are subject to change — verify with web search for the latest information.

---

## 1. SPI3 Personality Quadrant Model

An aptitude assessment tool developed by Recruit. Classifies candidate personality traits into 4 quadrants.

### Quadrant Definitions

| Quadrant | Japanese | Core Traits | High-Score Behavior Patterns |
|----------|----------|-------------|------------------------------|
| Creation | 創造 | Embraces change, prefers new approaches, originality | Questions existing rules, tries new approaches, interested in open-ended problems |
| Result | 結果 | Goal achievement drive, logical judgment, efficiency | Sets numerical targets independently, intolerant of inefficiency, motivated to prove through outcomes |
| Harmony | 調和 | Interpersonal skills, collaboration, empathy | Sensitive to team atmosphere, mediates conflicts, quickly reads others' emotions |
| Order | 秩序 | Process-oriented, stability, thoroughness | Checks manuals/processes first, cautious about changes, prioritizes quality and accuracy |

### SPI3 Matching Criteria by IT/Marketing Role

| Role | Primary Quadrant | Secondary Quadrant | Matching Rationale |
|------|-----------------|-------------------|-------------------|
| New Service Planning | Creation | Result | Ideation + execution |
| Growth Hacking Marketing | Creation | Result | Experimentation culture + data-driven |
| Performance Marketing | Result | Order | KPI achievement + data accuracy |
| PM / PjM | Result | Harmony | Schedule management + stakeholder coordination |
| Frontend Development | Creation | Harmony | UX sensibility + designer collaboration |
| Backend / Infrastructure | Order | Result | System stability + performance optimization |
| Data Engineer | Order | Creation | Data integrity + pipeline design |
| Data Analyst | Result | Creation | Insight generation + hypothesis testing |
| Client Agency Marketer | Harmony | Result | Client relationships + performance reporting |
| Team-Based Agile Development | Harmony | Creation | Sprint collaboration + technical proposals |
| System Operations/Maintenance | Order | Harmony | Process adherence + team communication |
| Data Governance | Order | Result | Compliance + quality metrics management |

### SPI3 Quick Diagnostic (12 Statements)

Each statement describes a personal tendency. Rate how much it applies to you on a scale of 1–5:

> **1** = Not at all &nbsp;|&nbsp; **3** = Neutral &nbsp;|&nbsp; **5** = Very much so

Present 3–4 statements at a time, STOP and wait for the user's ratings before continuing.

**Scoring rule:** Sum the 3 scores per quadrant (max 15), then multiply by 10/15 to normalize to 0–10. Round to one decimal.
`Quadrant score = (Q_a + Q_b + Q_c) × (10/15)`

---

**[Creation]**

**Q1.** I want to try a new approach even if I've never done it before.
Rate 1–5: ___

**Q2.** I prefer finding my own improved approach over following established methods.
Rate 1–5: ___

**Q3.** I perform better in environments with frequent change.
Rate 1–5: ___

---

**[Result]**

**Q4.** I feel strong satisfaction when I set a numerical goal and achieve it.
Rate 1–5: ___

**Q5.** I am always conscious of efficiency — getting the most output from the same time.
Rate 1–5: ___

**Q6.** Making decisions based on data and evidence feels natural to me.
Rate 1–5: ___

---

**[Harmony]**

**Q7.** I naturally notice shifts in team atmosphere or colleagues' emotions.
Rate 1–5: ___

**Q8.** When conflict arises, I try to understand both sides and mediate.
Rate 1–5: ___

**Q9.** I feel the most fulfilled when I achieve a goal together with my team.
Rate 1–5: ___

---

**[Order]**

**Q10.** I tend to check procedures or manuals before starting a task.
Rate 1–5: ___

**Q11.** I work better in environments where things proceed as planned, rather than with sudden changes.
Rate 1–5: ___

**Q12.** I have a strong commitment to maintaining quality and accuracy.
Rate 1–5: ___

---

### Score Calculation Example

If a user rates Q1=3, Q2=4, Q3=2 → Creation raw = 9 → normalized = 9 × (10/15) = **6.0/10**

### Score Interpretation

| Quadrant Score (0–10) | Strength Level |
|-----------------------|---------------|
| 0–3 | Low |
| 4–6 | Medium |
| 7–10 | High |

Note: This quick diagnostic does not replace the official SPI3.
It is a reference tool for identifying tendencies — use Recruit's official service for formal assessment.
Because each quadrant is rated independently, a person can score high in multiple quadrants simultaneously — this is expected and more realistic than forced A/B comparisons.

---

## 2. Portable Skills: 9 Elements (MHLW Official)

A framework published by the Japanese Ministry of Health, Labour and Welfare (厚生労働省) and used in Persol Career's career transition evaluation. Classifies universal competencies transferable across job types and industries into 9 elements across 2 domains.

> Source: MHLW official Portable Skills definition (厚生労働省 2023, mhlw.go.jp/content/11800000/000935264.pdf). Persol Career Research Institute may use a proprietary variant; this follows the MHLW standard.

### 2 Domains × 9 Elements

**仕事のし方 (5 elements — how you do work)**
1. **現状の把握**: Continuously collect and evaluate/analyze information about the current situation
2. **課題の設定**: Set improvement/solution strategies based on own problem awareness
3. **計画の立案**: Design effective scenarios toward goals; create concrete action plans
4. **課題の遂行**: Commit to growth/goal achievement; meet deadlines; execute reliably
5. **状況への対応**: Adapt flexibly to any change in circumstances

**人との関わり方 (4 elements — how you engage with people)**
6. **社内対応**: Coordinate with internal stakeholders with different values/interests; reach consensus
7. **社外対応**: Coordinate with external stakeholders (clients, partners); reach consensus
8. **上司対応**: Report upward; provide opinion/proposals to superiors
9. **部下マネジメント**: Understand subordinates' strengths, assign work, develop/coach

### Portable Skills Scoring Criteria

Each element is rated 1–5 based on STAR analysis of the resume/career history.

**Scoring rule:** Score at the **highest level where ALL conditions are met**. When in doubt between two levels, score the lower one (conservatism bias). Never score 4 or 5 without a concrete STAR example as evidence.

#### 現状の把握 (Situation Assessment)
| Score | Evidence Required |
|-------|-----------------|
| 1 | Describes what happened, not why. No causal reasoning present. |
| 3 | Identified primary cause using available data. Structured problem into 2–3 factors. Presented findings to someone. |
| 5 | Built multi-variable causal model. Identified non-obvious root cause. Designed new data collection approach. Findings changed a decision or process. |

#### 課題の設定 (Problem Setting)
| Score | Evidence Required |
|-------|-----------------|
| 1 | Follows existing process without questioning. Avoids change. |
| 3 | Proposed improvement to own workflow. Implemented change with manager support. Others adopted the change. |
| 5 | Redesigned a process affecting other teams. Built buy-in for major change independently. Change persisted after departure. |

#### 計画の立案 (Planning)
| Score | Evidence Required |
|-------|-----------------|
| 1 | No milestone setting. Works task-by-task. Missed deadlines without early warning. |
| 3 | Set milestones for own work. Flagged a risk in advance. Delivered within scope despite one unexpected change. |
| 5 | Managed multi-team dependencies. Allocated buffer proactively. Plan survived 2+ unexpected changes. Others relied on the plan. |

#### 課題の遂行 (Task Execution)
| Score | Evidence Required |
|-------|-----------------|
| 1 | Waits for instruction. Does not act without explicit approval. |
| 3 | Initiated action within own scope. Escalated blockers. Saw task to completion despite one obstacle. |
| 5 | Drove cross-team initiative. Navigated stakeholder resistance. Delivered despite 3+ blocking obstacles. Changed org-level behavior as a result. |

#### 状況への対応 (Situational Agility)
| Score | Evidence Required |
|-------|-----------------|
| 1 | Struggles to reprioritize. Needs significant lead time to absorb change. |
| 3 | Reprioritized within same day. Delivered acceptable output under new constraints. |
| 5 | Delivered high-quality output under sudden full-scope change. Kept team calm and aligned through the pivot. |

#### 社内対応 (Internal Coordination)
| Score | Evidence Required |
|-------|-----------------|
| 1 | Avoids disagreement with internal stakeholders. Accepts others' position without pushback. |
| 3 | Stated own position clearly. Found a compromise meeting core needs of both parties within the organization. |
| 5 | Resolved cross-department conflict between parties with fundamentally different goals. Created win-win through interest reframing. |

#### 社外対応 (External Coordination)
| Score | Evidence Required |
|-------|-----------------|
| 1 | Avoids conflict with clients or partners. Takes instructions without negotiating scope or terms. |
| 3 | Negotiated a change in client scope or timeline. Found a mutually acceptable outcome. |
| 5 | Managed a difficult client escalation or partnership conflict to a win-win resolution. Relationship preserved or strengthened. |

#### 上司対応 (Upward Communication)
| Score | Evidence Required |
|-------|-----------------|
| 1 | Reports only when asked. Never pushes back or proposes alternatives to superiors. |
| 3 | Proactively flagged a risk or proposed an alternative to a superior. Received receptive response. |
| 5 | Influenced a senior decision through data-backed proposal. Changed the direction of a project or strategy through upward communication. |

#### 部下マネジメント (Subordinate Management)
| Score | Evidence Required |
|-------|-----------------|
| 1 | No experience developing others. Works independently only. |
| 3 | Onboarded or mentored at least one junior. Gave actionable feedback. Junior made visible progress. |
| 5 | Developed multiple team members to next skill level. Built a team learning system (docs, structured reviews, 1:1s). |

---

## 3. Skill Ontology Mapping Table

A mapping table based on the skill ontology concept used by Persol Career/doda.
Automatically maps individual technical skills (Hard Skills) to higher-level competencies (Capabilities) to expand matching scope.

### IT Skill Ontology

| Skill | Capability | Transferable Roles |
|-------|-----------|-------------------|
| Python | Data analysis, AI modeling fundamentals, automation scripting | Data Engineer, ML Engineer, Backend |
| SQL | Data extraction/processing, Business Intelligence | Data Analyst, BI Engineer |
| JavaScript | Frontend development, full-stack potential | Frontend, Full-Stack, Node.js Backend |
| React | Component-based architecture, SPA development | Vue.js, Angular and other framework transitions |
| Vue.js | Component-based architecture, SPA development | React, Angular and other framework transitions |
| AWS | Cloud infrastructure design, IaC | GCP, Azure transitions, SRE |
| Docker/K8s | Container orchestration, CI/CD | DevOps, SRE, Platform Engineer |
| dbt | Data transformation, analytics engineering | Data Engineer, Analytics Engineer |
| Terraform | IaC, infrastructure automation | Cloud Engineer, SRE |
| Excel (Advanced) | Data literacy, business analysis fundamentals | Data analysis entry-level, BizOps |

### Marketing Skill Ontology

| Skill | Capability | Transferable Roles |
|-------|-----------|-------------------|
| Google Analytics | Data analysis, user behavior understanding | Product Manager, Growth |
| SEO | Content strategy, search algorithm understanding | Content Marketer, Product |
| Social Media Management | Community management, brand communication | PR, Brand Manager |
| Listing Ads | Performance marketing, ROI analysis | Data Analysis, Business Planning |
| MA Tools (HubSpot, etc.) | Lead management, customer journey design | CRM, Inside Sales |
| Figma | UI/UX sensibility, prototyping | UX Researcher, Product Designer |

### Skillset Shift Assessment Criteria

Compares a candidate's current skills against the required skills for a target role on the ontology.

| Transfer Distance | Judgment | Description |
|------------------|----------|-------------|
| Same capability | Direct match | Shares the same higher-level capability (React → Vue.js) |
| Adjacent capability | Transferable | Connected by moving up one level (Excel → Data Analysis) |
| Distant capability | Bootcamp needed | 2+ levels apart, separate learning required (Social Media → Backend) |

---

## 4. Hataraku Well-being Index

A metric that quantifies Persol Career Group's "Work-and-Smile" vision.
Measures the fit between a candidate's values and a company's organizational culture to predict retention.

### 4 Measurement Elements

| Element | Japanese | Definition | Best-Fit Company Type (High Score) |
|---------|----------|------------|-------------------------------------|
| Autonomy | 自己決定感 | Sense of being able to choose how and what to work on | Startups, autonomous IT companies, remote environments |
| Social Contribution | 社会貢献感 | Feeling that one's work helps others/society | B2C services, social enterprises, education/healthcare |
| Manager Quality | 上司のマネジメント | Positive feedback, listening, fair evaluation | 1-on-1 culture, coaching-style leadership organizations |
| Mutual Respect | 組織内の相互尊重 | Atmosphere of respect and collaboration among colleagues | Agile teams, flat organizations, high psychological safety |

### Well-being Scoring Criteria

Ask the job seeker to rate the importance of each of the 4 elements on a 1–5 scale.
The company also self-rates their current state on the same 4 elements on a 1–5 scale.
The degree of alignment between the two scores becomes the culture fit score.

| Alignment | Judgment |
|-----------|----------|
| Total difference 0–4 | Highly compatible (High Fit) |
| Total difference 5–8 | Moderate (Medium Fit) |
| Total difference 9+ | Incompatible (Low Fit) — early turnover risk |

---

## 5. Gakuchika (学チカ) Evaluation Framework

Evaluation criteria used in new graduate (Class of 2027) recruiting.
Quantifies a student's qualitative experiences across 4 categories.

| Evaluation Item | Data Points | Scoring Criteria (1–5) |
|----------------|-------------|------------------------|
| Impact | Scale of results, number of people affected | 5: 100+ people impacted / 1: individual level |
| Goal Achievement | Difficulty of goal, completion status | 5: high difficulty 100% achieved / 1: no goal set |
| Leadership | How collaboration was led, conflict resolution | 5: delivered results as team leader / 1: individual work only |
| Challenger Spirit | New attempts, learning from failure | 5: succeeded after repeated failures / 1: only safe choices |

---

## 6. Matching Score Calculation Formula

### Recruit Style (Weighted Sum Model)

```
M_total = Σ(S_i × w_i) + α × P_fit + β × B_behavioral
```

- S_i: Individual skill stack score (0–100)
- w_i: Skill importance weight for the role (0–1, sum = 1)
- P_fit: SPI3 personality fit — alignment between candidate's dominant quadrant and role's primary quadrant (0–100)
- B_behavioral: Behavioral signal score — approximates Recruit's CTR/collaborative filtering on browse/application history (0–100)
- α: Personality fit weight (default 0.3)
- β: Behavioral signal weight (default 0.2)

> **Evidence note:** The actual Recruit Agent/リクナビNEXT system uses CTR prediction + collaborative filtering on behavioral data (browse history, 「気になる」clicks, application history) — not a direct SPI3-quadrant weighted sum. The formula above is a useful approximation for self-evaluation. α=0.3, β=0.2 are simulation defaults, not Recruit's actual weights. SPI3 is a separate product sold by Recruit Management Solutions; its real-time integration into リクナビNEXT matching is not publicly confirmed. Source: Recruit Data Blog 2021 ML competition description + リクナビNEXT privacy policy.

**Normalization (required — keeps output in 0–100 range):**

Without normalization, M_raw can exceed 100 (max = 100 + 30 + 20 = 150). Always divide by (1 + α + β):

```
M_total = (Σ(S_i × w_i) + α × P_fit + β × B_behavioral) / (1 + α + β)
```

With defaults (α=0.3, β=0.2): `M_total = M_raw / 1.5`

**Worked example (Data Engineer candidate vs. DE role JD):**

| Component | S_i | w_i | S_i × w_i |
|-----------|-----|-----|-----------|
| Python | 70 | 0.5 | 35.0 |
| SQL | 80 | 0.3 | 24.0 |
| Docker/K8s | 20 | 0.2 | 4.0 |
| **Σ(S_i × w_i)** | | **1.0** | **63.0** |

P_fit (SPI3 Order+Creation vs. role primary Order) = 75
B_behavioral (estimated behavioral signal from application/browse history) = 60

M_raw = 63.0 + (0.3 × 75) + (0.2 × 60) = 63 + 22.5 + 12 = **97.5**
M_total = 97.5 / 1.5 = **65 → C Match**

### Persol Career Style (Semantic Similarity + Bonus Model)

```
M_total = cos(V_candidate, V_job) × 100 + Bonus_transferable
```

- V_candidate: Candidate skill vector (after ontology mapping)
- V_job: Job requirement skill vector
- cos(): Cosine similarity (0–1)
- Bonus_transferable: Transferable skill bonus (0–20)

> **Evidence note:** doda's actual セカンドマッチ system (3rd-generation, ~2020) uses supervised ML trained on 選考通過実績 (historical screening outcomes), with BERT extracting skill tags from 職務経歴書 as input features. The cosine similarity formula above is a useful academic approximation of the "match similar skill vectors" goal, but not the exact implementation. The system also models bidirectionality: both "will the candidate be interested" AND "will the company select this candidate." Source: Persol techtekt engineering blog (techtekt.persol-career.co.jp).

### Overall Score Interpretation

| Score Range | Judgment | Agency Action |
|-------------|----------|--------------|
| 85–100 | A Match | Recommend immediately, priority report to RA |
| 70–84 | B Match | Include in recommendation list, conditions need adjustment |
| 55–69 | C Match | Consider skillset shift, propose training investment |
| 54 or below | D Match | Hold matching, explore other positions |

---

## 7. Company-Type Evaluation Differences (6 Types)

Mid-career screening criteria differ sharply by company type. Use this to set the SPI3 best-fit, the
dominant evaluation lens, and what each type screens hardest for. (`company_type` enum in `schemas.yml`.)

| Type | Best-fit SPI3 | Dominant evaluation lens | Screens hardest for | Resume/answer emphasis |
|------|--------------|--------------------------|---------------------|------------------------|
| **自社開発 (self-developed)** | Creation + Result | Ownership, product impact | Self-direction, tech curiosity, "問題を見つけ動いた" | 再現性 of initiative; GitHub/Qiita |
| **SIer** | Order + Harmony | Reliability, process, 長期コミット | 報連相, quality, stability, 5-year vision | Process adherence + teamwork episodes |
| **SES** | Harmony + Order | Adaptability across client sites; 定着 risk | Short-tenure / job-hopping pattern, 自走 ability | Reframe多現場経験 as "環境適応力"; address 定着 head-on |
| **コンサル (consulting)** | Result + Creation | Logical structure, 地頭, case ability | Hypothesis-driven thinking, 客観性, 論理整合 | ケース面接 prep; 成果の構造化; ワンプール制 understanding |
| **スタートアップ (startup)** | Creation + Result | Speed, 0→1, role-fluidity | Autonomy, ambiguity tolerance, mission fit | Breadth + 自走; willingness to wear many hats |
| **大企業 (large enterprise)** | Result + Order | バリューFIT, スケール経験, キャラクター | Final-interview value fit, 意思決定の一貫性, オーナーシップ | Match company values; clear キャリアビジョン |

**Evaluation notes:**
- **SES → 定着リスク coupling:** SES candidates and frequent-mover profiles trigger the same CA refund-risk
  flag as short tenure (see `job-seeker-agent/references/platforms.md` blocking rules and
  `matching-simulator/references/evaluation_perspectives.md` RA Risk Signal). Address 定着 explicitly.
- **コンサル ≠ 事業会社:** consulting screens 地頭/case ability (`wq0WrdFXivA`, `ub5NFGRanfs`, `MFwaU-l75TI`);
  事業会社 screens domain 再現性. Do not cross-map a consulting "framework" answer onto an 事業会社 role.
- **大企業 final-interview filter:** large enterprises fail ~half of finalists on value fit / character /
  decision-consistency / career vision / ownership (`UdjQxAtAUUI`). These are *not* skill checks — prep them
  via the 4-WHY chain in `job-seeker-agent/references/shibo-doki.md`.

> Evidence basis (sincereed channel, public chapter structure — transcript detail unverifiable): コンサル
> `ub5NFGRanfs` / `wq0WrdFXivA` / `MFwaU-l75TI` / `8bUkK0Kdd0c`; スタートアップ・SaaS `4zctjnpznjo` /
> `btaUiT98cRg` / `3YsS5ojfBSQ`; 大企業 final `UdjQxAtAUUI`; SES drawn from existing repo rules
> (platforms.md, enman-taishoku.md). SIer/自社開発 rows mirror existing `platforms.md` §2–§3.

---

## 8. Real Hourly Pay & Labor Contract Evaluation (みなし残業・労働条件)

### Real Hourly Pay Formula (みなし残業 시급 환산 산식)

A higher gross annual salary (提示年収) can be deceiving if it includes a large fixed overtime allowance (みなし残業 / 固定残業代). Always calculate the **Real Hourly Pay Rate** before comparing offers or evaluating market rate:

```
Total Monthly Standard Work Hours = (365 - Annual Days Off) / 12 × Daily Regular Work Hours
Annual Base Regular Hours = Total Monthly Standard Work Hours × 12

Fixed Overtime Premium Allowance = (Base Annual Salary × Fixed Overtime Hours × 1.25) / (Annual Base Regular Hours + Fixed Overtime Hours × 1.25 × 12)
Real Base Annual Salary = Gross Annual Salary - Fixed Overtime Premium Allowance

Real Hourly Pay Rate = Real Base Annual Salary / Annual Base Regular Hours
```

#### Practical Short Formula:

```
Real Hourly Pay = (Gross Annual Salary - Annual Bonus) / [12 × (Monthly Regular Hours + Fixed Overtime Hours × 1.25)]
```

#### Worked Comparison Example:

| Parameter | Company A (No fixed overtime) | Company B (45h fixed overtime) |
|-----------|--------------------------------|--------------------------------|
| **Gross Salary** | ¥6.0M | ¥6.5M |
| **Annual Days Off** | 125 days (240 work days) | 120 days (245 work days) |
| **Daily Hours** | 8.0h (160h/mo) | 8.0h (163.3h/mo) |
| **Fixed Overtime** | 0 hours | 45 hours / month |
| **Bonus** | ¥1.0M | ¥0.5M |
| **Real Hourly Pay** | **~¥2,604 / hr** | **~¥2,283 / hr** |
| **Verdict** | **WINNER (Higher real hourly rate)** | **LOWER REAL PAY despite +¥500k gross** |

### Labor Terms Evaluation Checklist

When evaluating 労働条件通知書 / 雇用契約書, verify these 5 critical flags:

1. **みなし残業 Overages:** Are hours above the fixed threshold actually paid? Check clause for 「超過分は別途支給」.
2. **Probation Salary (試用期間中):** Does salary drop during probation? (e.g., 90% pay for first 3–6 months).
3. **Commuting & Housing Allowances (手当):** Are allowances included inside the gross salary figure, lowering base pay for bonus calculations?
4. **Non-compete Clause (競業避止義務):** Is there an overly restrictive non-compete clause post-resignation?
5. **Retirement / DC Plan (退職金・確定拠出年金):** Is corporate DC or severance pay included?
