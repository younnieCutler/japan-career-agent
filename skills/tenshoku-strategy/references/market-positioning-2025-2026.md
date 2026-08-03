# Market positioning — claim registry required

This reference contains a workflow, not permanent labour-market facts. Current salary, demand,
regional, platform, visa, and timing claims must be loaded from `_shared/career_claims.yml` or a
fresh source supplied during the session.

## Freshness gate

Every external claim must have a publisher, source URL, `published_at`, `observed_at`, confidence,
and `expires_on`. Run:

```bash
python scripts/check_claim_freshness.py
```

An expired claim is `Stale` and cannot be used as a strategy rule until reverified. A marketing claim
must remain labelled `marketing_claim`. Do not convert any descriptive statistic into a candidate
outcome estimate.

## Analysis template

Ask for the candidate's role, experience scope, location, Japanese ability, work authorization,
salary target, start-date constraints, and preferred route. Then report only claims with source and
date:

| Claim | Type | Source/date | Confidence | Candidate-specific use |
|---|---|---|---|---|
| [role demand or salary reference] | official / survey / marketing_claim / third_party | [URL, dates] | [level] | context only |

Keep the candidate's confirmed evidence separate from external market context. A market claim can
help formulate a negotiation question; it cannot decide the user's target or promise an outcome.

## Negotiation questions

- What written compensation range applies to this role and level?
- Which part of the package is fixed, variable, or conditional?
- What evidence supports the proposed level, and what is still Unknown?
- Which source/date should be rechecked before the offer deadline?

## Limitations

Without a dated source, state `Unknown`. Do not fill a table with remembered values, a stale article,
or an agency marketing statement. The user decides whether to apply, negotiate, accept, or decline.
