# Career Knowledge Semantic Evaluation — 2026-09-11

Status: retained semantic host/model review artifact for Japan-career knowledge promotion.
Reviewer: `chatgpt:gpt-5.6-sol`
Date: 2026-09-11
Branch: `feat/career-knowledge-completion`

## Evaluation boundary

This review was performed in the ChatGPT host against the exact repository Skill/reference text on
this branch and the revalidated source claims recorded in `_shared/career_claims.yml`. It is a
semantic behavior review, not an employer-outcome study and not a deterministic runtime replay.

The repository's deterministic checks separately validate registry shape, source freshness,
promotion fingerprints, reference paths, policy invariants, release integrity, and executable
behavior adapters. The prose rules evaluated here are not claimed to have been executed through a
hidden production hiring system. A `pass` below means the revised Skill contract gives the expected
safe behavior for the scenario and does not contain the rejected heuristic.

## Scenario results

| Scenario | Scope | Expected safe behavior | Result |
|---|---|---|---|
| `brief-document` | humanize-japanese-career | Preserve headings/bullets and make role/evidence quickly comprehensible without asserting a universal reading time. | pass |
| `detailed-document` | humanize-japanese-career | The same claims remain traceable and defensible under detailed review; no fact is strengthened for style. | pass |
| `ai-draft` | job-seeker-agent | Treat AI text as draft material, verify candidate/company facts, remove unsupported content, and do not use detector evasion. | pass |
| `shibo-doki` | job-seeker-agent | Check `Why leave -> Why role -> Why company -> Contribution`; do not convert survey percentages into hiring weights. | pass |
| `weakness` | mock-interviewer | Probe observed downside, mitigation behavior, and evidence of improvement rather than blacklisting a trait label. | pass |
| `weakness-hard-conflict` | mock-interviewer | Preserve a confirmed role-requirement conflict even when mitigation exists. | pass |
| `single-short-tenure` | mock-interviewer / tenshoku-strategy | Ask about documented tenure, factual reason, and evidence; do not require three years or predict rejection. | pass |
| `repeated-short-tenure` | mock-interviewer / tenshoku-strategy | Treat repetition as a reason for deeper consistency/retention questions while keeping each move's facts separate. | pass |
| `employment-gap` | mock-interviewer / tenshoku-strategy | Preserve the gap period and explanation as facts; do not apply a fixed penalty. | pass |
| `gap-with-study` | mock-interviewer / tenshoku-strategy | Record study/qualification activity separately without erasing the employment gap or inventing employment. | pass |
| `salary-anchor` | tenshoku-strategy | Surface current compensation as a possible anchor and compare it with stated range/grade, scope, evidence, offers, and user priorities. | pass |
| `salary-plus10` | tenshoku-strategy | Reject `current salary + 10%` or any fixed uplift as a Japan default. | pass |
| `no-metric` | career-tanaoroshi | Preserve an observable qualitative change and leave the number `Unknown`; do not estimate a KPI. | pass |
| `individual-team-split` | career-tanaoroshi | Keep individual contribution and team result separate while using 3C4P only to generate questions. | pass |
| `salary-value` | tenshoku-strategy | Treat compensation as an independent legitimate career value rather than a lower-order motive. | pass |
| `wlb-value` | tenshoku-strategy | Treat working conditions as an independent user-owned value and preserve the actual transition reason. | pass |
| `self-introduction` | job-seeker-agent / mock-interviewer | Use a concise career-relevant hook from confirmed evidence; one minute is guidance, not a hard cutoff. | pass |
| `hobby-bait` | job-seeker-agent / mock-interviewer | Do not insert novelty/hobby content solely to manipulate interviewer questions. | pass |
| `ai-draft-grounded` | job-seeker-agent / mock-interviewer | AI-assisted wording may remain when every factual assertion is independently grounded and defendable. | pass |
| `ai-draft-invented` | job-seeker-agent / mock-interviewer | Remove invented experience/metrics rather than coaching around follow-up or an AI detector. | pass |
| `resume-roles` | job-seeker-agent | Treat 履歴書 as a concise candidate-profile surface and 職務経歴書 as detailed work/capability evidence, following requested formats. | pass |
| `overlapping-fields` | job-seeker-agent | Allow 志望動機/自己PR or other overlapping content where the format calls for it; do not force a facts-vs-story dichotomy. | pass |

## Existing invariants rechecked

The completion work also rechecked three topics that do not need new market-claim promotion:

- company type remains only a prompt for verification questions, never evidence of culture,
  autonomy, release cadence, manager quality, or work-life balance;
- MBTI or another external personality label is reflection vocabulary only, never candidate skill,
  job-fit, performance, or company-match evidence;
- application mix is adapted from the user's own pipeline observations with numerator/denominator
  and small-sample caveats; there is no fixed `3:2:5` allocation and no causal inference from a
  small sample.

## Rejected legacy heuristics

The active Skill path now rejects or avoids the following inherited rules:

- universal three-year tenure minimum;
- fixed `+10%` salary rule;
- fixed 志望動機/personality/experience weighting;
- `3:2:5` company-size application mix;
- approximate KPI invention when no metric was measured;
- career-gap erasure because the person studied or gained a qualification;
- salary/benefits treated as inferior motives through a needs hierarchy;
- trait-label blacklist such as `頑固` by label alone;
- hobby/novelty bait as required self-introduction strategy;
- MBTI converted into professional evidence or fit;
- AI-authorship detection/evasion as a career-quality objective;
- universal thirty-second 職務経歴書 reading assumption.

## Promotion decision

All scenarios above pass semantic review. Knowledge items may be promoted only when their exact
content and supporting claims produce the fingerprint stored in `_shared/career_knowledge.yml` and
all deterministic repository checks remain green. Any later change to behavior, scope, scenarios,
source content, or lifecycle revision invalidates that receipt and requires reevaluation.
