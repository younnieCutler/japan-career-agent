"""Regression checks for the Jiko Bunseki v2 raw-response contract."""

import re
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CHECKLIST = ROOT / "skills" / "jiko-bunseki" / "checklist.html"
CHECKLIST_RUNTIME = ROOT / "skills" / "jiko-bunseki" / "checklist_runtime.js"
SCHEMA = ROOT / "_shared" / "schemas.yml"
MATCHING = ROOT / "_shared" / "matching_v3.py"
PROFILE = ROOT / "_shared" / "self_analysis_profile.py"
CAREER_AGENT = ROOT / "skills" / "career-agent" / "career_agent.py"

_matching_spec = spec_from_file_location("matching_v3_contract_target", MATCHING)
if _matching_spec is None or _matching_spec.loader is None:
    raise ImportError(f"cannot load {MATCHING}")
v3 = module_from_spec(_matching_spec)
_matching_spec.loader.exec_module(v3)

_profile_spec = spec_from_file_location("self_analysis_profile_contract_target", PROFILE)
if _profile_spec is None or _profile_spec.loader is None:
    raise ImportError(f"cannot load {PROFILE}")
profile = module_from_spec(_profile_spec)
_profile_spec.loader.exec_module(profile)

BEHAVIOR_IDS = {
    "initiative", "execution", "discipline", "ownership", "analysis", "learning",
    "strategy", "empathy", "harmony", "communication", "support", "confidence",
}
ENVIRONMENT_IDS = {
    "autonomy", "competence", "relatedness", "structure_preference", "speed_preference",
    "change_tolerance", "collaboration_preference", "feedback_frequency",
}


def test_v2_submission_has_independent_unknown_safe_controls() -> None:
    source = "\n".join([
        CHECKLIST.read_text(encoding="utf-8"),
        CHECKLIST_RUNTIME.read_text(encoding="utf-8"),
    ])
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
    assert 'type="range"' in source
    assert 'data-touched="false"' in source
    assert "dataset.touched === 'true'" in source
    assert "data-scale-unknown" in source
    assert 'name="${namePrefix}.${item.id}"' in source


def test_checklist_activity_ids_match_profile_validator() -> None:
    source = CHECKLIST.read_text(encoding="utf-8")
    ids = re.findall(r'name="interest_activities" value="([^"]+)"', source)
    assert len(ids) == len(set(ids))
    assert set(ids) == profile.ACTIVITY_IDS


def test_unanswered_and_explicit_unknown_remain_distinct() -> None:
    source = CHECKLIST_RUNTIME.read_text(encoding="utf-8")
    assert "if (selection === undefined)" in source
    assert "if (selection === \"unknown\")" in source
    assert "function collectText" in source
    assert "career_self_efficacy.outcome_expectation" in source
    assert "career_self_efficacy.goal" in source


def test_learning_confidence_uses_shared_scale_export_path() -> None:
    source = CHECKLIST.read_text(encoding="utf-8")
    assert "function scaleSelection(prefix, id)" in source
    assert "items.map(item => [item.id, scaleSelection(prefix, item.id)])" in source
    assert "scaleSelection('career_self_efficacy', 'learning_confidence')" in source
    assert 'input[name="career_self_efficacy.learning_confidence"]:checked' not in source


def test_checklist_is_local_bilingual_and_does_not_calculate_results() -> None:
    source = "\n".join([
        CHECKLIST.read_text(encoding="utf-8"),
        CHECKLIST_RUNTIME.read_text(encoding="utf-8"),
    ])
    assert "function nextStep" in source
    assert "function prevStep" in source
    assert "한국어" in source and "日本語" in source
    assert "navigator.clipboard" in source
    for forbidden in (
        "fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "fit score", "personality", "diagnos",
        "occupation recommendation", "company recommendation", "hiring probability",
    ):
        assert forbidden.lower() not in source.lower(), forbidden


def test_user_facing_language_spans_are_not_cross_contaminated() -> None:
    source = CHECKLIST.read_text(encoding="utf-8")
    japanese_spans = re.findall(r'<span class="ja">([^<]*)</span>', source)
    korean_spans = re.findall(r'<span class="ko">([^<]*)</span>', source)
    assert japanese_spans
    assert korean_spans
    assert all(not re.search(r"[가-힣]", text) for text in japanese_spans)
    assert all(not re.search(r"[ぁ-ヿ]", text) for text in korean_spans)
    assert "표시してください" not in source


def test_profile_schema_is_v2_and_keeps_legacy_read_compatibility() -> None:
    schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    profile = schema["self_analysis_profile"]
    assert schema["schema_version"] == "2.5"
    assert {
        "self_analysis_version", "candidate_name", "language_preference", "track",
        "interest_hypotheses", "behavior_tendencies", "evidence_episodes",
        "career_self_efficacy", "perceived_barriers", "perceived_supports",
        "environment_preferences", "value_candidates", "avoid_candidates",
    } <= set(profile["required"])
    assert profile["optional"]
    pipeline_company = schema["pipeline"]["companies"][0]
    assert "match_required_gaps" in pipeline_company
    assert "match_unknowns" in pipeline_company
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


def test_raw_reflection_cannot_become_candidate_skill_evidence() -> None:
    combined = "\n".join([
        (ROOT / "skills" / "job-seeker-agent" / "SKILL.md").read_text(encoding="utf-8"),
        (ROOT / "skills" / "job-seeker-agent" / "references" / "shinsotsu.md").read_text(encoding="utf-8"),
    ])
    assert "Do not copy raw checklist values into a skill level" in combined
    assert "A perceived barrier is not proof of an actual skill gap" in combined


def test_analysis_tendency_cannot_create_a_matched_requirement() -> None:
    result = v3.evaluate({
        "behavior_tendencies": {"analysis": 5},
        "skills": {"required": [{"name": "analysis", "status": "unknown"}]},
    })
    assert [item["name"] for item in result["skills"]["required_skills"]["unknown"]] == ["analysis"]
    assert result["skills"]["required_skills"]["matched"] == []


def test_interest_activity_has_no_automatic_occupation_output() -> None:
    source = CHECKLIST.read_text(encoding="utf-8").lower()
    assert "interest_activities" in source
    assert "occupation recommendation" not in source
    assert "recommended_occupation" not in source
    assert "recommended_company" not in source


def test_value_candidates_require_confirmation_before_canonical_context() -> None:
    jiko = (ROOT / "skills" / "jiko-bunseki" / "SKILL.md").read_text(encoding="utf-8")
    questions = (ROOT / "skills" / "jiko-bunseki" / "references" / "questions.md").read_text(encoding="utf-8")
    career_agent = CAREER_AGENT.read_text(encoding="utf-8")
    assert "require a direct user statement" in jiko
    assert "only after the user explicitly confirms" in questions
    assert 'CAREER_CONTEXT_FIELDS = ("career_anchors", "career_theme", "energy_map", "career_values")' in career_agent
    assert "value_candidates" not in career_agent


def test_perceived_skill_gap_is_not_an_actual_missing_skill() -> None:
    questions = (ROOT / "skills" / "jiko-bunseki" / "references" / "questions.md").read_text(encoding="utf-8")
    assert "Perceived difficulty is a self-report, not evidence of an actual deficit." in questions
    assert "perceived_barriers" in questions
    assert "skill" in questions


def test_legacy_v1_profile_is_read_only_and_not_converted() -> None:
    schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    compatibility = schema["legacy_self_analysis_profile_v1"]
    assert "top_strengths" in compatibility["readable_fields"]
    assert "Do not convert scores" in compatibility["migration"]
    assert "top_strengths" not in schema["self_analysis_profile"]["required"]


def test_raw_jiko_fields_are_not_matching_coefficients() -> None:
    source = MATCHING.read_text(encoding="utf-8")
    for field in (
        "interest_activities", "behavior_tendencies", "career_self_efficacy",
        "perceived_barriers", "environment_preferences", "value_candidates", "avoid_candidates",
    ):
        assert field not in source, field


def test_career_agent_context_allowlist_excludes_raw_reflection() -> None:
    source = CAREER_AGENT.read_text(encoding="utf-8")
    assert 'CAREER_CONTEXT_FIELDS = ("career_anchors", "career_theme", "energy_map", "career_values")' in source
    for field in ("interest_activities", "behavior_tendencies", "perceived_barriers", "value_candidates"):
        assert field not in source, field


if __name__ == "__main__":
    test_v2_submission_has_independent_unknown_safe_controls()
    test_checklist_activity_ids_match_profile_validator()
    test_unanswered_and_explicit_unknown_remain_distinct()
    test_learning_confidence_uses_shared_scale_export_path()
    test_checklist_is_local_bilingual_and_does_not_calculate_results()
    test_user_facing_language_spans_are_not_cross_contaminated()
    test_profile_schema_is_v2_and_keeps_legacy_read_compatibility()
    test_job_seeker_handoff_keeps_reflection_separate_from_evidence()
    test_raw_reflection_cannot_become_candidate_skill_evidence()
    test_analysis_tendency_cannot_create_a_matched_requirement()
    test_interest_activity_has_no_automatic_occupation_output()
    test_value_candidates_require_confirmation_before_canonical_context()
    test_perceived_skill_gap_is_not_an_actual_missing_skill()
    test_legacy_v1_profile_is_read_only_and_not_converted()
    test_raw_jiko_fields_are_not_matching_coefficients()
    test_career_agent_context_allowlist_excludes_raw_reflection()
    print("OK: 16 checklist/profile contract tests passed")
