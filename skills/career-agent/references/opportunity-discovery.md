# Opportunity discovery — 求人探索・候補整理

This reference owns the discovery step of the chuto lifecycle. It does not add a new Skill: the deterministic `career-agent discover` capability remains the execution owner.

## Boundary

Discovery answers **what real opportunities should enter review**, not whether the user should apply or whether they will be hired.

- Preserve the original posting URL and observation date.
- Do not invent a posting, company opening, salary, requirement, or deadline.
- A discovered posting is a candidate for review, not a recommendation or match result.
- Do not submit an application or contact an employer.
- Do not rank postings by an undisclosed fit score.

## Workflow

1. Confirm the user's target role or search query. If the target is not settled, return to target-role exploration instead of silently choosing one.
2. Discover or ingest current public postings through the existing `career-agent discover` path.
3. Deduplicate by canonical public URL and keep source provenance.
4. Remove postings that are unavailable, malformed, or outside the user's explicit search constraint; keep uncertain cases as `Unknown` rather than guessing.
5. Present a small shortlist candidate set with only observable fields: company, role, location/work mode when stated, source/date, and notable requirements.
6. Let the user choose which opportunity proceeds to company/JD analysis. Selection for deeper review is a user action; it is not a hiring prediction.

## Handoff

A chosen posting moves to `企業研究・JD分析`:

- `kigyou-bunseki` owns source-labelled company/JD research;
- `matching-simulator` owns candidate-vs-requirement diagnosis when the user asks whether their confirmed evidence addresses that posting.

Application tracking does not wait for the lifecycle to finish. Once the user actually starts an application, `tenshoku-strategy` tracking runs as a cross-cutting selection loop through closure.