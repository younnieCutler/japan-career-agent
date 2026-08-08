# Four-skill evolution decisions

## Run identity and decision rule

- Starting `main` SHA: `72a87e8760ab1630aa5f3130596a099ea6cec911`.
- Isolated branch: `agent/four-skill-evolution-8x`.
- Decision unit: the smallest owning layer that can correct an observed failure.
- Promotion rule: keep only a treatment that passes its frozen evaluator and the canonical clean-tree
  check. Do not average candidates into a score and do not compensate for a failed safety boundary
  with another strength.
- Learning rule: `_shared/agent_context/learning.md:3-13` requires repeated real failures to be
  promoted to the smallest owning layer. The candidate skill test directories contain no
  `tests/mistakes.md`, so this review found no logged repeated contrary failure to promote.

## Candidate A — `mock-interviewer`: DEFER

| Field | Evidence-based decision |
|---|---|
| Repo evidence | `skills/mock-interviewer/SKILL.md:79-102` already defines the coverage ledger and largest-unresolved-risk priority; `:104-113` defines clarification and counterexample probes; `:120-159` defines question budget, stop, `Not assessable`, readiness, and user exit. `skills/mock-interviewer/tests/eval.md:19-68` covers breadth, clarification, stop, and readiness. |
| Owning layer | Future treatment belongs to the `mock-interviewer` subject behavior and its evaluator, not Career Agent routing. |
| Frozen evaluator status | Existing scenarios are deterministic contract replays (`_shared/behavior_eval_schema.yml:79-210`). `_shared/behavior_replay.py:1-5,43-138` explicitly replays a policy oracle and does not simulate an LLM; `scripts/run_behavior_evals.py:320-338` registers that replay, not a direct skill/LLM subject. This cannot attribute a next-question improvement to actual subject behavior. |
| User-visible benefit | A valid future treatment could make the next interview question more reliably target the highest-value unresolved axis. Much of that intended behavior is already specified. |
| Complexity and risk | Editing the skill against a policy replay risks making prose satisfy its own oracle without demonstrating an actual next-question improvement. A new evaluator without a stable direct subject would add misleading infrastructure. |
| Attempted experiments | Evidence audit only. No subject or instruction treatment was run because the attribution prerequisite was absent. `skills/mock-interviewer/tests/test_contract.py:28-48` remains a prose-contract guard, not direct subject evidence. |
| Final state | **DEFER.** Prerequisite: a stable direct-subject next-question evaluator with fixed inputs and attributable outputs. Revisit only after that contract exists. |

The existing coverage ledger, priority rule, clarification probes, stop rule, and `Not assessable`
state mean the proposed product behavior is not missing at the instruction level. With no repeated
failure in a mistakes log and no direct-subject evaluator, another instruction edit is not justified.

## Candidate B — `kigyou-bunseki`: DEFER

| Field | Evidence-based decision |
|---|---|
| Repo evidence | `skills/kigyou-bunseki/SKILL.md:23-31` says blocked/stale sources become `Unknown` and facts/missing fields are shown before save; `:33-57` defines evidence state and decision-relevant fields; `:69-93` requires unknown/stale output and candidate-facing implications. `skills/kigyou-bunseki/tests/eval.md:3-26` describes five cases only in prose. |
| Owning layer | After the prerequisite, the owner is the `kigyou-bunseki` skill plus its evaluator. It is not Career Agent stage routing. |
| Frozen evaluator status | The gap is decision-relevant evidence and stop-state behavior, but no registered callable adapter executes this skill. The complete adapter registry at `scripts/run_behavior_evals.py:332-339` contains only mock-interviewer, matching, and Career Agent adapters. Prose cases cannot attribute a pass or failure to a treatment. |
| User-visible benefit | A valid future treatment could make the skill stop cleanly with explicit `Unknown` evidence and the exact verification question when a decision-relevant source is absent or stale. |
| Complexity and risk | Company research includes source retrieval and evidence-state boundaries. Without a callable subject/evaluator seam, an instruction edit and a prose judgment could agree while actual behavior remains unchanged. |
| Attempted experiments | Evidence and adapter audit only; no treatment was attempted because the evaluator could not execute or attribute the subject. |
| Final state | **DEFER.** The gap is real, but promotion waits for a registered callable adapter and frozen direct evaluator. The owning team is the kigyou skill/evaluator after that prerequisite. |

## Candidate C — `company-battlecard`: CUT

| Field | Evidence-based decision |
|---|---|
| Repo evidence | `skills/company-battlecard/SKILL.md:32-46` already separates `Decision Status`, conflict, interest, and missing information; `:62-74` preserves conflicts and turns missing evidence into verification questions/actions; `:96-105` already has conflicts/missing information and a user-owned next step; `:108-109` forbids a winner and preserves `Unknown`. `skills/company-battlecard/tests/eval.md:10-28` covers missing evidence, conflict/interest independence, next evidence, and no winner. |
| Owning layer | Any genuine omission would belong to `company-battlecard/SKILL.md`; no Career Agent or shared runtime change is indicated. |
| Frozen evaluator status | The existing evaluator is prose, but no experiment is needed to establish duplication: the proposed extra section is already present in the current output contract and eval cases. |
| User-visible benefit | An extra conflict/action section offers no distinct benefit because the current template already exposes both. |
| Complexity and risk | Duplicating the same conflict, `Unknown`, question, and action content creates two places that can drift or contradict each other. |
| Attempted experiments | Static contract comparison only. No code or skill treatment was attempted. The skill directory also has no mistakes log showing a repeated contrary output. |
| Final state | **CUT.** Current behavior already preserves conflict plus interest independence, maps `Unknown` to questions/actions, and names no winner. |

## Candidate D — Career Agent context routing: ACCEPT narrowly

| Field | Evidence-based decision |
|---|---|
| Repo evidence | At the starting SHA, `skills/career-agent/routing.py:94-113` exposed only `skill_context(skills_root, stage)` and selected `SKILL_BY_STAGE`; `skills/career-agent/models.py:182-211` maps one broad skill/reference per stage. The stage router at `skills/career-agent/routing.py:85-107` cannot distinguish two topics inside one stage. This is the exact root cause. |
| Owning layer | `skills/career-agent/references/routing.yml`, `skills/career-agent/routing.py`, and the single call site in `skills/career-agent/proposals.py`. The owner is not `skills/tenshoku-strategy/SKILL.md`; all ten target references already existed. |
| Frozen evaluator status | Executable and frozen before production edits in `skills/career-agent/test_routing.py:65-143` and `skills/career-agent/test_career_agent.py:282-297`. It directly calls routing and the CLI persistence path. |
| User-visible benefit | A specific chuto request now loads one relevant execution reference instead of a broad stage default, without changing lifecycle stage or `flow_phase`. |
| Complexity and risk | One ordered phrase list can miss unlisted synonyms or match a phrase used in negation. Terms are deliberately specific, routing is chuto-only, and a miss falls back to the existing stage context. Selected paths are constrained beneath the skill directory. |
| Attempted experiments | Numbered experiment **D-1** only; details below. No target skill, schema, dependency, or shared evaluator change. |
| Final state | **ACCEPT narrowly; KEEP.** The behavior evaluator is green and the clean committed tree passed all 56 canonical checks. |

## Shared evaluator harness: CUT

| Field | Evidence-based decision |
|---|---|
| Repo evidence | D is deterministic and already fits `unittest`: message, track, stage, selected skill, reference existence, and persisted equality are directly observable in `skills/career-agent/test_routing.py:65-143` and `test_career_agent.py:282-297`. `scripts/run_all_checks.py` already includes Career Agent and routing tests in the canonical matrix. |
| Owning layer | No new owner is needed. If future subjective subjects stabilize, the shared behavior-eval registry in `scripts/run_behavior_evals.py:332-339` would own common execution. |
| Frozen evaluator status | Existing deterministic tests are sufficient for D-1. A/B lack direct subjective subject/evaluator contracts, so a shared harness would not solve attribution. |
| User-visible benefit | None directly; this would be test infrastructure only. |
| Complexity and risk | A new abstraction would duplicate `unittest` for D while giving A/B a shared shell without stable subject semantics. |
| Attempted experiments | No harness implementation was attempted. D-1 ran in the existing focused tests and canonical runner. |
| Final state | **CUT.** Reconsider only after at least two stable subjective subject/evaluator contracts exist and share an actual execution need. |

## D-1 — ordered chuto message context

### Hypothesis

An ordered, message-specific chuto route can select exactly one existing `tenshoku-strategy`
reference for a single-topic request while preserving the two-argument stage fallback and avoiding
capture of generic interview, research, resume, and shinsotsu messages.

### Six-case baseline observed with the original two-argument path

The old stage-only selector was replayed with `stage_for(message, "chuto")` and
`skill_context(skills_root, stage)`. Five of six mandatory cases selected the wrong reference.

| Message | Observed baseline stage and reference | Expected | Baseline |
|---|---|---|---|
| 年収交渉をしたいが、まだオファーはありません | `自己分析・転職軸` → `jiko-bunseki/references/questions.md` | `tenshoku-strategy/references/nenshu-koushou.md` | Wrong |
| 書面のオファーと口頭説明が矛盾しています | `自己分析・転職軸` → `jiko-bunseki/references/questions.md` | `tenshoku-strategy/references/roudou-joken-review.md` | Wrong |
| 面接のお礼を送りたいが、話題のメモがありません | `面接` → `job-seeker-agent/references/mensetsu-rounds.md` | `tenshoku-strategy/references/mensetsu-follow.md` | Wrong |
| 退職したいが就業規則の予告期間は不明です | `退職・入社準備` → `tenshoku-strategy/references/nyusha-teichaku.md` | `tenshoku-strategy/references/enman-taishoku.md` | Wrong |
| 市場年収を知りたいが情報が古いです | `自己分析・転職軸` → `jiko-bunseki/references/questions.md` | `tenshoku-strategy/references/market-positioning-2025-2026.md` | Wrong |
| 入社手続きだけ確認したいです | `退職・入社準備` → `tenshoku-strategy/references/nyusha-teichaku.md` | same | Correct |

Measured result is a case count, not a composite quality score: mandatory routing improved from
1/6 correct (5/6 wrong) to 6/6 correct. The sibling table also routes the remaining four references,
and retention coverage checks four precedence collisions, the old two-argument fallback, unmatched
fallback, exact-one reference, generic interview/research/resume behavior, configuration shape, and
shinsotsu non-capture.

### Frozen evaluator and RED

Tests were written before production edits. The first focused run was:

```text
Ran 49 tests in 15.764s
FAILED (failures=5, errors=15, skipped=1)
```

The 15 subtest errors were the expected `TypeError: skill_context() takes 2 positional arguments but
4 were given`. Four configuration-validation subtests failed because malformed `message_context`
was not rejected. The CLI integration failure returned `references/questions.md` instead of
`references/roudou-joken-review.md`.

### Treatment

1. `skills/career-agent/references/routing.yml:10-52`: add one ordered list covering all ten existing
   tenshoku references with narrow JA/KO/EN phrases and required precedence.
2. `skills/career-agent/routing.py:24-47`: validate list shape and the required `skill`, `reference`,
   and `terms` fields.
3. `skills/career-agent/routing.py:110-155`: add optional `message` and `track`, reuse
   `term_present`, route only chuto messages, require the chosen reference beneath the chosen skill,
   and retain the old stage fallback.
4. `skills/career-agent/proposals.py:102-134`: compute the selected dict once and reuse it in both the
   response and persisted trajectory.
5. `skills/career-agent/test_routing.py:65-143` and `test_career_agent.py:282-297`: retain the frozen
   evaluator and response/persistence integration assertion.

The first treatment run exposed one missing collision phrase (`書面の労働条件`) in D-1; adding that
specific term made the same frozen evaluator green. This was a minimal GREEN correction within D-1,
not a new experiment or a widened hypothesis.

### GREEN, stop rule, and current KEEP gate

```text
Ran 49 tests in 15.927s
OK (skipped=1)
```

The skip is the existing Windows-only test. D-1 therefore meets its focused behavior gate. Attempts
D-2 through D-8 were intentionally not attempted: the stop rule says to stop after the first numbered
treatment that passes the frozen behavior evaluator, rather than add more aliases, abstractions,
schema, dependencies, target-skill edits, or a shared harness. Final KEEP was confirmed by the root
review and the clean-HEAD canonical run; the release-integrity check intentionally rejects any dirty
worktree, so that gate could only close after the commit.

## Regressions and unresolved weaknesses

- Lifecycle `stage` and `flow_phase` are intentionally unchanged; this treatment selects context
  only. It does not improve stage classification for phrases such as katakana `オファー`.
- The ordered lexicon is intentionally narrow. An unlisted synonym falls back to stage context; it
  does not guess. JA mandatory cases are frozen, while the added KO/EN topic phrases do not yet have
  an equally exhaustive table.
- Phrase presence does not understand negation. For example, a sentence containing a routed phrase
  to say it is unnecessary can still select that reference. The consequence is limited to context
  selection, not a lifecycle transition or user action.
- A selected configured reference fails closed if it escapes or is missing from its skill directory.
- A/B still lack attributable direct-subject evaluators. C remains intentionally unchanged.
- The stable marketplace tag/ref was not changed; source version metadata and SBOM moved to 1.18.1
  for the behavior change.

## Verification status

- Baseline supplied for starting `main` (`72a87e8`): all 56 canonical repository checks passed.
- Changed tree focused command: 49 tests passed, with 1 existing Windows-only skip.
- Changed dirty tree canonical command: ruff through SBOM tests passed. The runner then stopped only
  at `scripts/test_release_integrity.py` with
  `ReleaseBuildError: release requires a clean working tree`; that test calls
  `git status --porcelain` and is structurally unavailable before commit. No bypass or temporary
  commit was used.
- First clean-HEAD run at the starting SHA: `All 56 repository checks passed`.
- Rebase onto the current `main` (`08b7f41`, after PRs #52 and #54): eight conflicts, all in version
  metadata except `skills/career-agent/proposals.py`. `routing.py`, `references/routing.yml`, and
  `test_routing.py` merged without conflict. The proposals conflict was textual only — both sides
  edited the same return statement — and was resolved by keeping the onboarding result structure
  from `main` and reading the routed context from `selected_skill`.
- Final canonical run on the rebased clean HEAD: `All 57 repository checks passed` (the count grew
  with `main`), and the focused command reports 56 tests with the same single Windows-only skip.
  D-1 is therefore **KEEP**.

## Branch, commit, and PR state

- Branch: `agent/four-skill-evolution-8x`, rebased onto `main` at `08b7f41`.
- Starting HEAD: `72a87e8760ab1630aa5f3130596a099ea6cec911`.
- Implementation commit: `0171bdd`, root-reviewed and root-authored.
- Push and PR: pushed to `origin`; PR opened against `main`.
- Merge: never automatic; no merge was attempted.

## Completed work

- D-1 implementation and frozen regression coverage.
- Response/persisted context equality check.
- Candidate and harness decisions with owning layers and evaluator prerequisites.
- Version 1.18.1 metadata, changelog, current-release docs, and regenerated deterministic SBOM.
- Focused GREEN and dirty-tree canonical verification up to the clean-tree release gate.
- Root review, commit `0171bdd`, rebase onto current `main`, clean-HEAD 57/57 canonical run, and the
  PR against `main`.

## Recommended remaining work

1. Human review and merge of the PR. Merge is never automatic.
2. Publish `v1.18.1` through the release workflow, then update the stable marketplace ref in a
   separate change; the ref still points at `v1.17.2`.
3. Separately, create a stable direct-subject evaluator before reconsidering A, and a registered
   callable adapter before reconsidering B. Do not revive C without a repeated contrary failure.
