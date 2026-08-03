#!/usr/bin/env python3
"""Tests for descriptive workflow observations and explicit user rule promotion."""

from __future__ import annotations

import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibrate  # noqa: E402


def closed(slug: str, **kw) -> dict:
    entry = {"slug": slug, "name": slug, "closed": True, "reached_stage": 3}
    entry.update(kw)
    return entry


def run(fn, *args) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        fn(*args)
    return buffer.getvalue()


def test_below_sample_floor_prints_no_comparison() -> None:
    out = run(calibrate.report, {"companies": [closed("a"), closed("b")]})
    assert "workflow observations: 2" in out
    assert "rate" not in out.lower()


def test_open_entries_do_not_count() -> None:
    pipeline = {"companies": [closed("a"), closed("b"), {"closed": False, "reached_stage": 4}]}
    assert "workflow observations: 2" in run(calibrate.report, pipeline)


def test_closed_without_reached_stage_does_not_count() -> None:
    pipeline = {"companies": [closed("a"), closed("b"), {"closed": True}]}
    assert "workflow observations: 2" in run(calibrate.report, pipeline)


def test_report_at_floor_is_observational() -> None:
    pipeline = {"companies": [
        closed("a", channel="direct"),
        closed("b", channel="agent", feedback_obtained=True),
        closed("c", channel="agent", feedback_obtained=True, gate_override=True, reached_stage=4),
    ]}
    out = run(calibrate.report, pipeline)
    assert "workflow observations (3 closed entries" in out
    assert "agent: 2/2" in out
    assert "direct: 0/1" in out
    assert "User overrides: 1 recorded; 1 reached interview" in out
    assert "not rates or forecasts" in out


def test_no_root_cause_is_promoted() -> None:
    assert "no root_cause" in run(calibrate.rules_report, {"companies": []}, {})


def test_single_cause_is_not_promotable() -> None:
    pipeline = {"companies": [closed("a", root_cause="missing evidence")]}
    out = run(calibrate.rules_report, pipeline, {})
    assert "WAIT missing evidence - 1 entries" in out
    assert "--approve" not in out


def test_two_causes_become_promotable() -> None:
    pipeline = {"companies": [
        closed("a", root_cause="missing evidence"),
        closed("b", root_cause="missing evidence"),
        closed("c", root_cause="preparation"),
    ]}
    out = run(calibrate.rules_report, pipeline, {})
    assert "READY missing evidence - 2 entries [a, b]" in out
    assert "WAIT preparation - 1 entries" in out
    assert "--approve" in out


def test_approve_below_threshold_exits() -> None:
    try:
        calibrate.approve_rule(
            {"companies": [closed("a", root_cause="missing evidence")]},
            "missing evidence", "review the JD", Path("unused-rules.yml"),
        )
    except SystemExit as exc:
        assert "1 supporting entries" in str(exc)
        assert "candidate diagnosis" in str(exc)
        return
    raise AssertionError("promotion below the threshold must exit")


def test_approve_rule_is_atomic_and_locked() -> None:
    """PERSIST-001/005: rule promotion goes through pipeline_store.mutate, not a bare write_text."""
    with tempfile.TemporaryDirectory() as tmp:
        rules_path = Path(tmp) / "rules.yml"
        pipeline = {"companies": [
            closed("a", root_cause="missing evidence"),
            closed("b", root_cause="missing evidence"),
        ]}
        calibrate.approve_rule(pipeline, "missing evidence", "review the JD before applying", rules_path)
        rules = calibrate.load(rules_path, required=False)
        assert rules["rules"][0]["id"] == "missing evidence"
        assert rules["rules"][0]["text"] == "review the JD before applying"
        assert not list(Path(tmp).glob("*.tmp-*")), "atomic_write left a temp file behind"

        try:
            calibrate.approve_rule(pipeline, "missing evidence", "duplicate", rules_path)
        except SystemExit as exc:
            assert "already exists" in str(exc)
        else:
            raise AssertionError("re-approving the same cause must exit")


def test_main_workspace_flag_resolves_pipeline_and_rules_paths() -> None:
    """WORK-001: --workspace resolves both data/pipeline.yml and data/rules.yml under it."""
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "ws"
        (workspace / "data").mkdir(parents=True)
        import yaml

        (workspace / "data" / "pipeline.yml").write_text(
            yaml.safe_dump({"companies": [closed("a", root_cause="missing evidence"),
                                          closed("b", root_cause="missing evidence")]}),
            encoding="utf-8",
        )
        out = io.StringIO()
        with redirect_stdout(out):
            code = calibrate.main(["--workspace", str(workspace), "rules",
                                   "--approve", "missing evidence", "--text", "review the JD"])
        assert code == 0
        rules = calibrate.load(workspace / "data" / "rules.yml", required=False)
        assert rules["rules"][0]["id"] == "missing evidence"


def run_all() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"OK: {len(tests)} calibrate tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_all())
