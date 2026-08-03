# Platform Routing — dated evidence, not outcome prediction

Platform routing is a channel recommendation. It is not a hiring model, a platform score, or a
claim about a private agency system. Start with the candidate's stated constraints and compare
routes on feedback, access, role coverage, and verification burden.

## Inputs to collect

- track: `shinsotsu` or `chuto`
- role type and target industry
- years and scope of experience
- desired salary and whether the number is flexible
- Japanese requirement and evidence
- visa/work authorization constraints when relevant
- direct application versus agent/scout preference
- desired feedback channel (rejection reason, coaching, or no preference)
- company-size and environment preference

Missing inputs stay `Unknown`. Do not infer them from age, nationality, company type, or a platform
name.

## Claim record

External facts must be registered in `_shared/career_claims.yml` before becoming a reusable routing
rule. Each record has this shape:

```yaml
platform:
  name: "[platform]"
  suitable_for:
    - "[role or route characteristic supported by evidence]"
  known_constraints:
    - "[access, coverage, language, or feedback limitation]"
  evidence:
    - claim_id: "[career_claims.yml id]"
      claim_type: "official|marketing_claim|survey|third_party"
      statement: "[descriptive claim, not a candidate outcome estimate]"
  evidence_date: "YYYY-MM-DD"
  source: "[URL or source reference]"
  confidence: "high|medium|low|unknown"
  needs_reverification: true
```

If there is no dated primary or directly observed source, label the item `Unknown` and do not use it
as a routing rule. A marketing claim remains `marketing_claim`; it is not evidence of candidate
success.

## Route comparison template

```text
Route: [direct | agent | scout | referral]
Observed fit: [role coverage / language / visa / feedback evidence]
Known constraints: [what this route cannot confirm]
Candidate-specific trade-off: [what the user gains and gives up]
Evidence: [source and observation date, or Unknown]
Verification question: [what to ask the platform or hiring team]
Decision: [user chooses; no automatic application action]
```

Agent routes may offer a feedback channel; direct routes may give a faster path to the company.
These are route characteristics, not universal rules. Record an actual response or feedback event
in `pipeline.yml` as `Observed` when it occurs.

## Language, work authorization, and gaps

Treat Japanese ability, work authorization, employment gaps, and short tenure as requirements or
context only when the JD, law, user, or platform documentation provides evidence. Do not convert any
of them into an arbitrary penalty. Ask the user for the missing dates or the company/CA's explicit
policy.

## Required closing

The platform section must end with the recommended route(s), the evidence behind each, the trade-off,
and the next verification question. It must not contain an outcome-rate line or an uncalibrated
number. A user can continue with any route after reviewing the trade-off.
