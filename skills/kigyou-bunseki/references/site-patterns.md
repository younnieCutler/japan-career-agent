# Site-specific extraction patterns: retrieval evidence only

Site names and URLs are search routes, not evidence of what a private platform does internally. Page
layout, access, salary visibility, and review fields change. Record the exact URL, retrieval date,
publisher, fields actually visible, and confidence. If a page is blocked, stale, or login-gated, mark
the affected fields `Unknown`.

## Retrieval order

1. supplied job URL;
2. official company domain and recruitment page;
3. a dated public company source;
4. a review or recruitment platform as an external observation;
5. a search-result snippet only as a lead, never as confirmation.

Do not infer a platform policy from one missing field. Do not claim that a site is always accessible,
always hides salary, or always provides a rating. Do not combine review ratings, salary observations,
or page metadata into a company score or candidate outcome estimate.

## Field record

```yaml
field: salary_range | requirements | work_style | review_signal | process | other
value: "[exact retrieved text or normalized fact]"
source: "[URL]"
publisher: "[site/company]"
observed_at: "YYYY-MM-DD"
source_type: official | job_posting | company_public_source | third_party | unknown
confidence: high | medium | low | unknown
state: Confirmed | Unknown | Contradictory | Stale | Low Confidence
```

## Route notes

The following are route names only. Choose the route based on the fields that are actually available
in the current retrieval:

- official company site: identity, mission, role, team, and conditions when published;
- job-board or agency posting: role requirements and stated process when the posting is current;
- employee-review site: a dated third-party observation, never a culture fact;
- scout or professional network: a message or posting supplied by the user, never proof of an internal
  search rule;
- search engine: discovery only; open and cite the supporting source.

## Required output

```text
Retrieval: [URL, publisher, observed_at, access result]
Confirmed fields: [field -> exact source]
Unknown fields: [field -> reason]
Contradictions/staleness: [source pairs and dates]
External observations: [typed, dated, confidence-labelled signals]
Next verification: [question for company, CA, or user]
```

Add reusable, time-sensitive external facts to `_shared/career_claims.yml` and run
`python scripts/check_claim_freshness.py`. A missing field is not a negative judgment.
