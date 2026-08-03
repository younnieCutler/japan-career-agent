# tenshoku-strategy evaluation cases

## Case 1: fixed entry and routing

Korean, Japanese, and English requests use the latest-message language and reach the same stage/module.
Only the response language changes.

## Case 2: offer and condition review

An offer is reviewed by facts, unknowns, and user priorities. Salary examples are cited and dated when
external. No offer-rate or negotiation-success estimate is produced.

## Case 3: interview follow-up

The draft cites the actual interview point supplied by the user, distinguishes a direct route from an
agent route, and does not invent a question or promise a response.

## Case 4: application tracking

The tracker records observed states, dates, feedback, missing information, preparation actions, and
user overrides. It does not transform Decision Status into a probability, tier, rank, or forecast.

## Case 5: market claims

Time-sensitive market guidance is read from `_shared/career_claims.yml`; stale claims produce a warning.
Missing claims are `Unknown`, not filled with a remembered statistic.

## Case 6: user ownership

A warning or conflict is explained with its evidence and next verification step. The skill does not
submit, send, or decide on the user's behalf.
