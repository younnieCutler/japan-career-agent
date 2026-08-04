#!/usr/bin/env python3
"""Guard the mock-interviewer readiness and trigger contract against prose drift."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = ROOT / "mock-interviewer" / "SKILL.md"


def _section(text: str, heading: str, next_heading: str) -> str:
    start = text.index(heading)
    end = text.index(next_heading, start)
    return text[start:end]


def test_frontmatter_describes_adaptive_deep_dive() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1].lower()

    assert "adaptive deep-dive" in frontmatter
    assert "probe families" in frontmatter
    assert "3-level" not in frontmatter


def test_readiness_state_precedence_and_material_gates() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    not_assessable = _section(text, "### Not assessable", "### Needs targeted follow-up")
    needs_follow_up = _section(text, "### Needs targeted follow-up", "### Ready")
    ready = text[text.index("### Ready") : text.index("This label gates the assessment")]

    assert "too sparse" in not_assessable
    for status in ("Unknown", "user-stated-unverified", "conflict-needs-confirmation"):
        assert status in needs_follow_up
    assert "ownership and scope are grounded" in ready
    assert "quantitative claim" in ready
    assert "qualitative outcome" in ready
    assert "unsupported metric" in text


def test_readiness_does_not_treat_unknown_as_a_pass() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    ready = text[text.index("### Ready") : text.index("This label gates the assessment")]

    assert "not merely stated in a document or left `Unknown`" in ready
    assert "unverified quantitative claim keeps readiness" in ready


if __name__ == "__main__":
    for test in (
        test_frontmatter_describes_adaptive_deep_dive,
        test_readiness_state_precedence_and_material_gates,
        test_readiness_does_not_treat_unknown_as_a_pass,
    ):
        test()
    print("OK: 3 mock-interviewer contract tests passed")
