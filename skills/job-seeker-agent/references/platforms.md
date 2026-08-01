# Platform Strategy & Routing Rules

This document details the strategies for specific company types, Japanese language levels, and platform routing logic.

## 1. Japanese Level Targeting Strategy

Don't simply mark language level as "unmet" — provide level-appropriate strategy.

| JLPT | Role | Realistic targets | Platform routing |
|------|------|------------------|-----------------|
| N1 | Sales / Back-office / SIer | Any company type; keigo proficiency expected | Recruit Agent, doda, MyNavi Agent all viable |
| N2 | IT Engineer | Self-developed, SIer, foreign-capital IT | Levertech (N2 floor), doda IT, Recruit Agent IT, Green |
| N2 | Non-engineer | Korean subsidiaries, foreign-friendly SME | Must confirm N1 study plan + target date |
| N3 | IT Engineer only | Foreign-capital startups(English OK), Korean IT | Green (direct-apply) viable; agent platforms limited |
| N3 | Non-engineer | Korean companies, Korean subsidiaries | Pivot to Korean company track; Japan agents will not route |
| N4 | Any | Korean companies, IT-specialized Korean-hire | Position as Korean native; MyNavi Global only |

## 2. Self-Developed (自社開発) Resume Strategy

Self-developed companies prioritize **ownership and self-direction**.
- **Key appeal points:** "Identifying a problem and acting", Tech curiosity (GitHub/Qiita), Enjoyment of change.
- **Phrasing approach:** Instead of "Handled tasks", write "Identified manual errors, wrote SQL query, cut review time."
- **Red-flag reframes:** SES dispatch → "flexibility adapting to environments". Operations → "stable system upkeep + frontline problem awareness".

## 3. SIer (System Integrator) Resume Strategy

SIer companies prioritize **reliability, process adherence, and long-term commitment**.
- **Required appeal items:**
  1. 報連相 (Ho-Ren-So): Prove with an episode (e.g., "Reported inquiries within 4 hours, reducing complaints").
  2. Long-term vision: "I want to grow long-term as an IT professional in Japan."
  3. Teamwork / quality management / accuracy episode.
  4. IT certification plan (e.g., ITパスポート acquisition plan).

## 4. Platform Routing & Blocking Rules

Based on candidate profile, recommend the best-fit platform(s):

| Candidate profile | Primary platform | Why |
|-------------------|-----------------|-----|
| Age 20s–early 30s, first job change | MyNavi Agent | Highest screening pass rate (~50%); 70% users under 34 |
| IT engineer, wants self-developed | Levertech | Engineer-only specialist; 96% target-company placements |
| Age 20s–30s, broad search, needs volume | Recruit Agent | Largest job inventory in Japan; reproducibility evaluation |
| Age 20s–30s, agency + job board hybrid | doda | Strongest Portable Skills coaching; CA curates carefully |
| Age 35+, income 600万+, management | BizReach | Scout-based; 7.5M tier for premium access |
| Non-traditional, startup-curious, low JLPT | Green | No registration screening; startup culture tolerance |
| Foreign national, needs visa support | MyNavi Global | Foreign-specialist; visa/COE documentation support |
| Startup culture, any JLPT, wants culture-first | Wantedly | No registration screening; culture/mission matching; no salary shown upfront — confirm expectations |
| Foreign national in Japan, IT mid-career, needs sponsor | VISIONARY CAREER | Specialist in foreign national placement; navigates visa categories and COE; N2+ required |

**⚠️ Platform Risk Flags (Cold Mode — surface before routing):**

These flags lower the odds an agent platform routes the candidate well. They are **warnings, not blocks** —
never remove an agent platform from the option list because of them.

| Risk flag | Threshold | What it means |
|---|---|---|
| Short tenure (pattern) | 3+ job changes by late-20s, or any single stint <1yr | CAs face a refund obligation if the candidate leaves early, so they pitch such profiles cautiously. Direct-apply routes (Green, BizReach) avoid the CA filter |
| Employment gap | Lev: 2~3 mo; Rec/doda: 3~6 mo; MyNavi: 6+ mo | Signals "unemployed" risk to a CA. Green is gap-tolerant |
| JLPT N3 or below, non-engineer | All agent platforms | Agents rarely route non-engineer roles at N3. MyNavi Global or Korean-founded companies are the realistic path |
| Fragmented skills | 3+ unrelated domains | CAs struggle to pitch the profile in one sentence. Green accepts it directly |

**Feedback-loss disclosure (mandatory whenever a direct-apply route is recommended):**

Direct application removes the CA filter, and it removes the rejection reason with it. Companies send a
定型お祈りメール; only an agent or scout relays what the company actually said. A rejection with no reason
teaches nothing, and the highest-priority company is exactly the one whose rejection is most worth
understanding.

State this whenever the routing above points to Green or BizReach:

```
⚠️ 直接応募のトレードオフ
  Agent route:  CA filter may weaken the pitch — but a rejection comes with the company's real reason
  Direct route: no CA filter — but a rejection comes with no reason at all (定型お祈りメール)

  This company is [high/low] priority for you. The higher the priority, the more the
  rejection reason is worth.
```

If the user takes an agent route despite a risk flag, or a direct route despite this warning, record
`gate_override: true` on the pipeline entry. Whether these flags were right for this user is then
measurable by `career-agent calibrate` instead of assumed.

**Screening passage probability output (mandatory):**
At the end of the Platform Routing section, ALWAYS output a probability line, **immediately followed by
the disclaimer line — the STEP is not complete without it**:

```
📊 Screening Passage Probability Estimate
Target: [Role] @ [Platform]
Document screening: [X]% (basis: [gap count, JLPT level, tenure flags])
CA recommendation rate: [X]% (basis: [agent profiling logic — applies to agent platforms only])
Overall passage to interview: [X]%

⚠️ LLM estimate, not a statistic (±10pt or more). Agency routing also depends on placement fee
   margins, CA quotas, and how many openings are left that week — none of which are observable here.
   Use this to decide where to spend preparation time, never as a reason to prepare less.

Basis: [2–3 sentence explanation citing the specific flags that drove the estimate]
```
