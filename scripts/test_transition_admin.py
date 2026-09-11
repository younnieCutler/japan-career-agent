#!/usr/bin/env python3
"""Regression tests for source-backed transition administration projection."""

from __future__ import annotations

import copy
import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "_shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from transition_admin import (  # noqa: E402
    TransitionAdminError,
    load_registry,
    project,
    render_text,
    validate_registry,
)


def by_id(results: list[dict]) -> dict[str, dict]:
    return {row["id"]: row for row in results}


class TransitionAdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry()

    def scenario(self, **overrides) -> dict:
        base = {
            "employment_end_date": "2026-09-30",
            "new_employment_start_date": "2026-10-01",
            "new_contract_conclusion_date": "2026-09-15",
            "unemployment_benefit_planned": False,
            "resident_tax_mode": "continue_special_collection",
            "health_insurance_after_exit": "new_employer_immediate",
            "residence_status": "技術・人文知識・国際業務",
            "new_activity_scope": "same",
        }
        base.update(overrides)
        return base

    def test_representative_gijinkoku_next_day_transition(self) -> None:
        rows = by_id(project(self.scenario(), registry=self.registry, as_of=dt.date(2026, 9, 12)))
        self.assertEqual(rows["withholding_slip"]["state"], "required")
        self.assertEqual(rows["withholding_slip"]["deadline"], "2026-10-30")
        self.assertEqual(rows["employment_insurance_number"]["state"], "required")
        self.assertEqual(rows["retirement_certificate"]["state"], "recommended")
        self.assertEqual(rows["resident_tax_special_collection_handoff"]["state"], "required")
        self.assertEqual(
            rows["resident_tax_special_collection_handoff"]["owner"],
            "former_and_new_employer",
        )
        self.assertEqual(rows["separation_slip"]["state"], "not_applicable")
        self.assertEqual(rows["health_insurance_loss_proof"]["state"], "not_applicable")
        self.assertEqual(rows["immigration_contract_end_notification"]["state"], "required")
        self.assertEqual(rows["immigration_contract_end_notification"]["deadline"], "2026-10-14")
        self.assertEqual(rows["immigration_new_contract_notification"]["state"], "required")
        self.assertEqual(rows["immigration_new_contract_notification"]["deadline"], "2026-09-29")
        self.assertEqual(rows["work_qualification_certificate"]["state"], "recommended")
        self.assertEqual(rows["residence_status_change_verification"]["state"], "not_applicable")

    def test_non_target_status_does_not_receive_work_status_notifications(self) -> None:
        rows = by_id(
            project(
                self.scenario(residence_status="永住者"),
                registry=self.registry,
                as_of=dt.date(2026, 9, 12),
            )
        )
        immigration_ids = (
            "immigration_contract_end_notification",
            "immigration_new_contract_notification",
            "immigration_activity_leave_notification",
            "immigration_activity_transfer_notification",
            "work_qualification_certificate",
        )
        for task_id in immigration_ids:
            self.assertEqual(rows[task_id]["state"], "not_applicable", task_id)

    def test_spouse_status_is_not_treated_as_contract_institution_status(self) -> None:
        rows = by_id(
            project(
                self.scenario(residence_status="日本人の配偶者等"),
                registry=self.registry,
                as_of=dt.date(2026, 9, 12),
            )
        )
        self.assertEqual(rows["immigration_contract_end_notification"]["state"], "not_applicable")
        self.assertEqual(rows["immigration_new_contract_notification"]["state"], "not_applicable")

    def test_unknown_residence_status_remains_unknown(self) -> None:
        rows = by_id(
            project(
                self.scenario(residence_status=None),
                registry=self.registry,
                as_of=dt.date(2026, 9, 12),
            )
        )
        self.assertEqual(rows["immigration_contract_end_notification"]["state"], "unknown")
        self.assertIn("residence_status", rows["immigration_contract_end_notification"]["missing_inputs"])

    def test_contract_date_is_not_inferred_from_start_date(self) -> None:
        rows = by_id(
            project(
                self.scenario(new_contract_conclusion_date=None),
                registry=self.registry,
                as_of=dt.date(2026, 9, 12),
            )
        )
        task = rows["immigration_new_contract_notification"]
        self.assertEqual(task["state"], "unknown")
        self.assertIsNone(task["deadline"])
        self.assertIn("new_contract_conclusion_date", task["missing_inputs"])

    def test_gap_scenario_activates_benefit_and_nhi_documents(self) -> None:
        rows = by_id(
            project(
                self.scenario(
                    new_employment_start_date="2026-11-01",
                    unemployment_benefit_planned=True,
                    health_insurance_after_exit="national_health_insurance",
                ),
                registry=self.registry,
                as_of=dt.date(2026, 9, 12),
            )
        )
        self.assertEqual(rows["separation_slip"]["state"], "conditional")
        self.assertEqual(rows["health_insurance_loss_proof"]["state"], "conditional")

    def test_changed_activity_requires_verification_not_assumed_certificate_only(self) -> None:
        rows = by_id(
            project(
                self.scenario(new_activity_scope="changed"),
                registry=self.registry,
                as_of=dt.date(2026, 9, 12),
            )
        )
        self.assertEqual(rows["residence_status_change_verification"]["state"], "required")
        self.assertEqual(
            rows["residence_status_change_verification"]["user_action"],
            "verify_with_immigration",
        )
        self.assertEqual(rows["work_qualification_certificate"]["state"], "recommended")

    def test_activity_institution_status_uses_leave_and_transfer_tasks(self) -> None:
        rows = by_id(
            project(
                self.scenario(residence_status="企業内転勤"),
                registry=self.registry,
                as_of=dt.date(2026, 9, 12),
            )
        )
        self.assertEqual(rows["immigration_activity_leave_notification"]["state"], "required")
        self.assertEqual(rows["immigration_activity_transfer_notification"]["state"], "required")
        self.assertEqual(rows["immigration_contract_end_notification"]["state"], "not_applicable")

    def test_stale_procedural_source_downgrades_rule_to_unknown(self) -> None:
        rows = by_id(project(self.scenario(), registry=self.registry, as_of=dt.date(2028, 1, 1)))
        task = rows["withholding_slip"]
        self.assertEqual(task["state"], "unknown")
        self.assertEqual(task["reason"], "stale_source")
        self.assertTrue(task["stale_sources"])

    def test_registry_rejects_unsupported_predicate(self) -> None:
        broken = copy.deepcopy(self.registry)
        broken["tasks"][0]["applies_if"] = {
            "all": [{"field": "x", "op": "python_eval", "value": "True"}]
        }
        with self.assertRaises(TransitionAdminError):
            validate_registry(broken)

    def test_text_output_keeps_owner_and_unknown_visible(self) -> None:
        results = project(
            self.scenario(new_contract_conclusion_date=None),
            registry=self.registry,
            as_of=dt.date(2026, 9, 12),
        )
        text = render_text(results)
        self.assertIn("former_and_new_employer", text)
        self.assertIn("new_contract_conclusion_date", text)
        self.assertIn("出入国在留管理庁", text)


if __name__ == "__main__":
    unittest.main()
