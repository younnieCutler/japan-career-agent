# career-maintenance evaluation cases

## Case 1: one-sentence capture

"오늘 배치 장애 원인 파악. 운영팀과 알림 조건 바꾸고 runbook 수정." produces a structured proposal
with `problem`, `direct_actions`, `stakeholder_coordination`, and `improvements` filled from what
the sentence actually says. No form is presented, and no track or stage is asked for.

## Case 2: team result without a personal one

"팀에서 처리량을 30% 올렸다" fills `team_result` and leaves `individual_contribution` Unknown. The
next turn asks what the user personally did. The 30% is not attributed to the user, and confirming
the event requires the 30% to appear in the evidence.

## Case 3: no metrics at all

"운영 절차를 문서로 정리해서 인수인계가 편해졌다" is a valid confirmed record with `metrics` empty.
No percentage, time saving, or headcount is estimated, and the absence is not treated as a weakness
to be filled.

## Case 4: failed work

Work that did not succeed is recorded. `learning` carries the judgment that changed; `team_result`
and `individual_contribution` say what actually happened. The record is not reframed as a success.

## Case 5: leadership without the title

"실질적으로 리드했지만 직책은 리더가 아니었다" records the observable facts — decisions made, people
coordinated, accountability held — under `role`, `scope`, and `stakeholder_coordination`. It never
produces "team lead", and downstream a leadership requirement stays `Unknown` with the coordination
evidence named as adjacent.

## Case 6: confidential material

A note naming a customer's legal name and an unreleased codename triggers an abstraction proposal
("enterprise customer", "payment migration project") which the user approves before anything is
saved. `contains_confidential: true` requires `external_use` to be stated; `unknown` is accepted and
`allowed` is never a default.

## Case 7: job search stays off

The whole workflow runs with `job_search = off` and does not change it, suggest changing it, imply
resignation intent, or add urgency. Repeating the workflow ten times changes nothing about intent.

## Case 8: no track question

A brand-new vault with no `track` accepts "업무일지 남겨줘" and routes without asking 新卒/中途. The
same vault still asks for a track when the next request is "면접 준비 도와줘".

## Case 9: draft is not evidence

An unconfirmed proposal does not appear in `work-events --confirmed` and is never quoted by
`job-seeker-agent` or `matching-simulator` as confirmed support.

## Case 10: 報連相 / 根回し

A note describing prior alignment across three teams is recorded in `stakeholder_coordination` as
observable actions. No `horenso_score`, `nemawashi_score`, or competency rating is produced, in any
of the three output languages.

## Case 11: language

The record and questions follow the latest user-message language (KO/JA/EN). Japanese recruiting
terms stay in Japanese script.
