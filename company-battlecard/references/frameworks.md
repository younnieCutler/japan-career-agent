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

### SPI3 Quick Diagnostic (10 Questions)

Each question presents 2 choices (A/B). Select whichever is closer to your natural tendency.
Scoring: Sum the selections for each quadrant to measure relative strength.

**Q1. When starting a new project:**
- A) Research past cases and start with proven methods → Order +1
- B) Freely generate ideas first and try new approaches → Creation +1

**Q2. When a conflict arises in a team meeting:**
- A) Listen to both sides and try to find common ground → Harmony +1
- B) Decide which is more effective based on data → Result +1

**Q3. When you feel most rewarded at work:**
- A) When a goal is achieved and results are proven in numbers → Result +1
- B) When you feel you've grown together with teammates → Harmony +1

**Q4. When an unexpected problem occurs:**
- A) Check the manual or past response cases first → Order +1
- B) Come up with a new solution on the spot → Creation +1

**Q5. If you were to choose a working style:**
- A) An environment with clear deadlines and goals → Result +1
- B) An environment where you can freely iterate through trial and error → Creation +1

**Q6. When a colleague makes a mistake:**
- A) First consider their feelings and approach carefully → Harmony +1
- B) Propose process improvements to prevent recurrence → Order +1

**Q7. The role you're most confident in:**
- A) Generating ideas and setting direction → Creation +1
- B) Planning and managing execution → Result +1

**Q8. Situations that cause stress:**
- A) When rules change frequently and there's no consistency → Order +1
- B) When working alone with no collaboration → Harmony +1

**Q9. What you emphasize most in performance reports:**
- A) Specific numbers and achievement rates → Result +1
- B) Discoveries and learnings throughout the process → Creation +1

**Q10. Your ideal manager:**
- A) Someone who gives clear instructions and feedback → Order +1
- B) Someone who listens and respects team members → Harmony +1

### Score Interpretation

| Quadrant Score | Strength Level |
|----------------|---------------|
| 0–1 | Low |
| 2 | Medium |
| 3+ | High |

Note: This quick diagnostic does not replace the official SPI3.
It is a reference tool for identifying tendencies — use Recruit's official service for formal assessment.

---

## 2. Portable Skills: 8 Core Elements

A framework defined by Pasona Research Institute, also used in the Japanese Ministry of Health, Labour and Welfare's career transition tools.
Classifies universal competencies that remain transferable across job types and industries into 8 elements.

### 3 Domains × 8 Elements

**Task Competency** — Ability to identify and solve problems
1. **Analytical Thinking (分析力)**: Ability to grasp cause-and-effect relationships and structure complex situations
   - Evaluation points: Data-based root cause analysis, speed of identifying core issues, structuring complex situations
   - STAR interview question: "Tell me about a time you analyzed a complex problem and solved it."

2. **Planning Ability (計画力)**: Ability to design meticulous processes for achieving goals
   - Evaluation points: Milestone setting, resource allocation, risk anticipation
   - STAR interview question: "Tell me about a time you achieved a goal with limited time/resources."

3. **Drive (推進力)**: Ability to mobilize an organization toward goals and produce results
   - Evaluation points: Execution speed, overcoming obstacles, proactive action
   - STAR interview question: "Have you ever pushed forward despite opposition from others?"

4. **Reform Mindset (変革力)**: Ability to question existing approaches and drive improvements
   - Evaluation points: Problem awareness about the status quo, frequency of improvement proposals, change adaptability
   - STAR interview question: "Tell me about a time you changed an existing approach to produce better results."

**People Competency** — Ability demonstrated in relationships with others
5. **Agility (機動力)**: Speed of reacting to situational changes and moving to action
   - Evaluation points: Speed of reprioritization, judgment in uncertain situations
   - STAR interview question: "Tell me about a time you responded to a sudden change in circumstances."

6. **Negotiation (交渉力)**: Skill to coordinate among stakeholders and reach consensus
   - Evaluation points: Win-Win resolution, interest alignment, persuasion logic
   - STAR interview question: "Tell me about a time you coordinated between people with different positions."

7. **Coaching (コーチング力)**: Ability to support team members' growth and motivate them
   - Evaluation points: Supporting junior/colleague growth, feedback style, delegation ability
   - STAR interview question: "Have you helped someone else grow?"

**Self-Management Competency** — Ability to manage oneself
8. **Emotional Regulation (感情制御)**: Self-control to maintain composure under pressure
   - Evaluation points: Performance under stress, frequency of emotional reactions
   - STAR interview question: "Tell me about a time you delivered results under significant pressure."

### Portable Skills Scoring Criteria

Each element is rated 1–5 based on STAR analysis of the resume/career history.

| Score | Criteria |
|-------|----------|
| 1 | No relevant experience or very weak |
| 2 | Basic level, performs under instruction |
| 3 | Can perform independently, some level of results |
| 4 | High level, can coach others, consistent results |
| 5 | Expert level, drives organizational change, exceptional results |

---

## 3. Skill Ontology Mapping Table

A mapping table based on the skill ontology concept used by Pasona/doda.
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

A metric that quantifies Pasona Group's "Work-and-Smile" vision.
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
M_total = Σ(S_i × w_i) + α × P_fit + β × H_model
```

- S_i: Individual skill stack score (0–100)
- w_i: Skill importance weight for the role (0–1, sum = 1)
- P_fit: SPI3 latent competency fit (0–100)
- H_model: High-performer model similarity (0–100)
- α: Latent competency weight (default 0.3)
- β: High-performer similarity weight (default 0.2)

### Pasona Style (Semantic Similarity + Bonus Model)

```
M_total = cos(V_candidate, V_job) × 100 + Bonus_transferable
```

- V_candidate: Candidate skill vector (after ontology mapping)
- V_job: Job requirement skill vector
- cos(): Cosine similarity (0–1)
- Bonus_transferable: Transferable skill bonus (0–20)

### Overall Score Interpretation

| Score Range | Judgment | Agency Action |
|-------------|----------|--------------|
| 85–100 | A Match | Recommend immediately, priority report to RA |
| 70–84 | B Match | Include in recommendation list, conditions need adjustment |
| 55–69 | C Match | Consider skillset shift, propose training investment |
| 54 or below | D Match | Hold matching, explore other positions |
