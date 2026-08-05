#!/usr/bin/env python3
"""Personal fact timeline and projection tests.

Covers docs/PRIVATE_CAREER_DATA_PRD.md phase 3 exit criteria: AC-08, AC-10, AC-14, AC-15, AC-21,
AC-22, AC-26. All fixtures are synthetic (AC-06).

    synthetic://test-fixtures
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import personal_timeline  # noqa: E402
import vault as vault_module  # noqa: E402
from models import CareerError  # noqa: E402
from validation import iso_date, validate_event  # noqa: E402


def event(event_id: str, category: str, key: str, value, **fact_fields) -> dict:
    """A confirmed ledger event carrying one personal fact."""
    fact = {"category": category, "key": key, "value": value}
    fact.update(fact_fields)
    return {
        "id": event_id,
        "track": "chuto",
        "stage": "面接",
        "flow_phase": "explore",
        "type": "fact",
        "occurred_at": "2026-08-05T10:00:00Z",
        "title": f"synthetic {key}",
        "summary": "synthetic fixture",
        "evidence": [f"doc_{event_id}"],
        "source": "synthetic",
        "next_action": None,
        "deadline": None,
        "status": "confirmed",
        "fact": fact,
    }


class ProjectionTest(unittest.TestCase):
    def test_current_value_is_selected_for_the_as_of_date(self) -> None:
        events = [
            event("f1", "compensation", "base", 6100000, effective_from="2025-04-01"),
            event("f2", "compensation", "base", 7200000, effective_from="2026-04-01",
                  supersedes="f1"),
        ]
        current = personal_timeline.project(events, "2026-08-05")["compensation"]["base"]
        self.assertEqual(current["state"], "confirmed")
        self.assertEqual(current["value"], 7200000)

        earlier = personal_timeline.project(events, "2025-06-01")["compensation"]["base"]
        self.assertEqual(earlier["value"], 6100000, "the older fact is current for an older as_of")

    def test_a_draft_successor_does_not_retire_a_confirmed_fact(self) -> None:
        """An unapproved proposal must not route a state change around the approval gate."""
        proposed = event("f2", "compensation", "base", 7200000,
                         effective_from="2026-04-01", supersedes="f1")
        proposed["status"] = "draft"
        events = [event("f1", "compensation", "base", 6100000, effective_from="2025-04-01"),
                  proposed]
        field = personal_timeline.project(events, "2026-08-05")["compensation"]["base"]
        self.assertEqual(field["state"], "confirmed")
        self.assertEqual(field["value"], 6100000, "the confirmed value stands until approval")
        history = {row["fact_id"]: row for row in
                   personal_timeline.timeline(events, "compensation", "base")}
        self.assertIsNone(history["f1"]["effective_to"])
        self.assertEqual(history["f1"]["status"], "confirmed")

    def test_unknown_never_borrows_from_history(self) -> None:
        """AC-08: historical compensation exists, so `value` must still be null."""
        events = [event("f1", "compensation", "base", 4800000,
                        effective_from="2023-04-01", expires_on="2023-12-31")]
        field = personal_timeline.project(events, "2026-08-05")["compensation"]["base"]
        self.assertEqual(field["state"], "unknown")
        self.assertIsNone(field["value"])
        self.assertTrue(field["history_available"])
        self.assertNotIn("4800000", repr(field["value"]))

    def test_expired_certificate_is_not_currently_valid(self) -> None:
        """AC-10."""
        events = [event("f1", "certification", "synthetic-cert", "Level 1",
                        effective_from="2022-01-01", expires_on="2025-01-01")]
        field = personal_timeline.project(events, "2026-08-05")["certification"]["synthetic-cert"]
        self.assertEqual(field["state"], "unknown")
        self.assertEqual(field["reason"], personal_timeline.UNKNOWN_EXPIRED)
        # But it stays visible in history.
        history = personal_timeline.timeline(events, "certification", "synthetic-cert")
        self.assertEqual(history[0]["value"], "Level 1")

    def test_draft_facts_are_not_projected(self) -> None:
        """Section 12.1 rule 1: a proposal the user has not accepted is not a current fact."""
        draft = event("f1", "language", "jlpt", "N1", effective_from="2026-01-20")
        draft["status"] = "draft"
        field = personal_timeline.project([draft], "2026-08-05")["language"]["jlpt"]
        self.assertEqual(field["state"], "unknown")

    def test_a_fact_effective_after_as_of_is_not_current(self) -> None:
        events = [event("f1", "language", "jlpt", "N1", effective_from="2026-12-01")]
        field = personal_timeline.project(events, "2026-08-05")["language"]["jlpt"]
        self.assertEqual(field["state"], "unknown")
        self.assertEqual(field["reason"], personal_timeline.UNKNOWN_NOT_YET)

    def test_identical_values_are_one_value_not_a_conflict(self) -> None:
        events = [
            event("f1", "language", "jlpt", "N1", effective_from="2026-01-20"),
            event("f2", "language", "jlpt", "N1", effective_from="2026-03-01"),
        ]
        field = personal_timeline.project(events, "2026-08-05")["language"]["jlpt"]
        self.assertEqual(field["state"], "confirmed")
        self.assertEqual(field["evidence"], ["doc_f1", "doc_f2"], "evidence merges")

    def test_two_different_values_at_the_same_time_conflict(self) -> None:
        events = [
            event("f1", "language", "jlpt", "N1", effective_from="2026-01-20"),
            event("f2", "language", "jlpt", "N2", effective_from="2026-01-20"),
        ]
        field = personal_timeline.project(events, "2026-08-05")["language"]["jlpt"]
        self.assertEqual(field["state"], "conflict")
        self.assertIsNone(field["value"], "a consumer reading value gets null, not a wrong answer")
        self.assertEqual(len(field["candidates"]), 2)

    def test_candidates_are_capped(self) -> None:
        """Section 12.1: the personal path is not the unbounded exception."""
        events = [
            event(f"f{index}", "skill", "synthetic", f"value-{index}", effective_from="2026-01-01")
            for index in range(personal_timeline.MAX_CANDIDATES + 3)
        ]
        field = personal_timeline.project(events, "2026-08-05")["skill"]["synthetic"]
        self.assertEqual(len(field["candidates"]), personal_timeline.MAX_CANDIDATES)

    def test_keys_are_independent(self) -> None:
        events = [
            event("f1", "language", "jlpt", "N1", effective_from="2026-01-20"),
            event("f2", "certification", "synthetic-cert", "Level 2", effective_from="2026-02-01"),
        ]
        projection = personal_timeline.project(events, "2026-08-05")
        self.assertEqual(projection["language"]["jlpt"]["state"], "confirmed")
        self.assertEqual(projection["certification"]["synthetic-cert"]["state"], "confirmed")


class SupersessionTest(unittest.TestCase):
    def test_interval_is_derived_from_the_successor(self) -> None:
        """AC-26: `effective_to` is the day before the successor's `effective_from`."""
        events = [
            event("f1", "language", "jlpt", "N2", effective_from="2024-07-01"),
            event("f2", "language", "jlpt", "N1", effective_from="2026-01-20", supersedes="f1"),
        ]
        history = {row["fact_id"]: row for row in personal_timeline.timeline(events, "language", "jlpt")}
        self.assertEqual(history["f1"]["effective_to"], "2026-01-19")
        self.assertEqual(history["f1"]["status"], "superseded")
        self.assertEqual(history["f1"]["superseded_by"], "f2")
        self.assertIsNone(history["f2"]["effective_to"], "the newest record stays open-ended")

    def test_unknown_successor_date_conflicts_instead_of_newest_wins(self) -> None:
        """AC-26 second half: an unorderable supersession is a conflict, not a silent resolution."""
        events = [
            event("f1", "language", "jlpt", "N2", effective_from="2024-07-01"),
            event("f2", "language", "jlpt", "N1", supersedes="f1"),
        ]
        field = personal_timeline.project(events, "2026-08-05")["language"]["jlpt"]
        self.assertEqual(field["state"], "conflict")
        self.assertIsNone(field["value"])
        self.assertEqual({item["value"] for item in field["candidates"]}, {"N1", "N2"})

    def test_conflict_does_not_apply_before_the_older_fact_starts(self) -> None:
        events = [
            event("f1", "language", "jlpt", "N2", effective_from="2024-07-01"),
            event("f2", "language", "jlpt", "N1", supersedes="f1"),
        ]
        field = personal_timeline.project(events, "2023-01-01")["language"]["jlpt"]
        self.assertEqual(field["state"], "unknown")

    def test_superseding_never_deletes(self) -> None:
        events = [
            event("f1", "compensation", "base", 6100000, effective_from="2025-04-01"),
            event("f2", "compensation", "base", 7200000, effective_from="2026-04-01",
                  supersedes="f1"),
        ]
        history = personal_timeline.timeline(events, "compensation", "base")
        self.assertEqual([row["value"] for row in history], [6100000, 7200000])
        self.assertEqual(history[0]["evidence"], ["doc_f1"], "evidence survives supersession")
        self.assertEqual(history[0]["effective_from"], "2025-04-01", "the original date is kept")

    def test_supersedes_an_unknown_fact_is_an_error(self) -> None:
        events = [event("f2", "language", "jlpt", "N1", effective_from="2026-01-20",
                        supersedes="does-not-exist")]
        with self.assertRaises(CareerError):
            personal_timeline.project(events, "2026-08-05")

    def test_self_supersession_is_an_error(self) -> None:
        events = [event("f1", "language", "jlpt", "N1", effective_from="2026-01-20",
                        supersedes="f1")]
        with self.assertRaises(CareerError):
            personal_timeline.project(events, "2026-08-05")


class DeterminismTest(unittest.TestCase):
    def test_same_history_same_as_of_is_identical(self) -> None:
        """AC-15."""
        events = [
            event("f1", "compensation", "base", 6100000, effective_from="2025-04-01"),
            event("f2", "compensation", "base", 7200000, effective_from="2026-04-01",
                  supersedes="f1"),
        ]
        self.assertEqual(
            personal_timeline.project(events, "2026-08-05"),
            personal_timeline.project(list(reversed(events)), "2026-08-05"),
            "ledger order must not change the projection",
        )

    def test_no_function_on_the_projection_path_reads_the_clock(self) -> None:
        """AC-21: changing only the clock must not change the result."""
        events = [event("f1", "language", "jlpt", "N1", effective_from="2026-01-20")]
        baseline = personal_timeline.project(events, "2026-08-05")

        real_today = vault_module.today
        vault_module.today = lambda: dt.date(1999, 1, 1)
        try:
            shifted = personal_timeline.project(events, "2026-08-05")
        finally:
            vault_module.today = real_today
        self.assertEqual(baseline, shifted)

        source = (SCRIPT_DIR / "personal_timeline.py").read_text(encoding="utf-8")
        for forbidden in ("date.today", "datetime.now", "time.time", "utcnow"):
            self.assertNotIn(forbidden, source, f"the projection path must not call {forbidden}")

    def test_as_of_is_required_and_validated(self) -> None:
        with self.assertRaises(CareerError):
            personal_timeline.project([], None)
        with self.assertRaises(CareerError):
            personal_timeline.project([], "2026-99-99")

    def test_projection_rebuilds_from_history_alone(self) -> None:
        """AC-14: the projection is a pure function of the ledger, so a cache is replaceable."""
        events = [
            event("f1", "language", "jlpt", "N2", effective_from="2024-07-01"),
            event("f2", "language", "jlpt", "N1", effective_from="2026-01-20", supersedes="f1"),
            event("f3", "compensation", "base", 7200000, effective_from="2026-04-01"),
        ]
        first = personal_timeline.project(events, "2026-08-05")
        # Nothing is memoized between calls; a second build from the same rows must match.
        self.assertEqual(first, personal_timeline.project(events, "2026-08-05"))
        self.assertEqual(first["language"]["jlpt"]["value"], "N1")


class CalendarValidationTest(unittest.TestCase):
    """AC-22: one value must not be accepted by one path and rejected by another."""

    def test_iso_date_rejects_an_impossible_date(self) -> None:
        with self.assertRaises(CareerError):
            iso_date("2026-13-45", "expires_on")
        self.assertEqual(iso_date("2026-01-20", "expires_on"), "2026-01-20")
        self.assertIsNone(iso_date(None, "expires_on"))

    def test_malformed_expiry_makes_a_note_ineligible_not_eternal(self) -> None:
        note = {
            "kind": "playbook", "agent_read": True, "status": "verified",
            "source_type": "curated_practice", "agent_scope": "chuto",
            "agent_stage": "面接", "expires_on": "2026-13-45",
        }
        self.assertFalse(
            vault_module.context_eligible(note, "chuto", "面接", "2026-08-05"),
            "a typo must not silently mean 'never expires'",
        )
        note["expires_on"] = "2027-01-01"
        self.assertTrue(vault_module.context_eligible(note, "chuto", "面接", "2026-08-05"))

    def test_context_eligibility_uses_as_of_not_the_clock(self) -> None:
        note = {
            "kind": "playbook", "agent_read": True, "status": "verified",
            "source_type": "curated_practice", "agent_scope": "chuto",
            "agent_stage": "面接", "expires_on": "2026-06-30",
        }
        self.assertTrue(vault_module.context_eligible(note, "chuto", "面接", "2026-01-01"))
        self.assertFalse(vault_module.context_eligible(note, "chuto", "面接", "2026-08-05"))

    def test_impossible_occurred_at_is_rejected(self) -> None:
        bad = event("f1", "language", "jlpt", "N1", effective_from="2026-01-20")
        bad["occurred_at"] = "2026-13-45"
        with self.assertRaises(CareerError):
            validate_event(bad)

    def test_impossible_fact_dates_are_rejected(self) -> None:
        with self.assertRaises(CareerError):
            validate_event(event("f1", "language", "jlpt", "N1", effective_from="2026-02-30"))
        with self.assertRaises(CareerError):
            validate_event(event("f1", "language", "jlpt", "N1", expires_on="2026-99-01"))

    def test_hand_authored_effective_to_is_rejected(self) -> None:
        """Section 8.1: a second source of truth for a derived value goes stale silently."""
        with self.assertRaises(CareerError):
            validate_event(event("f1", "language", "jlpt", "N1",
                                 effective_from="2026-01-20", effective_to="2027-01-01"))

    def test_unknown_fact_category_is_rejected(self) -> None:
        with self.assertRaises(CareerError):
            validate_event(event("f1", "not-a-category", "jlpt", "N1"))

    def test_a_fact_must_state_its_value_explicitly(self) -> None:
        bad = event("f1", "language", "jlpt", "N1")
        del bad["fact"]["value"]
        with self.assertRaises(CareerError):
            validate_event(bad)


class CliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name) / "vault"
        self._run("init")
        events = self.vault / "02-state" / "events.jsonl"
        import json

        events.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            event("f1", "language", "jlpt", "N2", effective_from="2024-07-01"),
            event("f2", "language", "jlpt", "N1", effective_from="2026-01-20", supersedes="f1"),
        ]
        events.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, *arguments: str) -> subprocess.CompletedProcess:
        environment = dict(os.environ, CAREER_VAULT=str(self.vault))
        return subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "career_agent.py"), *arguments],
            capture_output=True, text=True, check=False, env=environment,
        )

    def test_personal_profile_projects_for_an_explicit_date(self) -> None:
        result = self._run("personal-profile", "--as-of", "2025-01-01")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"N2"', result.stdout, "the 2024 fact is current for a 2025 as_of")
        self.assertNotIn('"N1"', result.stdout)

    def test_personal_timeline_labels_history_explicitly(self) -> None:
        result = self._run("personal-timeline", "--category", "language", "--key", "jlpt")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"context_mode": "historical"', result.stdout)
        self.assertIn('"superseded"', result.stdout)

    def test_context_includes_the_current_only_personal_projection(self) -> None:
        result = self._run("context", "--track", "chuto", "--stage", "面接",
                           "--as-of", "2026-08-05")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"personal_context_mode": "current-only"', result.stdout)
        self.assertIn('"N1"', result.stdout)
        self.assertNotIn('"N2"', result.stdout, "historical values stay out of default context")


if __name__ == "__main__":
    unittest.main()
