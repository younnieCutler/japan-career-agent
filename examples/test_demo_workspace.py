"""Executable contract for the synthetic demo workspace."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "examples" / "demo-workspace" / "matching-input.example.json"


def contains_forbidden_outcome_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            ("score" in str(key).lower() or "probability" in str(key).lower())
            or contains_forbidden_outcome_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(contains_forbidden_outcome_key(child) for child in value)
    return False


def main() -> int:
    for required in (
        ROOT / "examples" / "demo-workspace" / "candidate-profile.example.yml",
        ROOT / "examples" / "demo-workspace" / "company-profile.example.yml",
        ROOT / "examples" / "demo-workspace" / "data" / "pipeline.yml",
    ):
        if not required.is_file():
            raise SystemExit(f"missing demo fixture: {required}")
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    if contains_forbidden_outcome_key(payload):
        raise SystemExit("demo input contains a forbidden outcome field")
    result = subprocess.run(
        [sys.executable, str(ROOT / "_shared" / "matching_v3.py"), str(INPUT), "--text"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise SystemExit(result.stderr or "demo matching command failed")
    for marker in ("Decision Status: Conflict", "Unknown", "Missing", "Conflict"):
        if marker not in result.stdout:
            raise SystemExit(f"demo output missing marker: {marker}")
    pipeline = yaml.safe_load(
        (ROOT / "examples" / "demo-workspace" / "data" / "pipeline.yml").read_text(encoding="utf-8")
    ) or {}
    company = next(
        (item for item in pipeline.get("companies", []) if item.get("name") == payload["company_name"]),
        None,
    )
    if company is None:
        raise SystemExit("demo pipeline is missing the matching synthetic company")
    if company.get("decision_status") != "conflict":
        raise SystemExit("demo pipeline decision_status must match the synthetic diagnosis")
    if not company.get("match_conflicts"):
        raise SystemExit("demo pipeline must expose match_conflicts for a conflict diagnosis")
    print("OK: synthetic demo workspace contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
