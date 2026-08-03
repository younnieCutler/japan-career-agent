# 求人の確認可能性: posting signals, not accusations

This supplementary section records whether a posting has enough current evidence to justify the next
verification step. It does not determine whether a job is real, rank applications, or tell the user
to stop. All signals are observations with source, date, and confidence.

## Signals to record

| Signal | Observation to collect | If absent |
|---|---|---|
| Freshness | posting date, page state, closing/redirect behavior | `Unknown` |
| Description quality | role scope, technologies, team, requirements, conditions | `Unknown` |
| Hiring context | official hiring page, dated company announcement, or recruiter message | `Unknown` |
| Reposting | exact URL/title/date comparisons | `Unknown` |
| Role plausibility | whether the stated work matches the company's public business | `Unknown` |

Do not create a threshold from posting age, repost frequency, headcount, mid-career ratio, or a
third-party rating. A platform or company type can suggest a question, not a fact. Agency contact is
recorded as an `Observed` route event, not proof of hiring intent.

## Output

```markdown
## 求人の確認可能性
| Signal | Observed fact | Source/date | Confidence | Next question |
|---|---|---|---|---|

Summary: Confirmed / Unknown / Contradictory / Stale
User decision: [the user chooses whether the available evidence is sufficient]
```

If multiple signals are missing, say `Insufficient Data`. Do not convert it into a negative judgment.
If sources disagree, mark `Contradictory` and show both sources. Do not accuse a company of a ghost
posting.

## Context questions

- Is the role still listed on the official page, and who confirms its current scope?
- Which team, manager, location, language, and authorization conditions are confirmed?
- Is this a pipeline or evergreen role, and what evidence supports that description?
- If an agent supplied the posting, what did the CA explicitly confirm and on what date?

## Evidence and freshness

For layoffs, hiring announcements, employee ratios, salary, or other market statements, cite the exact
source and date and register reusable claims in `_shared/career_claims.yml`. Expired claims are `Stale`.
No number is a default or a candidate outcome estimate.
