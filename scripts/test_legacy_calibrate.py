#!/usr/bin/env python3
"""Tests for the read-only legacy_v1 inspection path (WORK-001 workspace resolution)."""

from __future__ import annotations

import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_calibrate  # noqa: E402
import pipeline_store  # noqa: E402


def test_refuses_without_explicit_flag():
    try:
        legacy_calibrate.main([])
    except SystemExit as exc:
        assert "--legacy-experimental" in str(exc)
        return
    raise AssertionError("must refuse without --legacy-experimental")


def test_workspace_flag_resolves_pipeline_path():
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "ws"
        pipeline_store.atomic_write(workspace / "data" / "pipeline.yml", {
            "companies": [{"slug": "gao", "name": "GAO", "closed": True, "reached_stage": 4,
                           "predicted_tier": "B", "feedback_obtained": True}],
        })
        out = io.StringIO()
        with redirect_stdout(out):
            code = legacy_calibrate.main(["--workspace", str(workspace), "--legacy-experimental"])
        assert code == 0
        assert "tier=B" in out.getvalue(), out.getvalue()
        assert "reached=4 Interview" in out.getvalue(), out.getvalue()


def run() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"OK: {len(tests)} legacy_calibrate tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
