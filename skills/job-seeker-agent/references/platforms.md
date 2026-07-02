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

**🚨 Platform Blocking Rules (Cold Mode — apply before routing):**

Apply these hard blocks before recommending an agent platform (Recruit, doda, MyNavi, Levertech):

| Risk flag | Threshold | Block logic |
|---|---|---|
| Short tenure (pattern) | 3+ job changes by late-20s, or any single stint <1yr | CAs face refund obligation if candidate leaves. **Route to direct-apply only: Green, BizReach.** |
| Employment gap | Lev: 2~3 mo; Rec/doda: 3~6 mo; MyNavi: 6+ mo | Signals "unemployed" risk. **Route to Green (gap-tolerant) or BizReach.** |
| JLPT N3 or below, non-engineer | All agent platforms | Agents will not route non-engineer roles for N3. **Route to MyNavi Global or Korean-founded.** |
| Fragmented skills | 3+ unrelated domains | CAs struggle to pitch profile. **Route to Green before agents.** |

**Screening passage probability output (mandatory):**
At the end of the Platform Routing section, ALWAYS output a probability line:

```
📊 Screening Passage Probability Estimate
Target: [Role] @ [Platform]
Document screening: [X]% (basis: [gap count, JLPT level, tenure flags])
CA recommendation rate: [X]% (basis: [agent profiling logic — applies to agent platforms only])
Overall passage to interview: [X]%

Basis: [2–3 sentence explanation citing the specific flags that drove the estimate]
```
