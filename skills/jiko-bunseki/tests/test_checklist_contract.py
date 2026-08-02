#!/usr/bin/env python3
"""Regression checks for explicit self-analysis checklist answers."""

from pathlib import Path


CHECKLIST = Path(__file__).resolve().parents[1] / "checklist.html"


def test_slider_defaults_are_not_answers() -> None:
    source = CHECKLIST.read_text(encoding="utf-8")
    assert 'data-touched="false"' in source
    assert "function collectSliderAnswers" in source
    assert "input.dataset.touched !== 'true'" in source
    assert "missing.push(`${prefix}_${i}`)" in source


def test_missing_slider_feedback_targets_the_right_section() -> None:
    source = CHECKLIST.read_text(encoding="utf-8")
    assert "#workstyle-container" in source
    assert "#wellbeing-container" in source
    assert "slider-row.missing" in source


if __name__ == "__main__":
    test_slider_defaults_are_not_answers()
    test_missing_slider_feedback_targets_the_right_section()
    print("OK: 2 checklist contract tests passed")
