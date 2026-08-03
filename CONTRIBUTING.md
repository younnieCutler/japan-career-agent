# Contributing

This repository is an evidence-based, local-first career decision-support system. Keep changes
within the requested scope and preserve `Unknown`, confirmed conflicts, independent interest, and
legacy read-only compatibility.

## Before opening a change

- Read `AGENTS.md` and the relevant `_shared/agent_context/` reference.
- Do not add candidate-outcome percentages, composite scores, proprietary recruiter-algorithm
  claims, fabricated evidence, or automatic application/message actions.
- Keep external claims dated, sourced, confidence-labelled, and freshness-checkable.
- Do not include personal resumes, Vault files, pipeline data, or secrets.

## Verification

Run the deterministic checks relevant to the change. For a repository-wide change, run the same
Ubuntu/Windows matrix used by CI:

```bash
python -m pip install -r requirements.txt
python -m pip install "ruff>=0.8,<1"
python -m ruff check .
python scripts/check_policy.py
python scripts/check_claim_freshness.py
python scripts/check_context_budget.py
python scripts/check_reference_paths.py
python scripts/check_agent_context.py
python scripts/check_manifest_consistency.py
python scripts/check_readme_consistency.py
python scripts/test_hook_contract.py
python scripts/test_status_bar.py
python scripts/test_pipeline_integration.py
python _shared/test_matching_v3.py
python _shared/test_self_analysis_profile.py
python skills/career-agent/test_state_durability.py
node skills/jiko-bunseki/tests/test_checklist_runtime.js
```

When changing a writer or schema, also run its focused tests and one lifecycle smoke test. Verify
Windows path handling and retry/idempotency behavior when applicable. Context-budget changes require
the reason and baseline evidence to be recorded; token reduction without semantic regression tests
is not acceptable.

## Pull requests

Describe the decision or contract changed, list files touched, include regression tests, and state
any remaining limitation. Keep unrelated cleanup in a separate change. A maintainer reviews and
merges; the author should still perform the self-review checklist in the pull-request template.
