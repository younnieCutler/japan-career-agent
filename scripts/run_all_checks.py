#!/usr/bin/env python3
"""Run the repository verification matrix from one deterministic entry point."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

CHECKS = (
    ("ruff", (PYTHON, "-m", "ruff", "check", "--select", "E4,E7,E9,F", ".")),
    ("policy", (PYTHON, "scripts/check_policy.py")),
    # Runs early on purpose: a tracked personal document is the one finding worth surfacing
    # before spending the rest of the matrix.
    ("private data", (PYTHON, "scripts/check_private_data.py")),
    ("private data tests", (PYTHON, "scripts/test_check_private_data.py")),
    ("claim freshness", (PYTHON, "scripts/check_claim_freshness.py")),
    ("context budget", (PYTHON, "scripts/check_context_budget.py")),
    ("reference paths", (PYTHON, "scripts/check_reference_paths.py")),
    ("agent context", (PYTHON, "scripts/check_agent_context.py")),
    ("manifest consistency", (PYTHON, "scripts/check_manifest_consistency.py")),
    ("README consistency", (PYTHON, "scripts/check_readme_consistency.py")),
    ("release consistency", (PYTHON, "scripts/check_release_consistency.py")),
    ("schema contract", (PYTHON, "scripts/check_schema_contract.py")),
    ("schema contract tests", (PYTHON, "scripts/test_schema_contract.py")),
    ("dependency lock", (PYTHON, "scripts/check_dependency_lock.py")),
    ("dependency lock tests", (PYTHON, "scripts/test_dependency_lock.py")),
    ("SBOM", (PYTHON, "scripts/build_sbom.py", "--check")),
    ("SBOM tests", (PYTHON, "scripts/test_sbom.py")),
    ("release integrity", (PYTHON, "scripts/test_release_integrity.py")),
    ("live canary contract", (PYTHON, "scripts/test_live_canary.py")),
    ("release tag checker", (PYTHON, "scripts/test_release_tag.py")),
    ("version bump gate", (PYTHON, "scripts/check_version_bump.py")),
    ("hook lifecycle", (PYTHON, "scripts/test_hook_contract.py")),
    ("career-agent", (PYTHON, "skills/career-agent/test_career_agent.py")),
    ("career-agent golden CLI", (PYTHON, "skills/career-agent/test_golden_cli.py")),
    ("career-agent UX contract", (PYTHON, "skills/career-agent/test_ux.py")),
    ("career-agent guided frontend", (PYTHON, "skills/career-agent/test_guided.py")),
    ("career-agent localization", (PYTHON, "skills/career-agent/test_localization.py")),
    ("career-agent UX regression eval", (PYTHON, "skills/career-agent/test_ux_regression_eval.py")),
    ("Career Agent P1 workflows", (PYTHON, "scripts/test_workflows.py")),
    ("career-agent boundary imports", (PYTHON, "skills/career-agent/test_boundary_imports.py")),
    ("career-agent architecture boundary", (PYTHON, "scripts/check_career_agent_boundaries.py")),
    ("career-agent architecture boundary tests", (PYTHON, "scripts/test_career_agent_boundaries.py")),
    ("career-agent private store", (PYTHON, "skills/career-agent/test_private_store.py")),
    ("career-agent personal timeline", (PYTHON, "skills/career-agent/test_personal_timeline.py")),
    ("career-agent fact promotion", (PYTHON, "skills/career-agent/test_fact_promotion.py")),
    ("career-agent durability", (PYTHON, "skills/career-agent/test_state_durability.py")),
    ("career-agent routing", (PYTHON, "skills/career-agent/test_routing.py")),
    ("career-agent routing intents", (PYTHON, "skills/career-agent/test_routing_intents.py")),
    ("routing benchmark contract", (PYTHON, "scripts/test_routing_eval.py")),
    ("routing runner contract", (PYTHON, "scripts/test_routing_autoresearch.py")),
    ("career-agent onboarding", (PYTHON, "skills/career-agent/test_onboarding.py")),
    ("career-agent career axes", (PYTHON, "skills/career-agent/test_career_axes.py")),
    ("career-agent work events", (PYTHON, "skills/career-agent/test_work_event.py")),
    ("career-agent projects", (PYTHON, "skills/career-agent/test_project.py")),
    ("career-agent experiences", (PYTHON, "skills/career-agent/test_experience.py")),
    ("career-agent evidence reuse", (PYTHON, "skills/career-agent/test_reuse.py")),
    ("matching v3", (PYTHON, "_shared/test_matching_v3.py")),
    ("legacy self-test", (PYTHON, "_shared/legacy_experimental.py", "--self-test")),
    ("legacy calibration", (PYTHON, "scripts/legacy_calibrate.py", "--legacy-experimental")),
    ("legacy calibration tests", (PYTHON, "scripts/test_legacy_calibrate.py")),
    ("status bar", (PYTHON, "scripts/test_status_bar.py")),
    ("calibration", (PYTHON, "scripts/test_calibrate.py")),
    ("action checks", (PYTHON, "scripts/test_check_action.py")),
    ("pipeline integration", (PYTHON, "scripts/test_pipeline_integration.py")),
    ("pipeline CLI", (PYTHON, "scripts/test_pipeline_cli.py")),
    ("E2E artifact packaging", (PYTHON, "scripts/test_e2e_artifact.py")),
    ("pipeline store durability", (PYTHON, "_shared/test_pipeline_store.py")),
    ("policy regression", (PYTHON, "scripts/test_policy.py")),
    ("canonical self-analysis", (PYTHON, "_shared/test_self_analysis_profile.py")),
    ("synthetic demo workspace", (PYTHON, "examples/test_demo_workspace.py")),
    ("mock-interviewer contract", (PYTHON, "skills/mock-interviewer/tests/test_contract.py")),
    ("behavior eval runner", (PYTHON, "scripts/test_behavior_eval_runner.py")),
    (
        "behavior eval contract scenarios",
        (PYTHON, "scripts/run_behavior_evals.py", "--schema", "_shared/behavior_eval_schema.yml"),
    ),
    ("Jiko source contract", (PYTHON, "skills/jiko-bunseki/tests/test_checklist_contract.py")),
    ("Jiko executable export", ("node", "skills/jiko-bunseki/tests/test_checklist_runtime.js")),
)


def main() -> int:
    for label, command in CHECKS:
        print(f"\n==> {label}: {' '.join(command)}", flush=True)
        try:
            result = subprocess.run(command, cwd=ROOT, check=False)
        except OSError as exc:
            print(f"{label} could not start: {exc}", file=sys.stderr, flush=True)
            return 1
        if result.returncode:
            print(f"FAILED: {label} (exit {result.returncode})", file=sys.stderr, flush=True)
            return result.returncode
    print(f"\nAll {len(CHECKS)} repository checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
