# Japanese Career Evidence Foundation — 2026-09-11

Status: verified research dossier. This file is not runtime context; reviewed operational behavior is
promoted through `_shared/career_knowledge.yml` and materialized into lazy Skill references.
The original Korean extraction attachment is not stored in this checkout. Its assertions were
rechecked against Japanese primary/industry sources before any behavior was promoted.

## Verified source dossier

Observed on 2026-09-11. A page's labelled update date is stored as `source_updated_at`; original
publication remains `unknown` when the source does not establish it. Confidence describes fidelity
of the source description, not universal applicability or hiring probability.

| Topic / inherited assertion | Rechecked source | Evidence and limitation | Operational decision |
|---|---|---|---|
| Documents are read in thirty seconds | [doda document survey](https://doda.jp/guide/saiyo/007.html); `doda_document_review_2025` | 2,000 mid-career hiring respondents; modal self-reported review duration for both resume types was 5 to under 10 minutes. It does not measure the first skim. | Progressive readability: support rapid comprehension and detailed review; no universal seconds claim. |
| 志望動機 is negligible / fixed 70-20-minus-alpha weighting | [doda interview survey](https://doda.jp/guide/saiyo/008.html); `doda_interview_motivation_2026` | 43.1% selected motivation as important in multiple selection and 7.3% as most important in single selection. These are not hiring coefficients. | Check `Why leave -> Why role -> Why company -> Contribution`; no fixed weighting. |
| 頑固 must be blacklisted | [Mynavi weakness guide](https://tenshoku.mynavi.jp/knowhow/mensetsu/guide/05/); `mynavi_weakness_mitigation_2025` | Guidance includes stubbornness with mitigation. Editorial guidance is not employer-wide acceptance evidence. | Probe downside, mitigation, and improvement; preserve any hard requirement conflict. |
| Three years is the minimum safe tenure | [Mynavi mid-career hiring survey](https://career-research.mynavi.jp/reserch/20240930_85660/); `mynavi_early_turnover_2024` | Respondents' average early-turnover boundary was 9.5 months or less and objectively convincing background could mitigate many negative impressions. The average is not a cutoff. | Keep tenure length, transition pattern, factual reason, and period evidence separate; no three-year rule or fixed penalty. |
| Career gap has only a 5–10% impact / study means it is not a gap | [Hataractive hiring survey](https://hataractive.jp/partner/report/16660/); `hataractive_career_gap_2024` | 334 current mid-career hiring respondents varied on whether/when gaps matter and interpreted background/activity differently. | Preserve gap existence/length separately from activity, explanation, and relevance; no universal penalty and no gap erasure. |
| Experienced-hire salary is generally current salary +10% | [doda salary interview guidance](https://doda.jp/guide/mensetsu/interview/007.html); `doda_salary_basis_guidance_2026` | Guidance describes current compensation, experience/skills, and internal salary tables as common inputs and recommends a basis for desired pay. | Surface current-compensation anchoring risk; compare stated range/grade, scope, evidence, offers, and user priorities; no fixed uplift. |
| 3C4P can be transplanted as a Japanese hiring standard | [doda self-PR guide](https://doda.jp/guide/rireki/jikopr/index.html); `doda_self_pr_structure_2026` | doda supports `状況 -> 課題・意図 -> 行動 -> 結果` and explaining intent, not the 3C4P labels or superiority over STAR. | Use 3C4P only as an optional evidence-elicitation lens; map answers back to canonical evidence; never invent a metric. |
| Salary/benefits are lower-order motives and should be avoided | [doda turnover-reason survey](https://doda.jp/guide/reason/); `doda_turnover_reasons_2026` | Compensation, hours, and evaluation concerns are prominent actual turnover reasons. Prevalence is not an interview script. | Treat compensation, WLB, evaluation, role scope, location, learning, mission, and other confirmed conditions as independent career values. |
| One-minute intro should plant hobby/novelty bait | [Mynavi self-introduction guide](https://tenshoku.mynavi.jp/knowhow/mensetsu/qa01/); `mynavi_self_intro_2026` | Guidance centers roughly one minute on name, career history, relevant strengths and transferable experience. | Use a career-relevant evidence-backed hook; hobby bait is not required and one minute is not a hard cutoff. |
| AI-assisted application text is inherently suspect / detector score is useful | [Recruit Job Hunting White Paper 2026](https://shushokumirai.recruit.co.jp/white_paper_article/20260220001/); `recruit_ai_job_hunting_2026` | 63.3% of surveyed 2026 graduates used generative AI in job hunting across several preparation tasks. Population is new graduates, not all employers/candidates. | AI text is draft material; verify and defend every claim. No deception inference, detector-evasion target, or unsupported detector-error percentage. |
| 履歴書 is facts while 職務経歴書 is story | [MHLW My Job Card guide](https://www.job-card.mhlw.go.jp/column/employed/cv-resume); `mhlw_resume_roles_2022` | 履歴書 is a concise profile-oriented surface and 職務経歴書 provides detailed work/practical capability evidence; fields can overlap. | Use profile-vs-detailed-evidence distinction and follow employer format; do not force a facts-vs-story ontology. |

Community anecdotes are retained only as research observations when useful. They do not alone
authorize active knowledge. No source in this dossier becomes a hiring probability, private recruiter
algorithm, composite score, candidate fact, or automatic rejection rule.

## Existing invariants that required no new external claim

Three inherited topics were resolved by repository evidence rather than new market statistics:

- **Company type:** `startup`, `large company`, `SIer`, or similar labels may generate questions about
  autonomy, approval layers, release cadence, manager practice, or WLB; they never establish those facts.
- **MBTI / personality labels:** user-supplied labels may provide reflection vocabulary only. They are
  never skill, professional-capability, performance, job-fit, or company-match evidence.
- **Application mix:** use the user's observed pipeline with numerator/denominator and small-sample
  caveats. There is no fixed `3:2:5` company-size mix and no causal inference from a small sample.

## Implemented behavior map

| Knowledge | Runtime owner |
|---|---|
| Progressive readability | `humanize-japanese-career`, `job-seeker-agent/references/shokumukeireki-saigensei.md` |
| 志望動機 consistency and AI draft grounding | `job-seeker-agent/references/shibo-doki.md` |
| Self-introduction and AI interview drafting | `job-seeker-agent/references/mensetsu-rounds.md` |
| 履歴書 / 職務経歴書 role distinction | `job-seeker-agent/references/shokumukeireki-saigensei.md` |
| Short tenure, gap, weakness, AI defendability | `mock-interviewer/references/japan-market-probes.md` plus `mock-interviewer/SKILL.md` |
| Salary anchoring | `tenshoku-strategy/references/nenshu-koushou.md` plus `tenshoku-strategy/SKILL.md` |
| Short tenure, gap, independent career values | `tenshoku-strategy/references/transition-risk.md` plus `tenshoku-strategy/SKILL.md` |
| Evidence-safe 3C4P | `career-tanaoroshi/references/evidence-elicitation.md` plus `career-tanaoroshi/SKILL.md` |
| MBTI/personality-label boundary | `jiko-bunseki/SKILL.md` |
| Company-type and application-mix boundaries | existing `kigyou-bunseki`, `job-seeker-agent`, and `tenshoku-strategy` invariants |

## Evaluation and promotion

The semantic evaluation artifact is
[`docs/evals/career-knowledge-2026-09-11.md`](../evals/career-knowledge-2026-09-11.md).
It records 22 scenarios and their execution boundary. Eleven source-backed knowledge items are
`active` only because the retained semantic review and deterministic promotion fingerprint agree.
Changes to a behavior, scope, source, scenario, date, or lifecycle revision invalidate the receipt.

The repository test suite additionally checks that promoted behavior is present in the relevant
lazy Skill/reference text and that every active item has an eligible promotion receipt. Legacy
numeric rules remain read-only history and cannot enter the active knowledge path.

## Architecture reference and delivery boundaries

Read against `ai-agent-book` commit `3d9e1f8f9942c64a62979339a2a5225cb7486e3b`:

- [Chapter 3](https://github.com/younnieCutler/ai-agent-book/blob/3d9e1f8f9942c64a62979339a2a5225cb7486e3b/book-en/chapter3.md): separate persistent knowledge from user memory and load relevant context progressively.
- [Chapter 6](https://github.com/younnieCutler/ai-agent-book/blob/3d9e1f8f9942c64a62979339a2a5225cb7486e3b/book-en/chapter6.md): evaluate system behavior and preserve regression cases.
- [Chapter 8](https://github.com/younnieCutler/ai-agent-book/blob/3d9e1f8f9942c64a62979339a2a5225cb7486e3b/book-en/chapter8.md): stored knowledge is not validated capability; separate candidates from production and assess changes before promotion.

The completed path is therefore:

```text
research source
  -> dated atomic claim
  -> scoped knowledge candidate
  -> semantic scenario review
  -> deterministic fingerprint/freshness gate
  -> active knowledge
  -> lazy Skill/reference runtime representation
  -> regression check
```

This does not modify the personal evidence schema because the verified behaviors can be expressed
through existing confirmed facts, Unknown preservation, pipeline observations, and stage-specific
references. A future schema expansion still requires its own evidence and evaluation.

See [knowledge maintenance](../CAREER_KNOWLEDGE.md) for querying and lifecycle checks.
