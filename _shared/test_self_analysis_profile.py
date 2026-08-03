"""Deterministic SELF_ANALYSIS_PROFILE v2 validation tests."""

from __future__ import annotations

import copy
import unittest

import self_analysis_profile as profile


def valid_profile() -> dict:
    return {
        "self_analysis_version": 2,
        "candidate_name": "Test User",
        "language_preference": "ko",
        "track": "chuto",
        "interest_hypotheses": [],
        "behavior_tendencies": [],
        "evidence_episodes": [],
        "career_self_efficacy": {
            "learning_confidence": None,
            "outcome_expectation": None,
            "goal": None,
        },
        "perceived_barriers": None,
        "perceived_supports": None,
        "environment_preferences": {
            "autonomy": None,
            "competence": None,
            "relatedness": None,
            "structure_preference": None,
            "speed_preference": None,
            "change_tolerance": None,
            "collaboration_preference": None,
            "feedback_frequency": None,
        },
        "value_candidates": [],
        "avoid_candidates": [],
    }


class SelfAnalysisProfileTests(unittest.TestCase):
    def test_valid_profile_preserves_null_and_reviewed_empty_list(self) -> None:
        value = valid_profile()
        self.assertEqual(profile.validate_self_analysis_profile(value), value)
        self.assertIsNone(value["perceived_barriers"])
        self.assertEqual(value["value_candidates"], [])

    def test_version_and_enums_are_strict(self) -> None:
        for field, invalid in (("self_analysis_version", 1), ("language_preference", "ja-JP"), ("track", "other")):
            value = valid_profile()
            value[field] = invalid
            with self.subTest(field=field):
                with self.assertRaises(profile.ProfileValidationError):
                    profile.validate_self_analysis_profile(value)

    def test_scale_and_tendency_shape_are_strict(self) -> None:
        value = valid_profile()
        value["behavior_tendencies"] = [{
            "name": "analysis",
            "self_report": 6,
            "response_basis": "user said so",
            "evidence_episode_refs": [],
            "confidence": "high",
        }]
        with self.assertRaises(profile.ProfileValidationError):
            profile.validate_self_analysis_profile(value)

    def test_raw_submission_is_not_a_canonical_profile(self) -> None:
        value = valid_profile()
        value.update({"jiko_bunseki_submission": True, "submission_version": 2})
        with self.assertRaisesRegex(profile.ProfileValidationError, "raw checklist fields"):
            profile.validate_self_analysis_profile(value)

    def test_confirmed_career_values_require_confirmation_flag(self) -> None:
        value = valid_profile()
        value["career_values"] = {"must_have": ["autonomy"], "avoid": []}
        with self.assertRaisesRegex(profile.ProfileValidationError, "career_context_confirmed"):
            profile.validate_self_analysis_profile(value)

        value["career_context_confirmed"] = True
        self.assertEqual(profile.validate_self_analysis_profile(value), value)

    def test_validation_does_not_migrate_or_fill_legacy_values(self) -> None:
        legacy = {"top_strengths": [{"name": "analysis", "score": 5}]}
        with self.assertRaises(profile.ProfileValidationError):
            profile.validate_self_analysis_profile(legacy)
        self.assertEqual(legacy, {"top_strengths": [{"name": "analysis", "score": 5}]})

    def test_validation_does_not_mutate_nested_values(self) -> None:
        value = valid_profile()
        before = copy.deepcopy(value)
        profile.validate_self_analysis_profile(value)
        self.assertEqual(value, before)


if __name__ == "__main__":
    unittest.main()
