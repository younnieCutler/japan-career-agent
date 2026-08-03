# Evaluation Perspectives (RA / CA / Direct)

The qualitative layer that runs **after** the v3 diagnosis, not a scoring stage.

Three rules, because this section used to be where numbers crept back in:

1. **No scores.** Nothing here produces a 0–100 value, a grade, or a probability. The v3 axes
   are the quantitative output and they are not re-totalled.
2. **Evidence or nothing.** Every claim cites a confirmed fact from the diagnosis (a
   `conflict`, a `missing`, an `unknown`). What the diagnosis marked `unknown` stays a
   question here — it does not become a judgement.
3. **This is a simulated read of how a recruiter might argue**, not a decision and not a
   prediction of one.

## 1. Route Scope Check

- **Direct-apply route (Green, BizReach, Wantedly, company site)**: no CA layer exists. Skip
  "CA Perspective" and run "Hiring Manager Direct Evaluation".
- **Agent route (Recruit Agent, doda, MyNavi, Levtech)**: run RA + CA.

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
Recommendation reason:    [3 lines, each citing a `matched` required skill or experience item]
Expected company concerns: [drawn from `missing` required skills and confirmed experience gaps]
Counter-argument:         [reframe via evidenced transferable experience — no invented claims]
Condition adjustment:     [only when salary/conditions are confirmed on both sides; else "unknown"]
Early-exit risk:          [low / medium / high — and the tenure/gap fact it rests on]
Visa risk:                [low / medium / high — sponsor required? category match? COE in progress?]
```

Sensitive-attribute rule (v3 P5): age, gender, nationality and family status never enter this
read. Legal work eligibility appears only as an eligibility **fact** — stated, never scored, and
never extended into an inference about the person.

## 3. CA (Candidate-Side) Perspective

**(Agent routes only: Recruit Agent, doda, MyNavi Agent, Levtech)**

CA evaluates this company from the candidate's perspective. Analyze:
- Key pitch points when introducing this company to the candidate
- Points the candidate might be concerned about
- Which Career Value items are still `unknown`, and what would settle them

```
📋 CA Introduction
━━━━━━━━━━━━━━━━━━━━━
Key pitch:              [cite `aligned` career values and `matched` requirements]
Expected concerns:      [cite `tradeoffs`, `conflicts`, and confirmed condition gaps]
Open questions:         [the `unknown` career values — asked, not guessed]
```

No retention or satisfaction forecast is produced. Predicting post-hire satisfaction from four
preference ratings was the legacy Culture Fit score, and it is discontinued
(`legacy-v1.md`). Candidate interest, where recorded, is reported as the user's own
statement and is not evidence about the company.

## 4. Hiring Manager Direct Evaluation (direct-apply routes)

On direct-apply routes there is no CA layer. The hiring manager (or HR team) reads the profile
directly — often within 48–72 hours of an application or scout.

Simulate this perspective:
- **Profile completeness:** which required skills the profile evidences, and which it leaves
  `unknown` to a reader who has only this document.
- **Self-direction signals:** direct routes have no agency pre-filter, so the profile carries
  the whole argument by itself.
- **Speed:** direct routes move faster; a 1–2 business day response is expected.

```
🏫 Hiring Manager Direct Evaluation
━━━━━━━━━━━━━━━━━━━━━
Route: [Green / BizReach / Wantedly / company site]
Evidenced on the profile:  [required skills a reader can verify from the document alone]
Not visible to a reader:   [required skills the candidate has but the profile does not show]
First impression:          [what a reader would take away in 30 seconds — from the text, not inferred]
Red flags:                 [confirmed conflicts only; an `unknown` is a question, not a flag]
```

No appeal score, no culture-fit score, no scout-probability number. Where a real signal exists
(a scout received, a message, an interview invite) it belongs in `employer_signals` as an
observed event with its date — not converted into a likelihood.
