# career-tanaoroshi — recorded mistakes

Failures observed while building this workflow, kept so the same reasoning is not repeated.

## Asking for companies first

An early draft opened with "어느 회사에서 일하셨나요?". For a new graduate that question has no
answer, and answering it honestly ("없어요") reads as having no experience at all — when the
university, the part-time job and the club are exactly the evidence base. Context discovery now
offers the kinds before asking, and `--kind` has no default so the shape is never assumed.

## Treating every experience as a project

The first field set was borrowed from the project record, which made "매달 리포트를 만들었다" hard
to enter and easy to skip. Operations, support and research work is not less real for having no
project boundary. `experience_kind` lists `project` as one entry among sixteen for that reason, and
`experience_ref` gives a non-project experience a name without inventing a project to hold it.

## Storing non-work experience as a work event

A seminar and a release ask the same questions — role, problem, what you did, what the team got,
what number backs it — so reusing the work-event payload was right. Reusing the work-event *type*
was not: it would have said the user was employed at their university, and `readiness`,
`weekly-review` and `career-maintenance` are all scoped to work and would have returned coursework
as work history. The payload is shared; the type is not.

## Letting an imported document confirm facts

An early version wrote contexts straight from a parsed 職務経歴書, on the grounds that the user had
written it themselves. A document says what was true when it was written, by someone optimising for
a different application, and the ledger cannot tell an imported guess from a confirmed fact
afterwards. Extraction produces candidates; only the user's approval produces canonical evidence.

## Reporting progress as a percentage

"棚卸し 60% 완료" was tried as a resume aid. It is the composite this repository refuses everywhere
else, and it hides which part is missing — the only thing the number is asked about. The view
reports confirmed and missing separately and names one next step.
