#!/usr/bin/env python3
"""Read-only inspection of legacy_v1 tier history.

This module is intentionally opt-in and never imports legacy values into an evidence_based_v3
result. It exists only so old pipeline entries remain inspectable without making the default workflow
look predictive.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
import pipeline_store  # noqa: E402
from calibrate import load, scored_entries  # noqa: E402
from status_bar import stage_label  # noqa: E402


def report(pipeline: dict) -> int:
    entries = [entry for entry in scored_entries(pipeline) if entry.get("predicted_tier")]
    if not entries:
        print("legacy_v1: no historical predicted_tier entries found.")
        return 0
    print("legacy_v1 historical tiers (read-only; not a v3 diagnosis or hiring forecast)")
    for entry in sorted(entries, key=lambda item: str(item.get("predicted_tier"))):
        reached = entry.get("reached_stage")
        label = stage_label(reached)
        print(
            f"- {str(entry.get('name') or entry.get('slug'))}: "
            f"tier={entry.get('predicted_tier')} reached={label or 'unknown'} "
            f"feedback={'yes' if entry.get('feedback_obtained') else 'no'}"
        )
    print("These historical labels are preserved for audit only and must not be compared with v3 fields.")
    return 0


def main(argv: list[str]) -> int:
    argv, workspace = pipeline_store.extract_workspace_flag(list(argv))
    if argv != ["--legacy-experimental"]:
        raise SystemExit(
            "refusing legacy calibration; pass --legacy-experimental explicitly "
            "(optionally with --workspace <dir>)"
        )
    pipeline_path = pipeline_store.resolve_pipeline_path(workspace)
    return report(load(pipeline_path, required=False))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
