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
  rank, or interest-weighted result. `Unknown` stays outside skill coverage denominators.
- `scripts/status_bar.py`: nearest deadline, urgent action preview (maximum 3), relevant rules
  preview (maximum 3), all blocker companies/counts, and actionable workflow observations.
- `skills/jiko-bunseki/checklist.html`: local raw reflection export only. The executable collection
  helper and Node regression test cover unanswered, explicit Unknown, lists, episodes, and shape.
- `_shared/self_analysis_profile.py`: strict canonical `SELF_ANALYSIS_PROFILE v2` validation;
  raw checklist submissions are not canonical profiles.

## Deterministic checks

Run from the repository root:

```bash
python scripts/check_context_budget.py
python scripts/check_policy.py
python scripts/check_claim_freshness.py
python scripts/check_reference_paths.py
python scripts/check_agent_context.py
python scripts/check_manifest_consistency.py
python scripts/check_readme_consistency.py
python scripts/test_hook_contract.py
python _shared/test_self_analysis_profile.py
python skills/career-agent/test_state_durability.py
node skills/jiko-bunseki/tests/test_checklist_runtime.js
```

The Ubuntu/Windows CI matrix also runs the routing, Career Agent lifecycle, matching, status bar,
pipeline, policy, and Jiko source-contract tests. `requirements.txt` supplies runtime YAML support;
Ruff is installed by CI for `E4,E7,E9,F` checks.

## Safe context rules

Do not preload unrelated `_shared/agent_context` families or full Tier 2 evidence. A shorter status
bar may omit non-actionable repeated detail, but never omits a gate, blocker company/count, nearest
actionable deadline, required Unknown, provenance boundary, or approval requirement. A budget is a
guardrail, not permission to change decision semantics.
