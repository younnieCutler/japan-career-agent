#!/usr/bin/env python3
"""Tests for the offline loop: calibration report and rule promotion.

The behaviour worth protecting here is the refusal to conclude — no table below the
sample floor, no rule below two supporting entries. Those are the guards, so they get
the tests.

Run: python3 scripts/test_calibrate.py
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import calibrate  # noqa: E402


def closed(slug, **kw):
    entry = {"slug": slug, "name": slug, "closed": True, "reached_stage": 3}
    entry.update(kw)
    return entry


def run(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


def test_below_sample_floor_prints_no_table():
    pipeline = {"companies": [closed("a"), closed("b")]}
    out = run(calibrate.report, pipeline)
    assert "標本不足: 2 scored outcome(s), need 3" in out
    assert "予測 vs 実際" not in out, "a 2-row table is exactly what this must not print"


def test_open_entries_do_not_count_as_outcomes():
    pipeline = {
        "companies": [
            closed("a"), closed("b"),
            {"slug": "c", "closed": False, "reached_stage": 4},
        ]
    }
    assert "標本不足: 2" in run(calibrate.report, pipeline)


def test_closed_without_reached_stage_does_not_count():
    pipeline = {
        "companies": [closed("a"), closed("b"), {"slug": "c", "closed": True}]
    }
    assert "標本不足: 2" in run(calibrate.report, pipeline)


def test_report_at_floor():
    pipeline = {
        "companies": [
            closed("a", predicted_tier="A", reached_stage=1, channel="direct"),
            closed("b", predicted_tier="B", reached_stage=4, channel="agent",
                   feedback_obtained=True),
            closed("c", predicted_tier="B", reached_stage=4, channel="agent",
                   feedback_obtained=True, gate_override=True),
        ]
    }
    out = run(calibrate.report, pipeline)
    assert "キャリブレーション (3 scored outcomes)" in out
    assert "A: 1.0 (n=1)" in out
    assert "B: 4.0 (n=2)" in out
    assert "agent: 2/2" in out
    assert "direct: 0/1" in out
    assert "1 overrides, 1 reached 面接" in out
    assert "n=3. Direction only, not a rate." in out


def test_no_overrides_says_gate_is_unscored():
    pipeline = {"companies": [closed(s, predicted_tier="B") for s in "abc"]}
    out = run(calibrate.report, pipeline)
    assert "no overrides recorded" in out
    assert "can never be shown to be wrong" in out


def test_single_cause_is_not_promotable():
    pipeline = {"companies": [closed("a", root_cause="数値なし")]}
    out = run(calibrate.rules_report, pipeline, {})
    assert "… 数値なし — 1件" in out
    assert "needs 1 more before it becomes a rule" in out
    assert "--approve" not in out, "nothing is promotable, so offer no promotion command"


def test_two_causes_become_promotable():
    pipeline = {
        "companies": [
            closed("a", root_cause="数値なし"),
            closed("b", root_cause="数値なし"),
            closed("c", root_cause="PREP構造欠如"),
        ]
    }
    out = run(calibrate.rules_report, pipeline, {})
    assert "✅ 数値なし — 2件 [a, b]" in out
    assert "… PREP構造欠如 — 1件" in out
    assert "--approve" in out


def test_measurement_caveat_always_present():
    """The one thing the counts cannot show: the axis you won on produces no row."""
    pipeline = {"companies": [closed("a", root_cause="数値なし")]}
    out = run(calibrate.rules_report, pipeline, {})
    assert "not a distribution of your ability" in out
    assert "demo_slot" in out


def test_approve_below_threshold_exits():
    pipeline = {"companies": [closed("a", root_cause="数値なし")]}
    try:
        calibrate.approve_rule(pipeline, {}, "数値なし", "always add a number")
    except SystemExit as exc:
        assert "1 supporting entr" in str(exc)
        assert "not your weakness" in str(exc)
        return
    raise AssertionError("promotion below the threshold must exit")


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
    print(f"OK: {len(tests)} calibrate tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_all())
