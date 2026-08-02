# First-Draft Fast Path

Use this only for a first-session writing request. It is deliberately smaller than the formal assessment and
never emits a score, `CANDIDATE_PROFILE`, or pipeline event.

## 新卒 — 学チカ / 自己PR draft

Ask only these, in one 2–3 question turn:

1. Which activity should become the draft? (club, part-time work, volunteering, research, project, etc.)
2. What was your role, and what difficult situation or goal did you address?
3. What changed, or what did you learn? Exact numbers are optional; never estimate them.

On the next response, return:

1. `Facts used` — a short list containing only the user's words.
2. `学チカ draft` — context → role → action → result/learning, with brackets for unknown evidence.
3. `自己PR draft` — one strength sentence, the same evidence, and a cautious post-join contribution link.
4. `Verify next` — at most three questions needed to make the draft defensible.

If the user names a company, state that company-specific 志望動機 still needs company research. Offer the
formal 新卒 workflow, `kigyou-bunseki`, or interview preparation only after the draft is reviewed.

## 中途 — 職務要約 / 転職軸 draft

Ask only these, in one 2–3 question turn:

1. What target role or industry are you moving toward?
2. What was your most recent role, and what did you personally own or improve?
3. Why do you want to move now? Keep the answer factual; do not invent a polished 退職理由.

On the next response, return:

1. `Facts used` — a short list containing only the user's words.
2. `職務要約 draft` — role, scope, personal contribution, and evidence gaps.
3. `転職軸 draft` — desired work, evidence from the current role, and non-negotiables only if stated.
4. `Verify next` — at most three questions needed to make the draft defensible.

For 第二新卒, keep the 中途 path and permit student-era episodes only as supplementary, clearly labelled
evidence. Do not switch to the 新卒 scoring model.

## Handoff and persistence

After the user reviews the draft, offer exactly the relevant next option:

- richer profile or writing feedback → formal `job-seeker-agent` workflow
- company/JD-specific work → `kigyou-bunseki` then `matching-simulator`
- interview answer practice → `mock-interviewer` or STEP 4-3

Do not persist by default. On an explicit save request, create the CWD-relative `career-docs/` directory if
needed, ask before overwriting, write `career-docs/{track}-draft-{name}-{YYYYMMDD}.md`, print its absolute
path, and verify it exists. Never write a draft to `data/candidate_profile.yml`.
