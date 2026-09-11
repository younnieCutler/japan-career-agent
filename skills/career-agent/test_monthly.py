"""Contracts for the deterministic monthly career review projection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

import experiences  # noqa: E402
import monthly  # noqa: E402
import validation  # noqa: E402
from models import (  # noqa: E402
    EXPERIENCE_CONTEXT_EVENT_TYPE,
    EXPERIENCE_SUPERSESSION_EVENT_TYPE,
    WORK_EVENT_TYPE,
    CareerError,
)


def base_event(event_id: str, type_: str = WORK_EVENT_TYPE, **extra) -> dict:
    row = {
        "id": event_id,
        "track": None,
        "stage": None,
        "flow_phase": None,
        "type": type_,
        "occurred_at": "2026-09-11T00:00:00Z",
        "title": "note",
        "summary": "note",
        "evidence": ["user"],
        "source": "user",
        "next_action": None,
        "deadline": None,
        "status": "confirmed",
    }
    row.update(extra)
    return row


def evidence(event_id: str, **payload) -> dict:
    return base_event(event_id, work_event=payload)


def context(event_id: str, context_id: str, label: str) -> dict:
    return base_event(
        event_id,
        EXPERIENCE_CONTEXT_EVENT_TYPE,
        experience_context={"id": context_id, "kind": "company", "label": label},
    )


class MonthlyCareerProjectionTests(unittest.TestCase):
    def test_work_date_owns_the_month_and_capture_time_never_fills_a_blank(self) -> None:
        rows = monthly.monthly_career_projection([
            evidence("evt-july", work_date="2026-07", responsibility="release owner"),
            evidence("evt-august-day", work_date="2026-08-17", problem="manual handoff"),
            # occurred_at is September, but no work_date means the work month is genuinely unknown.
            evidence("evt-undated", responsibility="review owner"),
        ])

        self.assertEqual([row["month"] for row in rows], ["2026-08", "2026-07"])
        self.assertEqual(rows[0]["claim_refs"], ["evt-august-day"])
        self.assertEqual(rows[1]["claim_refs"], ["evt-july"])
        self.assertNotIn("evt-undated", [ref for row in rows for ref in row["claim_refs"]])

    def test_invalid_historical_work_dates_never_become_month_buckets(self) -> None:
        rows = monthly.monthly_career_projection([
            evidence("evt-valid", work_date="2026-02-28", responsibility="release owner"),
            evidence("evt-bad-month", work_date="2026-99", responsibility="release owner"),
            evidence("evt-bad-day", work_date="2026-02-30", responsibility="release owner"),
            evidence("evt-bad-shape", work_date="2026-02-extra", responsibility="release owner"),
        ])

        self.assertEqual([row["month"] for row in rows], ["2026-02"])
        self.assertEqual(rows[0]["claim_refs"], ["evt-valid"])

    def test_career_depth_fields_are_optional_non_empty_text(self) -> None:
        values = {
            "responsibility": "owned the release decision",
            "judgment": "kept the compatibility path",
            "decision_basis": "existing clients still depended on it",
            "risk_management": "isolated the migration behind a reversible gate",
            "organizational_context": "supported the quarter's reliability goal",
        }
        validation.validate_work_event(values)
        validation.validate_work_event({"decision_basis": values["decision_basis"]})

        for name in values:
            with self.subTest(name=name), self.assertRaises(CareerError):
                validation.validate_work_event({name: "   "})

    def test_numeric_career_depth_claim_requires_matching_evidence(self) -> None:
        row = evidence(
            "evt-number",
            work_date="2026-08",
            responsibility="12명 대상 배포 판단을 책임짐",
        )
        with self.assertRaises(CareerError):
            validation.validate_event(row)

        row["evidence"] = ["사용자 확인: 12명 대상 배포 판단을 책임짐"]
        validation.validate_event(row)

    def test_coverage_is_evidence_presence_not_a_generated_score(self) -> None:
        rows = monthly.monthly_career_projection([
            evidence(
                "evt-rich",
                work_date="2026-08",
                responsibility="owned release readiness",
                problem="manual handoff",
                judgment="automate validation before release",
                decision_basis="manual checks had repeated omissions",
                risk_management="kept a manual fallback for rollback",
                direct_actions=["automated validation"],
                stakeholder_coordination=["aligned with operations"],
                organizational_context="supported the reliability objective",
                outcome_state="quantitative",
                team_result="fewer manual checks",
                metrics=["3건의 수동 점검 제거"],
                improvements=["document the fallback"],
            ),
            # Assigned scope is context, not proof of responsibility.
            evidence("evt-sparse", work_date="2026-08", role="engineer", scope="release process"),
        ])

        self.assertEqual(len(rows), 1)
        august = rows[0]
        self.assertEqual(august["evidence_count"], 2)
        self.assertEqual(august["coverage"]["responsibility"], {"present": 1, "total": 2})
        self.assertEqual(august["coverage"]["judgment"], {"present": 1, "total": 2})
        self.assertEqual(august["coverage"]["decision_basis"], {"present": 1, "total": 2})
        self.assertEqual(august["coverage"]["risk_management"], {"present": 1, "total": 2})
        self.assertEqual(august["coverage"]["stakeholder_coordination"], {"present": 1, "total": 2})
        self.assertEqual(august["coverage"]["organizational_context"], {"present": 1, "total": 2})
        self.assertEqual(august["coverage"]["quantification"], {"present": 1, "total": 2})
        self.assertEqual(august["gaps"], [])
        self.assertEqual(set(august["partial"]), set(monthly.DIMENSIONS))
        self.assertNotIn("score", august)

    def test_role_and_scope_do_not_stand_in_for_responsibility(self) -> None:
        row = monthly.monthly_career_projection([
            evidence("evt-one", work_date="2026-08", role="owner"),
            evidence("evt-two", work_date="2026-08", scope="release process"),
        ])[0]

        self.assertIn("responsibility", row["gaps"])
        self.assertIn("judgment", row["gaps"])
        self.assertIn("decision_basis", row["gaps"])
        self.assertIn("risk_management", row["gaps"])
        self.assertIn("stakeholder_coordination", row["gaps"])
        self.assertIn("organizational_context", row["gaps"])
        self.assertIn("outcome", row["gaps"])

    def test_context_filter_never_mixes_two_employers_months(self) -> None:
        events = [
            evidence("evt-a", context_id="ctx-a", work_date="2026-08", responsibility="owner"),
            evidence("evt-b", context_id="ctx-b", work_date="2026-09", responsibility="owner"),
        ]

        rows = monthly.monthly_career_projection(events, context_id="ctx-a")

        self.assertEqual([row["month"] for row in rows], ["2026-08"])
        self.assertEqual(rows[0]["claim_refs"], ["evt-a"])

    def test_superseded_evidence_is_not_projected_into_a_month(self) -> None:
        predecessor = evidence("evt-old", work_date="2026-08", responsibility="old owner")
        replacement = evidence("evt-new", work_date="2026-09", responsibility="new owner")
        supersession = base_event(
            "evt-supersession",
            EXPERIENCE_SUPERSESSION_EVENT_TYPE,
            title="Corrected work evidence",
            summary="The September evidence replaces the August claim.",
            supersession={
                "predecessor_event_id": predecessor["id"],
                "replacement_event_id": replacement["id"],
            },
        )

        rows = monthly.monthly_career_projection([predecessor, replacement, supersession])

        self.assertEqual([row["month"] for row in rows], ["2026-09"])
        self.assertEqual(rows[0]["claim_refs"], ["evt-new"])

    def test_experiences_read_model_exposes_the_same_context_scoped_months(self) -> None:
        events = [
            context("evt-ctx-a", "ctx-a", "Acme"),
            context("evt-ctx-b", "ctx-b", "Beta"),
            evidence(
                "evt-a", context_id="ctx-a", experience_ref="release", work_date="2026-08",
                individual_contribution="owned release validation",
            ),
            evidence(
                "evt-b", context_id="ctx-b", experience_ref="migration", work_date="2026-09",
                individual_contribution="owned migration validation",
            ),
        ]
        home = SimpleNamespace(path=Path("vault"), events=Path("unused"))

        with patch.object(experiences, "read_jsonl", return_value=events):
            all_rows = experiences.list_experiences(home)
            acme = experiences.list_experiences(home, context_id="ctx-a")

        self.assertEqual([row["month"] for row in all_rows["months"]], ["2026-09", "2026-08"])
        self.assertEqual([row["month"] for row in acme["months"]], ["2026-08"])
        self.assertTrue(acme["no_total_by_design"])


if __name__ == "__main__":
    unittest.main()
