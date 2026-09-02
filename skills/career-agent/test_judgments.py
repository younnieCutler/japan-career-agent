#!/usr/bin/env python3
"""Regression tests for the append-only human judgment ledger."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from judgments import (
    judgment_ledger,
    judgment_timeline,
    list_judgments,
    record_agent_assessment,
    record_final_judgment,
    record_initial_judgment,
    record_outcome,
)
from models import CareerError
from vault import CareerVault


class JudgmentLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.home = CareerVault(Path(self.temporary.name) / "vault")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_full_judgment_stays_separate_from_canonical_career_state(self) -> None:
        initial = record_initial_judgment(
            self.home,
            subject="company_fit",
            target_ref="application:acme-platform-engineer",
            impact="l3",
            decision="hold",
            reasons=["delivery model is still unclear"],
        )
        judgment_id = initial["judgment_id"]

        record_agent_assessment(
            self.home,
            judgment_id,
            recommendation="proceed",
            confidence="medium",
            reasons=["role scope matches confirmed experience"],
            evidence_refs=["experience:platform-migration"],
            unknowns=["actual project allocation ratio"],
        )
        record_final_judgment(
            self.home,
            judgment_id,
            decision="hold",
            reasons=["verify allocation before applying"],
        )
        record_outcome(
            self.home,
            judgment_id,
            outcome="unknown",
            notes="waiting for recruiter clarification",
        )

        rows = judgment_timeline(self.home, judgment_id)
        self.assertEqual(
            [row["phase"] for row in rows],
            ["human_initial", "agent_assessment", "human_final", "outcome"],
        )
        self.assertEqual(len(judgment_ledger(self.home).read_text(encoding="utf-8").splitlines()), 4)
        self.assertFalse(self.home.events.exists())
        self.assertFalse(self.home.proposals.exists())
        self.assertFalse(self.home.state_toml.exists())

        projected = list_judgments(self.home)
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]["human_initial"], "hold")
        self.assertEqual(projected[0]["agent_recommendation"], "proceed")
        self.assertEqual(projected[0]["human_final"], "hold")
        self.assertTrue(projected[0]["human_agent_diverged"])
        self.assertTrue(projected[0]["complete"])
        self.assertFalse(projected[0]["outcome_known"])

    def test_agent_cannot_be_shown_as_recorded_before_human_initial_judgment(self) -> None:
        with self.assertRaises(CareerError) as caught:
            record_agent_assessment(
                self.home,
                "jdg-missing",
                recommendation="proceed",
                confidence="low",
            )
        self.assertEqual(caught.exception.code, "JUDGMENT_PHASE_ORDER")
        self.assertFalse(judgment_ledger(self.home).exists())

    def test_phase_is_append_only_and_cannot_be_replaced(self) -> None:
        initial = record_initial_judgment(
            self.home,
            subject="career_direction",
            target_ref="strategy:next-role",
            impact="l3",
            decision="unknown",
        )
        judgment_id = initial["judgment_id"]
        with self.assertRaises(CareerError) as caught:
            # A second initial answer would rewrite history semantically even if appended physically.
            # The ledger refuses it instead of inventing implicit supersession rules.
            from judgments import _require_phase_sequence

            _require_phase_sequence(self.home, judgment_id, "human_initial")
        self.assertEqual(caught.exception.code, "JUDGMENT_PHASE_EXISTS")
        self.assertEqual(len(judgment_timeline(self.home, judgment_id)), 1)

    def test_unknown_is_an_explicit_decision_not_a_default_score(self) -> None:
        initial = record_initial_judgment(
            self.home,
            subject="offer",
            target_ref="offer:example",
            impact="l3",
            decision="unknown",
            reasons=[],
        )
        record_agent_assessment(
            self.home,
            initial["judgment_id"],
            recommendation="unknown",
            confidence="unknown",
            unknowns=["total compensation", "team mandate"],
        )
        projection = list_judgments(self.home)[0]
        self.assertEqual(projection["human_initial"], "unknown")
        self.assertEqual(projection["agent_recommendation"], "unknown")
        self.assertFalse(projection["human_agent_diverged"])
        self.assertFalse(projection["complete"])

    def test_invalid_impact_and_decision_are_rejected_before_write(self) -> None:
        with self.assertRaises(CareerError):
            record_initial_judgment(
                self.home,
                subject="application",
                target_ref="application:x",
                impact="critical",
                decision="proceed",
            )
        with self.assertRaises(CareerError):
            record_initial_judgment(
                self.home,
                subject="application",
                target_ref="application:x",
                impact="l3",
                decision="yes",
            )
        self.assertFalse(judgment_ledger(self.home).exists())


if __name__ == "__main__":
    unittest.main()
