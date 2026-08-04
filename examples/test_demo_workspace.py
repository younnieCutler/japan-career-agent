"""Executable contract for the synthetic demo workspace."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "examples" / "demo-workspace" / "matching-input.example.json"


def main() -> int:
    for required in (
        ROOT / "examples" / "demo-workspace" / "candidate-profile.example.yml",
        ROOT / "examples" / "demo-workspace" / "company-profile.example.yml",
        ROOT / "examples" / "demo-workspace" / "data" / "pipeline.yml",
    ):
        if not required.is_file():
            raise SystemExit(f"missing demo fixture: {required}")
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    if any("score" in key.lower() or "probability" in key.lower() for key in payload):
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
    print("OK: synthetic demo workspace contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
