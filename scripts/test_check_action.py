#!/usr/bin/env python3
"""Tests for check_action.py's pipeline_store-backed write path.

The behaviour worth protecting: writes go through pipeline_store (atomic rename, no
stray temp file left behind) and checking an already-checked item is a no-op that
does not append a second history entry.

Run: python3 scripts/test_check_action.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))

import check_action  # noqa: E402
import pipeline_store  # noqa: E402


def seeded_pipeline(path: Path) -> None:
    pipeline_store.atomic_write(path, {
        "companies": [{
            "slug": "gao", "name": "GAO", "closed": False, "history": [],
            "action_items": [{"id": "a1", "text": "履歴書を送る", "checked": False}],
        }],
    })


def test_check_marks_item_and_leaves_no_temp_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pipeline.yml"
        seeded_pipeline(path)
        pipeline = check_action.load(path)
        check_action.check(pipeline, "gao", "a1", path)
        reloaded = pipeline_store.load(path)
        item = reloaded["companies"][0]["action_items"][0]
        assert item["checked"] is True, reloaded
        assert len(reloaded["companies"][0]["history"]) == 1, reloaded
        leftovers = list(Path(tmp).glob("*.tmp-*"))
        assert not leftovers, f"atomic_write left a temp file behind: {leftovers}"


def test_checking_twice_does_not_duplicate_history():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pipeline.yml"
        seeded_pipeline(path)
        pipeline = check_action.load(path)
        check_action.check(pipeline, "gao", "a1", path)
        pipeline = check_action.load(path)
        check_action.check(pipeline, "gao", "a1", path)
        reloaded = pipeline_store.load(path)
        assert len(reloaded["companies"][0]["history"]) == 1, reloaded


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
    print(f"OK: {len(tests)} check_action tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_all())
