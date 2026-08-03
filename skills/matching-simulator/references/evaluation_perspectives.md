# Qualitative evidence perspectives

This layer runs after the deterministic v3 diagnosis. It is a structured conversation aid, not a
score, grade, platform model, or hiring decision.

## Route context

Record the route the user actually used (`direct`, `agent`, `scout`, `referral`, or `unknown`). A
route may change which feedback was observed, but it does not change the candidate/JD evidence.
Do not infer a private agency rule from a rejection or a recruiter silence.

## Company-side and candidate-side questions

For an agent or scout conversation, ask what the recruiter explicitly confirmed about the role,
requirements, language, authorization, and process. For a direct route, record the company's actual
reply or the absence of a reply as `Observed`; absence is not negative evidence.

For any short tenure, work authorization, or employment-gap concern, state the documented fact and
the question to verify. Do not describe a refund arrangement or routing practice unless a source
directly supports it.

## Values and conditions

Candidate values are compared with company evidence item by item:

- `Aligned`: the user's stated condition and company evidence agree;
- `Tradeoff`: the user can accept the stated cost, or the evidence points both ways;
- `Conflict`: both sides are confirmed and a must-have or avoid condition disagrees;
- `Unknown`: the company or candidate side is missing.

No retention, satisfaction, or success conclusion is derived from preference ratings. A company type
is only a prompt for a verification question.

## Report shape

End with Decision Status, confirmed conflicts, three highest-value unknowns, and questions the user
can ask. Record real employer responses as dated `Observed` signals. Never use this layer to produce
a number that looks like an outcome forecast.
