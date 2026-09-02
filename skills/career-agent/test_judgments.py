#!/usr/bin/env python3
"""Regression tests for the append-only human judgment ledger."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from judgments import (
    JUDGMENT_SCHEMA_VERSION,
    judgment_ledger,
    judgment_timeline,
    list_judgments,
    record_agent_assessment,
    record_final_judgment,
    record_initial_judgment,
    record_outcome,
)
from models import CareerError
from persistence import append_jsonl
from vault import CareerVault


class JudgmentLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.home = CareerVault(Path(self.temporary.name) / "vault")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def initial(self, **changes):
        payload = {
            "subject": "company_fit",
            "target_ref": "application:acme-platform-engineer",
            "impact": "l3",
            "decision": "hold",
            "reasons": ["delivery model is still unclear"],
        }
        payload.update(changes)
        return record_initial_judgment(self.home, **payload)

    def test_full_judgment_stays_separate_from_canonical_career_state(self) -> None:
        initial = self.initial()
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

    def test_agent_cannot_be_recorded_before_human_initial_judgment(self) -> None:
        with self.assertRaises(CareerError) as caught:
            record_agent_assessment(
                self.home,
                "jdg-000000000000",
                recommendation="proceed",
                confidence="low",
            )
        self.assertEqual(caught.exception.code, "JUDGMENT_PHASE_ORDER")
        self.assertFalse(judgment_ledger(self.home).exists())

    def test_phase_is_append_only_and_cannot_be_replaced(self) -> None:
        initial = self.initial(subject="career_direction", target_ref="strategy:next-role", decision="unknown")
        judgment_id = initial["judgment_id"]
        record_agent_assessment(
            self.home,
            judgment_id,
            recommendation="hold",
            confidence="low",
        )

        with self.assertRaises(CareerError) as caught:
            record_agent_assessment(
                self.home,
                judgment_id,
                recommendation="proceed",
                confidence="high",
            )
        self.assertEqual(caught.exception.code, "JUDGMENT_PHASE_EXISTS")
        self.assertEqual(len(judgment_timeline(self.home, judgment_id)), 2)

    def test_unknown_is_an_explicit_decision_not_a_default_score(self) -> None:
        initial = self.initial(subject="offer", target_ref="offer:example", decision="unknown", reasons=[])
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
            self.initial(impact="l2")
        with self.assertRaises(CareerError):
            self.initial(decision="yes")
        self.assertFalse(judgment_ledger(self.home).exists())

    def test_future_schema_is_refused_on_read(self) -> None:
        row = self.initial()
        ledger = judgment_ledger(self.home)
        row["schema_version"] = JUDGMENT_SCHEMA_VERSION + 1
        ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")
        with self.assertRaises(CareerError) as caught:
            list_judgments(self.home)
        self.assertEqual(caught.exception.code, "JUDGMENT_SCHEMA_NEWER")

    def test_unknown_or_out_of_order_persisted_phase_fails_closed(self) -> None:
        initial = self.initial()
        ledger = judgment_ledger(self.home)
        bad = dict(initial)
        bad.update({"phase": "human_final", "decision": "proceed", "reasons": [], "source": "human"})
        append_jsonl(ledger, bad)
        with self.assertRaises(CareerError) as caught:
            list_judgments(self.home)
        self.assertEqual(caught.exception.code, "STATE_CORRUPTED")

        ledger.write_text(
            ledger.read_text(encoding="utf-8").replace('"human_final"', '"bogus_phase"'),
            encoding="utf-8",
        )
        with self.assertRaises(CareerError) as caught:
            list_judgments(self.home)
        self.assertEqual(caught.exception.code, "STATE_CORRUPTED")

    def test_duplicate_persisted_phase_fails_closed_instead_of_last_write_wins(self) -> None:
        initial = self.initial()
        append_jsonl(judgment_ledger(self.home), dict(initial))
        with self.assertRaises(CareerError) as caught:
            list_judgments(self.home)
        self.assertEqual(caught.exception.code, "STATE_CORRUPTED")

    def test_non_object_row_and_malformed_id_fail_closed(self) -> None:
        ledger = judgment_ledger(self.home)
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text("[]\n", encoding="utf-8")
        with self.assertRaises(CareerError):
            list_judgments(self.home)

        ledger.write_text(
            '{"schema_version":1,"judgment_id":"broken","phase":"human_initial",'
            '"subject":"company_fit","target_ref":"application:x","impact":"l3",'
            '"decision":"hold","reasons":[],"created_at":"2026-09-02T00:00:00Z","source":"human"}\n',
            encoding="utf-8",
        )
        with self.assertRaises(CareerError) as caught:
            list_judgments(self.home)
        self.assertEqual(caught.exception.code, "STATE_CORRUPTED")

    def test_concurrent_same_phase_append_allows_exactly_one_writer(self) -> None:
        initial = self.initial()
        barrier = threading.Barrier(2)

        def write_agent(recommendation: str):
            barrier.wait(timeout=5)
            try:
                return record_agent_assessment(
                    self.home,
                    initial["judgment_id"],
                    recommendation=recommendation,
                    confidence="medium",
                )
            except CareerError as exc:
                return exc

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write_agent, ("proceed", "hold")))

        successes = [value for value in results if isinstance(value, dict)]
        failures = [value for value in results if isinstance(value, CareerError)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].code, "JUDGMENT_PHASE_EXISTS")
        self.assertEqual(len(judgment_timeline(self.home, initial["judgment_id"])), 2)


if __name__ == "__main__":
    unittest.main()
