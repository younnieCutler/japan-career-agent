#!/usr/bin/env python3
"""Focused executable-schema and legacy-write contract tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_shared"))

from schema_contract import SchemaContractError, load_catalog, validate_document, validate_new_write  # noqa: E402


class SchemaContractTests(unittest.TestCase):
    def test_catalog_has_all_canonical_definitions(self) -> None:
        catalog = load_catalog()
        self.assertEqual(
            {"SELF_ANALYSIS_PROFILE", "CANDIDATE_PROFILE", "COMPANY_PROFILE", "MATCH_HISTORY", "PIPELINE", "RULES"},
            set(catalog["$defs"]),
        )

    def test_representative_documents_validate(self) -> None:
        profile = {
            "self_analysis_version": 2,
            "candidate_name": "candidate",
            "language_preference": "ko",
            "track": "chuto",
            "interest_hypotheses": None,
            "behavior_tendencies": None,
            "evidence_episodes": None,
            "career_self_efficacy": None,
            "perceived_barriers": None,
            "perceived_supports": None,
            "environment_preferences": None,
            "value_candidates": None,
            "avoid_candidates": None,
        }
        validate_document("SELF_ANALYSIS_PROFILE", profile)
        validate_document("CANDIDATE_PROFILE", {
            "candidate_name": "candidate",
            "work_style_reflection": {},
            "skill_stack": [],
            "target_role": "Data Engineer",
            "jlpt_level": None,
        })
        validate_document("COMPANY_PROFILE", {"company_name": "A", "position": "Engineer", "required_skills": []})
        validate_document("MATCH_HISTORY", [])
        validate_document("PIPELINE", {"companies": []})
        validate_document("RULES", [])

    def test_missing_shape_and_legacy_new_write_are_rejected(self) -> None:
        with self.assertRaises(SchemaContractError):
            validate_document("PIPELINE", {"companies": [{"name": "missing slug"}]})
        with self.assertRaises(SchemaContractError):
            validate_new_write("CANDIDATE_PROFILE", {
                "candidate_name": "candidate",
                "work_style_reflection": {},
                "skill_stack": [],
                "target_role": "Engineer",
                "jlpt_level": None,
                "overall_score": 80,
            })


if __name__ == "__main__":
    unittest.main()
