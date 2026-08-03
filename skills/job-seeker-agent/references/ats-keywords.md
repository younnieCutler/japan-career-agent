# Searchable Resume Keywords (STEP 4-1b)

This module improves findability without pretending to know a platform's private retrieval rules.
It uses only the target job posting, the candidate's confirmed evidence, and an explicitly dated
source when a platform behavior is described. A keyword is never evidence by itself.

## Evidence boundary

- Extract terms from the supplied JD: required skills, role titles, domains, tools, and language or
  authorization requirements.
- Mark each term `confirmed`, `unknown`, or `missing` against the candidate record.
- Add a term to the resume only when the candidate confirms real experience, training, or a clearly
  labelled learning activity. A missing requirement stays missing.
- Do not claim that an ATS, agent database, scout service, or company uses a particular hidden weight,
  ranking, or automatic rejection rule. Platform names are route context, not an algorithm.
- If a platform-specific statement matters, record it as a dated external claim in
  `_shared/career_claims.yml` with publisher, source, confidence, and expiry.

## Keyword extraction

Build a small table from the JD:

| JD term | Requirement type | Candidate evidence | State | Resume action |
|---|---|---|---|---|
| Python | required skill | source line/date | Confirmed / Unknown / Missing | use exact spelling only if confirmed |
| role title variant | role context | target role | Observed | include when accurate |
| domain term | domain context | source line/date | Confirmed / Unknown | include when supported |

Preserve the JD's spelling on first use, then add a confirmed common variant where useful. Do not
turn a synonym into a new skill claim.

## Placement and review

Place confirmed terms where they clarify the career summary, skills inventory, or achievement bullets.
Keep each term attached to scope, action, and evidence. Review the final text for:

1. unsupported terms that must be removed;
2. confirmed terms that are missing from the document;
3. ambiguous terms that need a user question;
4. exact JD spelling and language variants;
5. no keyword stuffing or invented proficiency.

Suggested output:

```text
Keyword evidence review
- Confirmed and usable: [terms + source]
- Confirmed but absent from draft: [terms]
- Unknown: [terms + question]
- Missing: [terms; do not add]
- Verification source/date: [if an external platform claim was used]
```

This is a document-quality and evidence-traceability check. It produces no candidate outcome rate,
platform score, or hidden ranking.
