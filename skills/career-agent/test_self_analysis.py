"""Contract tests for the read-only self-analysis projection and handoff."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CAREER_ROOT = ROOT / "skills" / "career-agent"
SHARED_ROOT = ROOT / "_shared"
for path in (CAREER_ROOT, SHARED_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import self_analysis  # noqa: E402


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


class SelfAnalysisProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        (self.workspace / "data").mkdir()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_profile(self, value: dict) -> Path:
        path = self.workspace / "data" / "self_analysis_profile.yml"
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def test_missing_profile_keeps_every_field_unknown_and_offers_user_led_handoff(self) -> None:
        result = self_analysis.profile_payload(self.workspace)

        self.assertEqual(result["state"], "unknown")
        self.assertIsNone(result["profile"])
        self.assertTrue(result["field_status"])
        self.assertTrue(all(row["status"] == "Unknown" for row in result["field_status"]))
        self.assertEqual(result["handoff"]["skill"], "jiko-bunseki")
        self.assertFalse(result["handoff"]["available"])

    def test_valid_profile_is_read_only_independent_and_approval_gated(self) -> None:
        profile = valid_profile()
        profile["evidence_episodes"] = [{
            "id": "episode-private-id",
            "experience_type": "project",
            "situation": "A project needed structure",
            "action": "I organized the work",
            "energy_effect": "energizing",
            "energy_reason": None,
            "source_type": "user",
            "confidence": "high",
        }]
        path = self.write_profile(profile)
        before = path.read_bytes()

        result = self_analysis.profile_payload(self.workspace)
        after = path.read_bytes()

        self.assertEqual(before, after)
        self.assertEqual(result["state"], "available")
        self.assertEqual(result["profile"]["candidate_name"], "Test User")
        statuses = {row["field"]: row["status"] for row in result["field_status"]}
        self.assertEqual(statuses["career_self_efficacy"], "Unknown")
        self.assertEqual(statuses["value_candidates"], "Reviewed empty")
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("episode-private-id", encoded)
        self.assertNotIn("percentage", encoded.casefold())
        self.assertTrue(result["handoff"]["available"])
        self.assertTrue(result["handoff"]["approval_required"])
        self.assertIn("propose-context", result["handoff"]["command"])
        self.assertIn("--source data/self_analysis_profile.yml", result["handoff"]["command"])

    def test_raw_checklist_submission_is_unavailable_not_promoted(self) -> None:
        profile = valid_profile()
        profile.update({"jiko_bunseki_submission": True, "submission_version": 2})
        self.write_profile(profile)

        result = self_analysis.profile_payload(self.workspace)

        self.assertEqual(result["state"], "invalid")
        self.assertIsNone(result["profile"])
        self.assertEqual(result["reason"], "invalid canonical profile")
        self.assertNotIn("jiko_bunseki_submission", json.dumps(result))

    def test_handoff_does_not_claim_canonical_confirmation(self) -> None:
        profile = valid_profile()
        profile["career_values"] = {"must_have": ["autonomy"], "avoid": []}
        profile["career_context_confirmed"] = True
        self.write_profile(profile)

        result = self_analysis.profile_payload(self.workspace)

        self.assertTrue(result["handoff"]["approval_required"])
        self.assertFalse(result["handoff"]["canonical_write_performed"])


if __name__ == "__main__":
    unittest.main()
