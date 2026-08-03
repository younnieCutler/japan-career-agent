#!/usr/bin/env python3
"""Regression checks for the Jiko Bunseki v2 raw-response contract."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
CHECKLIST = ROOT / "skills" / "jiko-bunseki" / "checklist.html"
SCHEMA = ROOT / "_shared" / "schemas.yml"


BEHAVIOR_IDS = {
    "initiative", "execution", "discipline", "ownership", "analysis", "learning",
    "strategy", "empathy", "harmony", "communication", "support", "confidence",
}
ENVIRONMENT_IDS = {
    "autonomy", "competence", "relatedness", "structure_preference", "speed_preference",
    "change_tolerance", "collaboration_preference", "feedback_frequency",
}


def test_v2_submission_has_independent_unknown_safe_controls() -> None:
    source = CHECKLIST.read_text(encoding="utf-8")
    for item_id in BEHAVIOR_IDS | ENVIRONMENT_IDS:
        assert f'id: "{item_id}"' in source, item_id
    assert "submission_version: 2" in source
    assert "behavior_tendencies" in source
    assert "environment_preferences" in source
    assert "unanswered_fields" in source
    assert "explicit_unknown_fields" in source
    assert 'value="unknown"' in source
    assert "const PAIRS" not in source
    assert "strength_pairs" not in source
    assert 'input type="range"' not in source


def test_checklist_is_local_bilingual_and_does_not_calculate_results() -> None:
    source = CHECKLIST.read_text(encoding="utf-8")
    assert "function nextStep" in source
    assert "function prevStep" in source
    assert "한국어" in source and "日本語" in source
    assert "navigator.clipboard" in source
    for forbidden in ("fetch(", "XMLHttpRequest", "WebSocket", "fit score", "personality", "diagnos"):
        assert forbidden.lower() not in source.lower(), forbidden


def test_profile_schema_is_v2_and_keeps_legacy_read_compatibility() -> None:
    schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    profile = schema["self_analysis_profile"]
    assert schema["schema_version"] == "2.2"
    assert {
        "self_analysis_version", "candidate_name", "language_preference", "track",
        "interest_hypotheses", "behavior_tendencies", "evidence_episodes",
        "career_self_efficacy", "perceived_barriers", "perceived_supports",
        "environment_preferences", "value_candidates", "avoid_candidates",
    } <= set(profile["required"])
    assert profile["optional"]
    compatibility = schema["legacy_self_analysis_profile_v1"]
    assert compatibility["readable_fields"]
    assert "Do not convert" in compatibility["migration"]


def test_job_seeker_handoff_keeps_reflection_separate_from_evidence() -> None:
    skill = (ROOT / "skills" / "job-seeker-agent" / "SKILL.md").read_text(encoding="utf-8")
    shinsotsu = (ROOT / "skills" / "job-seeker-agent" / "references" / "shinsotsu.md").read_text(encoding="utf-8")
    combined = f"{skill}\n{shinsotsu}"
    assert "not professional evidence" in combined
    assert "analysis = 5" in combined
    assert "value_candidates" in combined


if __name__ == "__main__":
    test_v2_submission_has_independent_unknown_safe_controls()
    test_checklist_is_local_bilingual_and_does_not_calculate_results()
    test_profile_schema_is_v2_and_keeps_legacy_read_compatibility()
    test_job_seeker_handoff_keeps_reflection_separate_from_evidence()
    print("OK: 4 checklist/profile contract tests passed")
