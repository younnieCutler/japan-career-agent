# company-battlecard evaluation cases

## Case 1: independent comparison

Compare two `COMPANY_PROFILE` records with a candidate profile. Render the nine required axes:
Decision Status, hard eligibility, required skills/experience, career values, working conditions,
practical constraints, role scope/growth evidence, candidate interest, and missing information.
There is no total, winner score, or hidden weighting.

## Case 2: missing evidence

Hide salary or manager information for one company. The row is `Unknown` or `Insufficient Data`, with
the exact missing item and a verification question. No estimate is inserted.

## Case 3: company-type boundary

Provide only a company type. The output must not create a culture advantage. It may state that the type
suggests a question to verify, not an observed fact.

## Case 4: conflict and interest independence

Provide a confirmed candidate dealbreaker, conflicting company evidence, and interest level 5. The
objective result remains `Conflict`; changing interest to 1 produces the same objective axes.

## Case 5: user-owned verdict

When one company has a trade-off and the other has unknowns, explain both options and the next evidence
to collect. Do not crown a winner or instruct the user to apply or not apply.
