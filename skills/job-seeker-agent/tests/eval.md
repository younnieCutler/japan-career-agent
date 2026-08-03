# job-seeker-agent evaluation cases

These cases verify language routing, evidence preservation, and document quality. They do not test a
pass-rate or recruiter-score prediction because the skill must not produce one.

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
