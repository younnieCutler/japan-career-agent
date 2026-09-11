# Japanese Career Evidence Foundation — 2026-09-11

Status: research and candidate knowledge only. This dossier is not runtime context.
The original Korean extraction attachment is not available in this checkout. Its assertions below
are inherited from the supplied research conversation, not a fresh inspection of that attachment.
Earlier conversation citations are leads, not independently verified evidence.

## Verified source dossier

Observed on 2026-09-11. The sources expose page update dates but do not establish original
publication dates, so `published_at` remains `unknown` and `source_updated_at` preserves the
labelled update date. Neither is a survey fieldwork date. A 2026-12-11 expiry is a repository
review interval, not a publisher validity guarantee.
Confidence refers to fidelity of source description, not universal applicability.

| Topic / inherited assertion | Rechecked primary source | Evidence and limitation | Candidate decision |
|---|---|---|---|
| Documents are read in thirty seconds | [doda document survey](https://doda.jp/guide/saiyo/007.html), updated 2025-12-11; `doda_document_review_2025` | 2,000 respondents involved in 2024/2025 mid-career hiring. Modal self-reported review duration for both document types: 5 to under 10 minutes. Does not measure initial skim duration. | Support both quick comprehension and detailed evidence review; no universal seconds claim. |
| 志望動機 is negligible / use fixed weighting | [doda interview survey](https://doda.jp/guide/saiyo/008.html), updated 2026-03-09; `doda_interview_motivation_2026` | 2,000 respondents. Motivation: 43.1% multiple selection, 7.3% single most-important selection. These are different questions, not hiring coefficients. | Proposed consistency questions across leaving, role, company and contribution. This chain is a design inference, not a directly tested survey result. |
| 頑固 must always be blacklisted | [Mynavi weakness guide](https://tenshoku.mynavi.jp/knowhow/mensetsu/guide/05/), updated 2025-11-21; `mynavi_weakness_mitigation_2025` | Publisher guidance explicitly includes stubbornness and accompanying mitigation. Editorial example, not an employer-wide acceptance survey. | Probe downside, mitigation and improvement; retain any confirmed role conflict. |

No community source was revalidated in this implementation pass. Community anecdotes must stay
observations and cannot alone authorize an active knowledge item. No hiring probability, weight,
composite score, or candidate fact follows from any source in this dossier.

## Remaining research and behavior backlog

These are proposed directions inherited from the earlier discussion. They are not newly verified
claims and are deliberately absent from the operational registry until source review is complete.

| Topic | Source lead / existing invariant | Next verification and scenario |
|---|---|---|
| Single short tenure / repeated short tenure | [Mynavi second-graduate analysis](https://career-research.mynavi.jp/column/20260203_107042/) | Verify population and survey wording; distinguish 11 months once from repeated moves. No universal three-year threshold or multiplier. |
| Gap and activity | Existing `Unknown` and provenance invariants | Preserve eight-month gap and certification activity separately; neither erase the gap nor invent employment or completion. |
| Salary anchoring | [Earlier community lead](https://www.reddit.com/r/JapanFinance/comments/1dn8pll/) | Recheck anecdote and obtain primary negotiation guidance; test current compensation vs role range without a default +10%. |
| Evidence-safe 3C4P | [doda self-promotion guide](https://doda.jp/guide/rireki/jikopr/index.html) | Verify question-lens mapping; distinguish individual actions, team results and source-backed quantities. No invented metric when none is available. |
| Career values / leaving | [doda leaving-reason guide](https://doda.jp/guide/mensetsu/interview/003.html) | Verify truth-preserving explanation; salary and working conditions remain independent legitimate values. |
| Self-introduction | [Mynavi introduction guide](https://tenshoku.mynavi.jp/knowhow/mensetsu/qa01/) | Career-relevant follow-up hook grounded in confirmed experience; no invented hobby bait. |
| AI draft | Existing provenance invariant | Probe whether the candidate can explain each assertion; no unsupported AI detector percentage. |
| Company type | Existing company evidence invariant | Startup/large-company labels generate questions, never establish culture facts. |
| MBTI | Existing self-analysis invariant | Reflection only; never candidate capability evidence or job-fit judgment. |
| Application mix | Existing pipeline evidence | Inspect actual route/role observations and small samples; no fixed 3:2:5 mix or causal claim. |
| Resume roles | [MHLW Job Card guide](https://www.job-card.mhlw.go.jp/column/employed/cv-resume) | Verify overlapping content before changing 履歴書 / 職務経歴書 definitions. |

Earlier conversation salary statistics and AI-use percentages are not copied into the registry:
publication year, measured period, and population must first be rechecked. A lack of verified
support here means pending research, not proof that an assertion is false.

## Architecture reference and delivery boundaries

Read against `ai-agent-book` commit `3d9e1f8f9942c64a62979339a2a5225cb7486e3b`:

- [Chapter 3](https://github.com/younnieCutler/ai-agent-book/blob/3d9e1f8f9942c64a62979339a2a5225cb7486e3b/book-en/chapter3.md): separate persistent knowledge from user memory and load relevant context progressively.
- [Chapter 6](https://github.com/younnieCutler/ai-agent-book/blob/3d9e1f8f9942c64a62979339a2a5225cb7486e3b/book-en/chapter6.md): evaluate system behavior, preserve regression cases and version prompts.
- [Chapter 8](https://github.com/younnieCutler/ai-agent-book/blob/3d9e1f8f9942c64a62979339a2a5225cb7486e3b/book-en/chapter8.md): stored knowledge is not validated capability; separate candidates from production and assess changes before promotion.

This first change implements plan stages 1–3 for the reverified subset. All three knowledge items
remain candidates. It does not claim host/model behavior evaluation has run, change skill routing,
or modify personal evidence schemas. The next change must reverify the remaining sources, update
only relevant Skill references, run the listed behavior scenarios through a real host handoff, and
retain the evaluation artifacts before promotion. In particular, the existing thirty-second text
in `humanize-japanese-career` remains a documented next-change target, not a silently fixed claim.

See [knowledge maintenance](../CAREER_KNOWLEDGE.md) for querying and promotion checks.
