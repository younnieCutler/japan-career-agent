# Career Transition Targeting — source-backed role hypotheses

Use this reference when the user does **not** yet have a settled target role and asks what role,
career path, or キャリアチェンジ direction is realistically worth investigating next.

This workflow does not predict hiring outcomes, assign a fit score, rank occupations with hidden
weights, or write `target_role` on the user's behalf. It turns a small set of role hypotheses into
an evidence map the user can inspect and choose from.

The deterministic comparison owner is `_shared/role_transition.py`.

## Problem this workflow owns

`jiko-bunseki` can surface interests, values, environment hypotheses, and role directions for
reflection. Those are not professional-capability evidence. `matching-simulator` and ordinary
job-seeker requirement review are strongest once a specific role/JD already exists.

This workflow owns the gap between them:

```text
confirmed career evidence
        +
user-confirmed direction / constraints
        +
source-backed role hypotheses
        ↓
what transfers directly?
what is only a transfer hypothesis?
what is explicitly missing?
what is still unknown?
        ↓
user chooses which role(s) to investigate or adopt as target_role
```

## Evidence boundary

When `CAREER_VAULT` is active, start from:

```bash
career-agent context --vault "$CAREER_VAULT"
python skills/career-agent/career_agent.py evidence-pool --vault "$CAREER_VAULT"
```

Use only confirmed work events and confirmed personal context returned by those interfaces. Never
read Vault note bodies directly. A job title, course name, intention to learn, self-analysis score,
or MBTI label is not evidence that the user can perform a target-role requirement.

`recommended_role_clusters` from `jiko-bunseki` may seed hypotheses only. It never makes a role more
likely, more suitable, or `Matched`.

## Role-hypothesis discovery

Default to **3–7 role hypotheses**. Fewer is fine when the evidence is narrow. Do not create a giant
occupation catalogue.

Build hypotheses from the smallest useful combination of:

1. roles or directions the user explicitly wants to investigate;
2. tasks/capabilities visible in confirmed career evidence;
3. official occupational information such as MHLW job tag;
4. current public job postings or company career pages that show real hiring requirements.

MHLW job tag is a useful official exploration source because it exposes occupation descriptions,
task search, skill/knowledge search, ability profiles, similar occupations, and career-analysis
functions. It is **not** a hiring-probability model and does not make a role recommendation binding.

Useful official entry points:

- occupation and career exploration: `https://shigoto.mhlw.go.jp/`
- skill/knowledge search: `https://shigoto.mhlw.go.jp/User/Search/knowledge`
- task search: `https://shigoto.mhlw.go.jp/User/Search/TaskWord`
- career analysis: `https://shigoto.mhlw.go.jp/Career/Step1`
- portable-skill tool: `https://shigoto.mhlw.go.jp/VocationalAbilityDiagnosticTool/Step1`
- terms / secondary-use rules: `https://shigoto.mhlw.go.jp/user/tos`

V1 does not bundle or silently scrape the job tag downloadable dataset. If a future PR bundles a
derived dataset, record its actual downloaded filename/version/date and comply with the stated
attribution terms first.

## Source rules for role requirements

Every role hypothesis needs at least one source, and every requirement row cites one or more of those
sources.

Prefer this distinction:

```text
official_framework
    occupation/task/capability description from an official source

job_posting
    one employer's current hiring requirement; a market sample, not a universal role definition

company_public_source
    company career page or public role description
```

Do not say “QA Automation requires X in Japan” because one JD says X. Say “this sampled posting
requires X” and keep its source/date. A recurring pattern across several sources may be summarized
only with those sources attached.

A stale, contradictory, low-confidence, or otherwise unconfirmed role source cannot produce
`Matched` or `Missing`; the deterministic engine returns `Unknown` for requirements backed by it.

## Requirement-to-evidence mapping

For each role hypothesis normalize a small set of meaningful requirements. Use:

- `core`: the cited source presents it as required or central to the work;
- `preferred`: explicitly optional/preferred in the source;
- `context`: role context worth understanding but not a pass/fail requirement.

Then map candidate evidence with two separate relations.

### Direct evidence

`direct_evidence_ids` means confirmed evidence demonstrates the requirement closely enough to be
compared directly. Only direct confirmed evidence may produce `Matched`.

Example:

```text
Requirement: design test cases from product requirements
Evidence: confirmed work event showing the user designed requirement-based test cases
→ direct evidence
```

### Transfer hypothesis

`transfer_evidence_ids` means confirmed evidence may transfer, but does **not** demonstrate the
requirement itself. It requires both a rationale and a verification question.

Example:

```text
Requirement: implement automated tests
Evidence: confirmed manual test-design experience
Transfer hypothesis: test decomposition may transfer to automation design
Verification: what automated test code has the user actually implemented and maintained?
→ Requirement remains Unknown until direct evidence is confirmed
```

Never convert a transfer hypothesis to `Matched` because the rationale sounds plausible.

### Missing vs Unknown

Silence is `Unknown`.

Use `candidate_absence_confirmed: true` only after comparable candidate-side evidence is explicitly
confirmed absent. This is the only normal path to `Missing` when no direct evidence exists.

“I do not see Selenium in the resume” is not confirmed absence.

“I have never implemented automated tests” can support confirmed absence for a requirement that is
actually comparable to that statement.

## Deterministic input

Create a temporary JSON/YAML file outside the installed Skill tree:

```yaml
candidate:
  evidence:
    - id: event-test-design
      capability: test design
      state: Confirmed
      source_type: user
      source_ref: vault:event:test-design
      observed_at: 2026-08-01
      confidence: high
      provenance: user

role_candidates:
  - id: qa-automation
    label: QA Automation Engineer
    sources:
      - id: jd-1
        source_type: job_posting
        source_ref: https://example.com/job
        observed_at: 2026-09-12
        state: Confirmed
        confidence: high
        provenance: job_posting
    requirements:
      - id: automated-tests
        text: Implement and maintain automated tests
        kind: core
        source_refs: [jd-1]
        transfer_evidence_ids: [event-test-design]
        transfer_rationale: Manual test design may transfer to automation design but does not prove coding.
        verification_question: Which automated test code have you implemented and maintained?
```

Run:

```bash
python scripts/role_transition.py scenario.yml --text
```

The engine uses exactly three requirement states from the repository-wide contract:

- `Matched`
- `Missing`
- `Unknown`

and four role-level exploration states:

- `evidence_supported`: every sourced **core** requirement has direct confirmed evidence;
- `needs_validation`: at least one sourced core requirement is still `Unknown`;
- `confirmed_core_gap`: at least one sourced core requirement is explicitly `Missing`;
- `insufficient_role_evidence`: no core requirement was sourced, so V1 refuses to characterize the role.

These are **exploration states**, not employability tiers, hiring predictions, or role rankings.
Preferred requirements never override the core state.

## Output contract

Present each role independently. Do not sort by a hidden formula.

```text
Role hypothesis: [role]
Source scope: [official occupation source + sampled JDs]

Directly demonstrated
- [requirement] ← [confirmed evidence]

Confirmed gap
- [requirement] ← [explicit confirmed absence]

Unknown
- [requirement] ← [what evidence is still needed]

Transfer hypotheses
- [confirmed evidence] may transfer to [requirement]
  Why: [bounded rationale]
  Verify: [question]

Targeting state: evidence_supported | needs_validation | confirmed_core_gap | insufficient_role_evidence
```

Do not turn the counts into percentages, scores, distances, grades, `near/adjacent/stretch` bands, or
“Top 3 roles”. If the user wants prioritization, ask which explicit axis they want to optimize (for
example fastest evidence closure, interest, salary, location, or language constraints) and compare
that axis separately.

## Handoff and persistence

A role hypothesis is not the canonical `target_role`.

After the user reviews the evidence map they may:

- reject a role hypothesis;
- keep it as an exploration target;
- request more market evidence;
- explicitly choose it as their target role.

Only the last case may flow into the existing user-reviewed `CANDIDATE_PROFILE.target_role` write.
Do not silently update onboarding, Career Vault, pipeline, or candidate profile because a role received
`evidence_supported`.

After a target role is confirmed, ordinary `job-seeker-agent` JD analysis and `matching-simulator`
resume their existing responsibilities.
