#!/usr/bin/env python3
"""Regression tests for deterministic review policy and the production judgment adapter."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import case_store
from gui import judgments as gui_judgments
from models import CareerError
from review_policy import judgment_policy, policy_catalog, policy_for
from vault import CareerVault, initialize_vault


class ReviewPolicyTests(unittest.TestCase):
    def test_policy_levels_are_deterministic_and_unknown_operations_fail_closed(self) -> None:
        self.assertEqual(policy_for("read_only")["impact"], "l0")
        self.assertEqual(policy_for("recoverable_local_write")["impact"], "l1")
        self.assertEqual(policy_for("canonical_career_change")["impact"], "l2")
        self.assertEqual(policy_for("consequential_decision")["impact"], "l3")
        self.assertTrue(judgment_policy("application")["requires_human_judgment"])
        self.assertEqual(set(policy_catalog()), {
            "read_only", "recoverable_local_write", "canonical_career_change", "consequential_decision"
        })
        with self.assertRaises(CareerError) as caught:
            policy_for("caller_says_low_risk")
        self.assertEqual(caught.exception.code, "REVIEW_POLICY_UNKNOWN")


class JudgmentGuiAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name) / "vault"
        initialize_vault(root)
        self.home = CareerVault(root)
        company = case_store.create_company(self.home, "Acme")
        self.application = case_store.create_application(
            self.home, company["case_id"], "Platform Engineer"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_application_initial_judgment_uses_server_policy_not_client_impact(self) -> None:
        result = gui_judgments.start(self.home, {
            "subject": "application",
            "target_ref": self.application["case_id"],
            "decision": "hold",
            "reasons": ["allocation is unclear"],
        })
        self.assertEqual(result["impact"], "l3")
        self.assertEqual(result["policy"]["interaction"], "human_first")
        self.assertEqual(result["human_initial"]["decision"], "hold")

        with self.assertRaises(CareerError) as caught:
            gui_judgments.start(self.home, {
                "subject": "application",
                "target_ref": self.application["case_id"],
                "impact": "l1",
                "decision": "proceed",
            })
        self.assertEqual(caught.exception.code, "INVALID_INPUT")

    def test_application_subject_rejects_a_non_application_target(self) -> None:
        company = case_store.create_company(self.home, "Wrong target")
        with self.assertRaises(CareerError) as caught:
            gui_judgments.start(self.home, {
                "subject": "application",
                "target_ref": company["case_id"],
                "decision": "unknown",
            })
        self.assertEqual(caught.exception.code, "INVALID_RELATIONSHIP")

    def test_browser_projection_never_exposes_unresolved_evidence_refs(self) -> None:
        started = gui_judgments.start(self.home, {
            "subject": "application",
            "target_ref": self.application["case_id"],
            "decision": "hold",
        })
        assessed = gui_judgments.assess(self.home, {
            "judgment_id": started["judgment_id"],
            "recommendation": "proceed",
            "confidence": "medium",
            "reasons": ["role scope fits"],
            "evidence_refs": ["experience:not-resolved-yet"],
            "unknowns": ["project allocation"],
        })
        self.assertEqual(assessed["agent_assessment"]["evidence_ref_count"], 1)
        self.assertNotIn("evidence_refs", assessed["agent_assessment"])
        rendered = json.dumps(gui_judgments.payload(
            self.home, target_ref=self.application["case_id"]
        ))
        self.assertNotIn("experience:not-resolved-yet", rendered)

    def test_final_and_outcome_stay_out_of_canonical_career_state(self) -> None:
        started = gui_judgments.start(self.home, {
            "subject": "application",
            "target_ref": self.application["case_id"],
            "decision": "unknown",
        })
        gui_judgments.assess(self.home, {
            "judgment_id": started["judgment_id"],
            "recommendation": "hold",
            "confidence": "low",
        })
        finalized = gui_judgments.finalize(self.home, {
            "judgment_id": started["judgment_id"],
            "decision": "hold",
            "reasons": ["verify first"],
        })
        self.assertEqual(finalized["human_final"]["decision"], "hold")
        result = gui_judgments.record_result(self.home, {
            "judgment_id": started["judgment_id"],
            "outcome": "unknown",
            "notes": "waiting",
        })
        self.assertEqual(result["outcome"]["value"], "unknown")
        self.assertFalse(self.home.events.exists())
        self.assertFalse(self.home.proposals.exists())


if __name__ == "__main__":
    unittest.main()
