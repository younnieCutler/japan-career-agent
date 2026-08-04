# Development context — lazy reference

Load this file for implementation, review, or repository-wide verification. It is not a second
decision philosophy; `_shared/decision_philosophy.md` and `_shared/schemas.yml` remain canonical.

## Ownership map

- `skills/career-agent/career_agent.py`: `load_routing`, `infer_track`, `stage_for`,
  `flow_phase_for`, event validation, approval, checkpoints, recovery, Vault metadata context,
  atomic JSON/TOML/rewritten-JSONL state writes, and workspace projection.
- `_shared/pipeline_store.py`: the lock + atomic writer for `data/pipeline.yml`; legacy fields are
  readable but new legacy writes are rejected.
- `_shared/matching_v3.py`: independent-axis `evidence_based_v3`; no composite score, probability,
  rank, or interest-weighted result. `Unknown` stays outside skill coverage denominators, while
  confirmed required gaps get separate deterministic verification questions.
- `scripts/status_bar.py`: nearest deadline, urgent action preview (maximum 3), relevant rules
  preview (maximum 3), all blocker companies/counts, and actionable workflow observations.
- `skills/jiko-bunseki/checklist.html`: local raw reflection export only. The executable collection
  helper and Node regression test cover unanswered, explicit Unknown, lists, episodes, and shape.
- `_shared/self_analysis_profile.py`: strict canonical `SELF_ANALYSIS_PROFILE v2` validation;
  raw checklist submissions are not canonical profiles. Optional nested shapes and known IDs are
  validated without migration.

## Deterministic checks

Run from the repository root:

```bash
python scripts/run_all_checks.py
```

The runner is the canonical local/CI verification path; it includes the repository checks used by
CI and keeps the release/document/version gates in the same command sequence.

The Ubuntu/Windows CI matrix also runs the routing, Career Agent lifecycle, matching, status bar,
pipeline, policy, and Jiko source-contract tests. `requirements.txt` supplies runtime YAML support;
Ruff is installed by CI for `E4,E7,E9,F` checks.

## Safe context rules

Do not preload unrelated `_shared/agent_context` families or full Tier 2 evidence. A shorter status
bar may omit non-actionable repeated detail, but never omits a gate, blocker company/count, nearest
actionable deadline, required Unknown, provenance boundary, or approval requirement. A budget is a
guardrail, not permission to change decision semantics.

## Command tooling (RTK)

Use RTK as the command prefix when it has a suitable wrapper. It reduces routine command output;
use `rtk proxy` when the unfiltered output is needed.

### Common workflows

```bash
rtk pytest                 # Python tests
rtk test <cmd>             # generic test wrapper
rtk ruff check .           # linting when available through the wrapper
rtk git status             # compact Git status
rtk git diff               # compact diff
rtk git add                # compact staging output
rtk git commit             # compact commit output
rtk git push               # compact push output
rtk gh pr view <num>       # compact pull-request view
rtk gh pr checks <num>     # compact pull-request checks
rtk gh run list            # compact workflow list
rtk ls <path>              # compact file listing
rtk read <file>            # compact file reading
rtk grep <pattern>         # compact search
rtk find <pattern>         # compact file search
rtk err <cmd>              # errors only
rtk summary <cmd>          # summarized command output
rtk gain                   # token-savings summary
rtk gain --history         # token-savings history
```

Git passthrough supports subcommands not listed above. Keep repository `CLAUDE.md` within the
context budget; do not run `rtk init` against it. Use `rtk init --global` only when global RTK
instructions are intentionally being updated.
