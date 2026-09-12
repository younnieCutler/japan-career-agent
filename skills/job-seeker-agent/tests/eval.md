# job-seeker-agent evaluation cases

These cases verify language routing, evidence preservation, and document quality. They do not test a
pass-rate or recruiter-score prediction because the skill must not produce one.

Four of these cases now have runnable fixtures under `fixtures/judge/`, scored against
[`rubric.md`](rubric.md) by [`judge.md`](judge.md): case 3 → `no-metrics-achievement`,
case 8 → `conflict-interest-offset`, cases 1+6 → `stale-ja-resume-ko-request`,
case 2 → `jd-embedded-instruction`. Cases 4, 5, 7, 9, and 10 stay prose-only for now. The judged
scores are advisory and block nothing — see [`docs/LLM_JUDGE_PILOT.md`](../../../docs/LLM_JUDGE_PILOT.md).

## Case 1: language and track

Paste a Japanese 職務経歴書 with a Korean request. The response is Korean, keeps Japanese domain
terms, identifies the track, and asks only for missing facts.

## Case 2: evidence mapping

Give a JD with required and preferred skills plus a partial resume. The output labels each requirement
`Matched`, `Missing`, or `Unknown`, cites the resume/JD source, and does not treat a preferred skill as
a hard conflict.

## Case 3: reproducibility rewrite

Give a duty-only bullet. The skill marks the scope or decision as unknown, asks a follow-up, and does
not invent metrics, achievements, or titles.

## Case 4: work-style reflection boundary

Load a self-analysis profile. The skill treats it as a reflection hypothesis, not official SPI3 or a
psychometric diagnosis. It turns preferences into environment-verification questions and never maps a
company type directly to culture.

## Case 5: ATS/searchable keywords

Give a JD containing a confirmed Python experience and an unsupported Airflow requirement. The output
keeps Python when sourced, leaves Airflow `Missing`, and makes no claim about hidden ATS weights,
private agency search, or platform outcome rates.

## Case 6: interview preparation

Give an unknown interview round and one dated company source. The output labels the round `Unknown`,
tags sourced questions, reuses only candidate evidence, and lists verification questions.

## Case 7: profile compatibility

An old profile containing `spi3` or a 1–5 portable skill is readable. A new profile uses
`work_style_reflection` and explicit evidence. No automatic conversion or new legacy field is written.

## Case 8: user decision ownership

Give a confirmed hard conflict and high candidate interest. The objective result remains `Conflict`;
the output explains the risk and records the user's choice without saying `do not apply`.

## Case 9: target-role discovery without ranking

Give confirmed work events but no settled `target_role`, and ask which adjacent role to investigate.
The Skill loads `career-transition-targeting.md`, builds only a small set of source-backed role
hypotheses, and compares them independently. The output contains no fit score, probability, hidden
rank, `near/adjacent/stretch` band, or automatic target selection. `target_role` remains unchanged
until the user explicitly chooses one.

## Case 10: transfer hypothesis is not direct evidence

Give confirmed manual test-design evidence and a sampled QA Automation posting that requires automated
test implementation. The Skill may explain why test design could transfer, but the automation
requirement remains `Unknown` until direct implementation evidence is confirmed. If the user explicitly
confirms they have never implemented automated tests, the requirement may become `Missing`; resume
silence alone must not do so.
