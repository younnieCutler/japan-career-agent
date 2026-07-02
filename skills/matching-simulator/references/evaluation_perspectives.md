# Evaluation Perspectives (RA / CA / Direct)

After calculating algorithm scores, simulate the "human judgment" layer inside agencies or direct-apply companies.

## 1. Platform Scope Check

- **`target_platform` = Green or BizReach**: **No CA layer exists.** Skip "CA Perspective" entirely. Replace with "Hiring Manager Direct Evaluation".
- **`target_platform` = Recruit Agent, doda, MyNavi, Levtech**: Run full RA + CA dual analysis.

## 2. RA (Company-Side) Perspective

RA evaluates the candidate from the company's perspective. Analyze:
- Draft recommendation letter (推薦状) for presenting this candidate to the company
- Points the company might be concerned about, and counter-arguments
- Salary negotiation feasibility
- **RA Risk Signal (mandatory):** Assess refund liability for any short tenure (<1yr), employment gap, or visa-related flag:
  - **Tenure/gap risk:** If candidate has tenure <1yr or gap >3 months — "If this candidate leaves within 6 months, the agency must refund placement fee." State: `[Early-exit risk: low / medium / high — basis: X]`
  - **Visa risk:** If `visa_status` ≠ "PR" — check three factors: (a) Is visa renewal currently in progress? (b) Does the target role's work category match the candidate's visa type? (Engineer/Specialist visa is NOT valid for pure sales or administrative roles. (c) Short tenure + non-PR visa = compounded refund risk. State: `[Visa risk: low / medium / high — basis: X]`
  - When both flags are present simultaneously (short tenure + non-PR visa), output: `[⚠️ Compounded risk: placement refund probability elevated. CAs may decline to recommend.]`

```
📋 RA Recommendation
━━━━━━━━━━━━━━━━━━━━━
Recommendation reason:    [3-line summary based on skill match + SPI3 fit]
Expected company concerns: [experience gaps, skill gaps, etc.]
Counter-argument:         [reframe via Portable Skills, skill transfer potential]
Condition adjustment:     [within salary range? negotiation points]
Early-exit risk:          [low / medium / high — and why]
Visa risk:                [low / medium / high — sponsor required? category match? COE in progress?]
```

## 3. CA (Candidate-Side) Perspective

**(Agent platforms only: Recruit Agent, doda, MyNavi Agent, Levtech)**

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

## 4. Hiring Manager Direct Evaluation (Green / BizReach only)

On direct-apply platforms, there is no CA layer. The hiring manager (or HR team) evaluates the profile directly — often within 48~72 hours after the candidate applies or is scouted.

Simulate this perspective:
- **Profile appeal on platform:** Does the candidate's profile stand out in the platform's search results? (For BizReach: scout-ability; for Green: company's direct interest trigger)
- **Culture fit priority:** Direct hires weight culture fit and self-motivation more heavily than agency-routed candidates (agency already filtered for skill match).
- **Speed and responsiveness:** Direct platforms are faster; hiring managers expect candidates to respond within 1~2 business days.

```
🏫 Hiring Manager Direct Evaluation
━━━━━━━━━━━━━━━━━━━━━
Platform: [Green / BizReach]
Profile appeal score:  [X/100] — [basis: skill keywords, profile completeness, login frequency if BizReach]
Culture fit (direct):  [X/100] — [basis: well-being index alignment]
First impression:      [what the hiring manager would think within 30 seconds of seeing the profile]
Red flags:             [anything that would cause immediate pass]
```
