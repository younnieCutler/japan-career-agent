# Routing Autoresearch — Phase 0–2 implementation record

**Date:** 2026-08-08
**Source:** Routing Autoresearch PRD (approved, no open questions)
**Benchmark:** `routing-eval-v1`
**Baseline commit:** `4b75b4a` (the harness commit; routing behaviour unchanged from `f69f9eb`)

## What shipped

| Path | Role |
| --- | --- |
| `scripts/routing_eval.py` | Frozen evaluator: fixture schema, gate classification, anti-gaming checks, aggregate report, CLI |
| `scripts/test_routing_eval.py` | Evaluator contract tests — digest freeze, schema strictness, candidate discrimination, reproducibility |
| `scripts/routing_autoresearch.py` | Experiment runner: mutation-surface enforcement, lexicographic gates, verdict classification, append-only log |
| `scripts/test_routing_autoresearch.py` | Runner contract tests — subset gates, judging-file pinning, log schema, verdict statuses |
| `skills/career-agent/tests/fixtures/routing_eval_v1_dev.yml` | Development set, 26 fixtures (visible to a research agent) |
| `skills/career-agent/tests/fixtures/routing_eval_v1_holdout.yml` | Frozen holdout, 56 fixtures (aggregate-only results) |
| `docs/routing-autoresearch-program.md` | The research agent's operating instructions and subject capsule |
| `docs/routing-autoresearch-results.tsv` | Append-only experiment log |
| `scripts/run_all_checks.py` | Registers `routing benchmark contract` in the canonical matrix |

## Contract decisions taken while implementing

Decisions the PRD left to implementation, or where implementation showed the PRD text needed a
concrete reading:

1. **Gate 1 is a subset test against the current best, not absolute zero.** The PRD says critical
   failures must be 0. The baseline has 4 (the negation cases the benchmark was written to expose),
   so an absolute rule deadlocks the loop: no single-hypothesis candidate can clear all four at
   once, which is exactly the multi-hypothesis change Gate 5 forbids. The runner therefore
   DISCARDs any candidate that produces a critical failure the best did not have, and zero remains
   the target the benchmark is designed around. **Gate 0 stays absolute** — the baseline has 0
   philosophy failures, so demanding 0 costs nothing and is the stronger contract.

   Subset, not count. A count comparison passes a candidate that fixes one critical failure and
   introduces a different one — the number is unchanged and a new way to break the contract has
   shipped. E-3 below is that exact candidate, and a count gate would have kept it. Gate 4 uses
   the same subset test for the same reason. The comparison runs over hashed fixture ids so the
   log can support it without carrying back the per-fixture holdout detail the evaluator withholds.
2. **Gate 0 for routing is `explicit_intent` + `stage_mutated`.** Those are the two decision-
   philosophy violations a routing candidate can actually commit: inventing an intent the user
   never stated, and moving the lifecycle stage to make a route fire. The rest of the PRD's Gate 0
   list is structurally unreachable from the mutation surface.
3. **Every file that decides a verdict is pinned, including the runner.** The evaluator, the
   runner, and both contract-test files are digested into each results row and compared on the
   next run; a candidate that edits any of them is INVALID. The path exemption in `HARNESS_PATHS`
   is not the protection — it exists so the harness's own files did not read as an unrelated
   production change before they were committed. Fixtures are pinned twice, by different
   mechanisms, because either alone has a hole: a digest in `test_routing_eval.py` catches an edit
   at any time including uncommitted, and the runner's comparison catches one mid-experiment even
   if the test is never run.
4. **Gate 6 does not require zero critical failures.** Blocking an unrelated improvement on
   pre-existing failures is the same deadlock as (1). Gate 6 is the canonical matrix, as written.
   A candidate that has not cleared it is recorded as `provisional_keep`, never `keep`. Provisional
   candidates still advance the loop — running the full matrix per candidate is the CI cost PRD §17
   separates out — but the log never lets an unverified candidate read as a promotable one.
   A Gate 6 failure that the candidate demonstrably did not cause (untracked local tooling failing
   the whole-tree lint) is `infra_error` per PRD §10, and does not become the next reference.
5. **Holdout isolation is by output shape, not by access control.** `report()` withholds
   per-fixture holdout detail unless `reveal=True`, which the runner never passes. The files are
   readable on disk — an agent that chooses to open them is out of contract, not out of reach.
   Strengthening this to a real boundary needs a separate process, and is not in this phase.
6. **`--on-discard revert` is opt-in, not the default.** Automatic `git checkout` of the mutation
   surface is destructive when the tree holds an uncommitted KEEP. The autonomous loop should pass
   it; a human iterating should not.
7. **Gate 7 is implemented as a term-count tie-break.** PRD §9 ranks fewer changed production
   lines first, but changed LOC is measured against each candidate's own base commit and so does
   not compare across rows. The routing term count is absolute and does compare. Without this gate
   the first candidate to reach a score keeps it even when a strictly smaller change routes
   identically — E-4 is that case.

## Measurements

The benchmark's own starting point, before any candidate:

```
dev      22/26 correct,  2 critical
holdout  43/56 correct,  2 critical, 0 fallback
philosophy failures 0   gaming failures 0   routing terms 219
python 3.13.5 on Darwin
```

Zero fallback failures at baseline: the lexicon under-captures rather than over-captures, which is
the right direction to start research from.

Two candidates were kept, for a net +2 held-out and +1 routing term:

| | held-out | terms |
| --- | --- | --- |
| baseline | 43/56 | 219 |
| E-1 `market_salary` | 44/56 | 222 |
| E-4 `interview_followup` | 45/56 | 220 |

The log restarts whenever a judging file changes, since a baseline row recorded against a
different evaluator or runner cannot be compared to. `docs/routing-autoresearch-results.tsv` holds
the run against the harness as merged.

## Verdict verification

Every runner outcome was exercised against the real subject, not a mock:

| Outcome | How it was produced | Result |
| --- | --- | --- |
| `provisional_keep` | E-1: three plain market-rate synonyms in `market_salary` | held-out 43 → 44, focused checks green |
| `discard` | E-2: `interview_manner` broadened to bare `面接`/`interview`/`면접` | held-out 44 → 41, stopped at Gate 1 |
| `discard` | E-3: fixed two negation criticals, introduced two over-capture criticals | **critical count unchanged at 4**, stopped at Gate 1 on the subset test |
| `provisional_keep` | E-4: three `お礼` compounds collapsed into the bare form | held-out 44 → 45 with three fewer terms |
| `infra_error` | E-4 re-run with `--promote` on a polluted tree | Gate 6 unjudgeable, correctly not attributed to the candidate |
| `INVALID` | a comment line appended to the frozen holdout | rejected on fixture digest before any gate was read |
| `INVALID` | `scripts/run_all_checks.py` edited during a candidate run | rejected on mutation surface |
| `CRASH` | malformed `routing.yml` | reported as CRASH, not DISCARD |

E-2 is the PRD §12 scenario in miniature: a candidate cannot buy back a safety regression with
accuracy, and here it did not even have accuracy to trade. **E-3 is the one that matters** — its
critical failure count is identical to the baseline's, so the count comparison this runner
originally used would have kept it while it shipped two new contract violations.

## Gate 6 status

**Passed.** The canonical matrix ran green on Ubuntu 3.11, Ubuntu 3.13, and Windows 3.11 for the
merged head of this work. Both candidates cleared it.

The log still records them as `provisional_keep`, and that is correct rather than stale: the
runner writes what it could verify at the moment it ran, and it could not run Gate 6 on the
authoring machine. Rewriting the row after the fact would defeat the point of an append-only
record. CI is the Gate 6 authority here.

Four of the 59 canonical checks fail here and nowhere else, all tracing to one untracked local
Claude plugin directory (`.agents/skills/`):

- `ruff` lints the whole tree, including untracked directories, and reports 8 errors inside it.
- `release integrity` and the two SBOM checks call `build_release._assert_clean()`, which runs
  `git status --porcelain --untracked-files=all` and refuses any output at all.

Neither exists in a clean checkout. The runner classifies this as `infra_error` rather than
DISCARD, precisely so the log does not record a false verdict about a candidate that passed every
gate it could be judged on. **CI green on this branch is the Gate 6 evidence; the local run is not.**

## Known limits

- **This is not yet a blind research run.** The benchmark author read holdout failures once to
  validate labels, so E-1 through E-4 demonstrate the runner's mechanics, not the loop's blind
  research capability. Phase 4 is the first run where that claim can be made.
- **The context capsule is untested against a real agent.** `docs/routing-autoresearch-program.md`
  is written to be sufficient on its own, and its factual claims are checked against the runner,
  but whether an agent can actually run a trial from it alone is only known once one does.
- **Bootstrap self-reference.** The harness lists its own files in `HARNESS_PATHS` so that before
  it was committed they did not read as an unrelated production change. `scripts/run_all_checks.py`
  is deliberately *not* in that list — a candidate that could edit it could delete a check to pass
  Gate 6 — so registering the benchmark in the matrix had to land in the harness commit, not during
  an experiment. Now that the harness is committed the list is belt-and-braces; the digest
  comparison against the baseline row is what actually holds.
- **`routing.py` is inside the mutation surface but no experiment has used it.** The PRD wants
  `routing.py` changes gated to an explicit experiment class; today the runner allows it and only
  the LOC budget constrains it.

## Next

1. Phase 3: grow the holdout to 150–300 cases per PRD §7.3, as `routing-eval-v2` if any label in v1
   turns out wrong — v1 is frozen. Whoever writes v2 should not be whoever runs Phase 4 against it.
2. Phase 4: the first autonomous run. Stop rules SR-2 (`N = 20`) and SR-5 apply; the four
   remaining critical failures are all negation/precedence, which may be an SR-5 architectural
   signal rather than a lexicon one.
