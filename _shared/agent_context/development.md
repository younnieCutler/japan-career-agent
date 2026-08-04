# Development context — lazy reference

Load this file for implementation, review, or repository-wide verification. It is not a second
decision philosophy; `_shared/decision_philosophy.md` and `_shared/schemas.yml` remain canonical.

## Ownership map

- `skills/career-agent/runtime.py` and `career_agent.py`: thin CLI compatibility facade and
  high-level orchestration; they do not own persistence, routing, proposal, lifecycle, or
  projection algorithms.
- `skills/career-agent/models.py` / `validation.py`: pure contracts and event/context validation.
- `skills/career-agent/routing.py`: KO/JA/EN language, track, stage, skill-context, and flow-phase
  routing.
- `skills/career-agent/persistence.py`: canonical JSON/TOML/JSONL readers and atomic writers.
- `skills/career-agent/vault.py`: Vault paths, metadata indexing, trusted-context selection, and
  canonical Vault state facade.
- `skills/career-agent/proposals.py`: approval-gated event/context proposal creation and listing.
- `skills/career-agent/lifecycle.py`: Vault locking, approval, retry-safe checkpoints, recovery,
  and safe-stop trajectories.
- `skills/career-agent/projection.py`: company slugs, workspace resolution, pipeline projection,
  event-to-state projection, and legacy pipeline migration.
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
