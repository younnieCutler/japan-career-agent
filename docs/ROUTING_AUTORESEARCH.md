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
| `scripts/routing_autoresearch.py` | Experiment runner: mutation-surface enforcement, lexicographic gates, KEEP/DISCARD/CRASH/INVALID, append-only log |
| `skills/career-agent/tests/fixtures/routing_eval_v1_dev.yml` | Development set, 26 fixtures (visible to a research agent) |
| `skills/career-agent/tests/fixtures/routing_eval_v1_holdout.yml` | Frozen holdout, 56 fixtures (aggregate-only results) |
| `docs/routing-autoresearch-results.tsv` | Append-only experiment log |
| `scripts/run_all_checks.py` | Registers `routing benchmark contract` in the canonical matrix |

## Contract decisions taken while implementing

Decisions the PRD left to implementation, or where implementation showed the PRD text needed a
concrete reading:

1. **Gate 1 is monotone against the current best, not absolute zero.** The PRD says critical
   failures must be 0. The baseline has 4 (the negation cases the benchmark was written to expose),
   so an absolute rule deadlocks the loop: no single-hypothesis candidate can clear all four at
   once, which is exactly the multi-hypothesis change Gate 5 forbids. The runner therefore
   DISCARDs any candidate whose critical count rises above the best, and zero remains the target
   the benchmark is designed around. **Gate 0 stays absolute** — the baseline has 0 philosophy
   failures, so demanding 0 costs nothing and is the stronger contract.
2. **Gate 0 for routing is `explicit_intent` + `stage_mutated`.** Those are the two decision-
   philosophy violations a routing candidate can actually commit: inventing an intent the user
   never stated, and moving the lifecycle stage to make a route fire. The rest of the PRD's Gate 0
   list is structurally unreachable from the mutation surface.
3. **Fixture and evaluator immutability is enforced twice**, by different mechanisms, because
   either alone has a hole: a digest pinned in `test_routing_eval.py` (catches an edit at any time,
   including uncommitted), and a digest comparison against the baseline row in the runner (catches
   an edit mid-experiment even if the test is not run).
4. **Gate 6 does not require zero critical failures.** Blocking an unrelated improvement on
   pre-existing failures is the same deadlock as (1). Gate 6 is the canonical matrix, as written.
5. **Holdout isolation is by output shape, not by access control.** `report()` withholds
   per-fixture holdout detail unless `reveal=True`, which the runner never passes. The files are
   readable on disk — an agent that chooses to open them is out of contract, not out of reach.
   Strengthening this to a real boundary needs a separate process, and is not in this phase.
6. **`--on-discard revert` is opt-in, not the default.** Automatic `git checkout` of the mutation
   surface is destructive when the tree holds an uncommitted KEEP. The autonomous loop should pass
   it; a human iterating should not.

## Baseline measurement

```
dev      22/26 correct,  2 critical
holdout  43/56 correct,  2 critical, 0 fallback
philosophy failures 0   gaming failures 0   routing terms 219
python 3.13.5 on Darwin
```

Zero fallback failures at baseline: the current lexicon under-captures rather than over-captures,
which is the right direction to start research from.

## Verdict verification

All four runner outcomes were exercised against the real subject:

| Outcome | How it was produced | Result |
| --- | --- | --- |
| KEEP | E-1: three plain market-rate synonyms in `market_salary` | held-out 43 → 44, focused checks green |
| DISCARD | E-2: `interview_manner` broadened to bare `面接`/`interview`/`면접` | held-out 44 → 41, critical 4 → 9, stopped at Gate 1 |
| INVALID | appended a comment line to the frozen holdout | rejected on fixture digest before any gate was read |
| INVALID | edited `scripts/run_all_checks.py` during a candidate run | rejected on mutation surface |
| CRASH | malformed `routing.yml` | reported as CRASH, not DISCARD |

E-2 is the PRD §12 scenario in miniature: a candidate cannot buy back a safety regression with
accuracy, and here it did not even have accuracy to trade.

## Gate 6 status

E-1 is committed (+2 LOC, +3 terms in `skills/career-agent/references/routing.yml`) and shipped in
release `1.19.0`. 55 of the 58 canonical checks pass on the resulting clean tree. The three that do
not fail for reasons outside this work, on a developer machine only:

- `ruff` reports 8 errors, all inside an untracked local Claude plugin directory
  (`.agents/skills/caveman-compress/`).
- `release integrity` and its SBOM sibling call `build_release._assert_clean()`, which runs
  `git status --porcelain --untracked-files=all` and refuses any output at all — the same untracked
  plugin directory.

Neither exists in a clean CI checkout, so Gate 6 is expected to pass there. Re-verify on CI rather
than treating this local result as the promotion evidence.

## Known limits

- **The demo run is not a blind research run.** The benchmark author read holdout failures once to
  validate labels, so E-1/E-2 demonstrate the runner's mechanics, not the loop's blind research
  capability. Phase 4 is the first run where that claim can be made.
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
   turns out wrong — v1 is frozen.
2. Phase 4: the first autonomous run. Stop rules SR-2 (`N = 20`) and SR-5 apply; the four
   remaining critical failures are all negation/precedence, which may be an SR-5 architectural
   signal rather than a lexicon one.
