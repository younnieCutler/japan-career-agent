#!/usr/bin/env python3
"""Status bar accuracy tests.

Accuracy is the first-line metric for this component, not a nice-to-have: the model
trusts these values without recomputing them, so a wrong count propagates straight into
its answer. Each test asserts exact output, not "contains roughly".

Run: python3 scripts/test_status_bar.py
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from status_bar import build_status  # noqa: E402

TODAY = dt.date(2026, 8, 2)


def company(slug, **kw):
    entry = {"slug": slug, "name": kw.pop("name", slug), "closed": False}
    entry.update(kw)
    return entry


def test_empty_pipeline_prints_nothing():
    assert build_status({"companies": []}, {}, TODAY) == ""
    assert build_status({}, {}, TODAY) == ""


def test_counts_and_stage_breakdown():
    pipeline = {
        "companies": [
            company("a", stage=3),
            company("b", stage=4),
            company("c", stage=4),
            company("d", stage=4, closed=True, reached_stage=4),
        ]
    }
    assert build_status(pipeline, {}, TODAY) == (
        "<career_status>\n"
        "pipeline: 3 active (3 応募・書類 1, 4 面接 2) / 1 closed\n"
        "calibration: 1 scored outcomes (need 2 more)\n"
        "</career_status>"
    )


def test_nearest_deadline_only():
    pipeline = {
        "companies": [
            company("far", stage=4, deadline="2026-08-20", status="二次面接"),
            company("near", name="Acme", stage=5, deadline="2026-08-06", status="回答期限"),
        ]
    }
    out = build_status(pipeline, {}, TODAY)
    assert "deadline: Acme 2026-08-06 (D+4) 回答期限" in out
    assert "2026-08-20" not in out, "only the nearest deadline belongs in the bar"


def test_deadline_today_and_overdue():
    today_only = {"companies": [company("x", stage=5, deadline="2026-08-02")]}
    assert "(TODAY)" in build_status(today_only, {}, TODAY)
    overdue = {"companies": [company("x", stage=5, deadline="2026-07-30")]}
    assert "(3d OVERDUE)" in build_status(overdue, {}, TODAY)


def test_unchecked_actions_block_interview_prep():
    """The failure this suite exists to prevent: a checklist written, then never opened."""
    pipeline = {
        "companies": [
            company(
                "triple",
                name="トリプルアイズ",
                stage=4,
                action_items=[
                    {"id": "num", "text": "エピソードに数値を入れる", "checked": False},
                    {"id": "prep", "text": "PREP 10問ドリル", "checked": False},
                    {"id": "jd", "text": "職務理解の確認", "checked": True},
                ],
            )
        ]
    }
    out = build_status(pipeline, {}, TODAY)
    assert "unchecked_actions[トリプルアイズ]: 2 — エピソードに数値を入れる; PREP 10問ドリル" in out
    assert "gate: interview-prep generation BLOCKED for トリプルアイズ" in out
    assert "scripts/check_action.py" in out, "the bar must name the way out of the gate"


def test_gate_clears_when_all_checked():
    pipeline = {
        "companies": [
            company(
                "a",
                stage=4,
                action_items=[{"id": "x", "text": "done", "checked": True}],
            )
        ]
    }
    out = build_status(pipeline, {}, TODAY)
    assert "unchecked_actions" not in out
    assert "BLOCKED" not in out


def test_active_rules_quoted_verbatim():
    rules = {
        "rules": [
            {"text": "自己PRにソフトスキルを言わない", "status": "active"},
            {"text": "まだ根拠1件", "status": "candidate"},
            {"text": "もう使わない", "status": "retired"},
        ]
    }
    out = build_status({"companies": [company("a", stage=4)]}, rules, TODAY)
    assert "active_rules: 1" in out
    assert "  - 自己PRにソフトスキルを言わない" in out
    assert "まだ根拠1件" not in out, "candidate rules are not yet rules"
    assert "もう使わない" not in out


def test_calibration_threshold():
    def scored(n):
        return {
            "companies": [
                company(f"c{i}", closed=True, reached_stage=3) for i in range(n)
            ]
        }

    assert "calibration: 2 scored outcomes (need 1 more)" in build_status(scored(2), {}, TODAY)
    assert "calibration: 3 scored outcomes — `scripts/calibrate.py` available" in build_status(
        scored(3), {}, TODAY
    )


def test_diversity_warning_only_when_window_full_and_uniform():
    def demo(values):
        return {"companies": [company(f"c{i}", demo_slot=v) for i, v in enumerate(values)]}

    assert "diversity:" in build_status(demo(["no"] * 5), {}, TODAY)
    # One artifact-demo slot in the window: not one-axis, no warning.
    assert "diversity:" not in build_status(demo(["no", "no", "yes", "no", "no"]), {}, TODAY)
    # company_test is a different axis from `yes` and must not be collapsed into `no`.
    assert "diversity:" not in build_status(demo(["no", "no", "no", "company_test", "no"]), {}, TODAY)
    # Too few known values to claim a pattern.
    assert "diversity:" not in build_status(demo(["no"] * 4), {}, TODAY)
    assert "diversity:" not in build_status(demo(["no", "no", "unknown", "no", "no"]), {}, TODAY)


def test_no_prose_lines():
    """Every line must be `key: value`, scannable without parsing a sentence."""
    pipeline = {
        "companies": [
            company("a", stage=4, deadline="2026-08-05",
                    action_items=[{"id": "x", "text": "y", "checked": False}])
        ]
    }
    rules = {"rules": [{"text": "r", "status": "active"}]}
    body = build_status(pipeline, rules, TODAY).splitlines()[1:-1]
    for line in body:
        assert ":" in line or line.startswith("  - "), f"prose line found: {line!r}"


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
    print(f"OK: {len(tests)} status bar tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
