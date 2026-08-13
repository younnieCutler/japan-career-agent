"""Contracts separating career contexts from application target companies."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

import case_store  # noqa: E402
import approvals  # noqa: E402
from gui import cases as gui_cases, tanaoroshi  # noqa: E402
from models import CareerError, EXPERIENCE_CONTEXT_KINDS  # noqa: E402
from vault import CareerVault, initialize_vault  # noqa: E402


class CaseHierarchyV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name) / "vault"
        initialize_vault(root)
        self.home = CareerVault(root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_employer_project_and_application_company_are_distinct(self) -> None:
        employer = case_store.create_career_context(
            self.home, "Acme", context_kind="company", relationship="employer"
        )
        project = case_store.create_project(self.home, employer["case_id"], "Payments migration")
        target = case_store.create_company(self.home, "Future Corp")
        application = case_store.create_application(self.home, target["case_id"], "Platform Engineer")

        self.assertEqual(employer["kind"], "career_context")
        self.assertEqual(project["parent_ref"], employer["case_id"])
        self.assertEqual(target["kind"], "company")
        self.assertEqual(application["parent_ref"], target["case_id"])
        self.assertNotEqual(project["parent_ref"], application["parent_ref"])

    def test_non_work_context_can_own_a_project(self) -> None:
        context = case_store.create_career_context(
            self.home, "Open source", context_kind="open_source", relationship="non_work"
        )
        project = case_store.create_project(self.home, context["case_id"], "Maintainer onboarding")

        self.assertEqual(context["metadata"]["context_kind"], "open_source")
        self.assertEqual(project["parent_ref"], context["case_id"])

    def test_personal_education_and_other_contexts_are_supported(self) -> None:
        for kind in ("personal", "university", "other"):
            context = case_store.create_career_context(
                self.home,
                f"Example {kind}",
                context_kind=kind,
                relationship="non_work",
            )
            self.assertEqual(context["metadata"]["context_kind"], kind)

    def test_every_context_kind_has_one_enforced_work_relationship(self) -> None:
        for kind in sorted(EXPERIENCE_CONTEXT_KINDS):
            expected = case_store.context_relationship(kind)
            with self.subTest(kind=kind, relationship=expected):
                context = case_store.create_career_context(
                    self.home,
                    f"Valid {kind}",
                    context_kind=kind,
                    relationship=expected,
                )
                self.assertEqual(context["metadata"]["relationship"], expected)
                wrong = "non_work" if expected == "employer" else "employer"
                with self.assertRaises(CareerError) as mismatch:
                    case_store.create_career_context(
                        self.home,
                        f"Invalid {kind}",
                        context_kind=kind,
                        relationship=wrong,
                    )
                self.assertEqual(mismatch.exception.code, "INVALID_RELATIONSHIP")

    def test_new_project_rejects_target_company_as_parent(self) -> None:
        target = case_store.create_company(self.home, "Target Corp")

        with self.assertRaises(CareerError) as invalid:
            case_store.create_project(self.home, target["case_id"], "Wrong hierarchy")

        self.assertEqual(invalid.exception.code, "INVALID_RELATIONSHIP")

    def test_archived_parents_reject_new_projects_and_applications(self) -> None:
        context = case_store.create_career_context(
            self.home, "Acme", context_kind="company", relationship="employer"
        )
        target = case_store.create_company(self.home, "Target Corp")
        case_store.archive_case(
            self.home, context["case_id"], expected_updated_at=context["updated_at"]
        )
        case_store.archive_case(
            self.home, target["case_id"], expected_updated_at=target["updated_at"]
        )

        with self.assertRaises(CareerError) as project_error:
            case_store.create_project(self.home, context["case_id"], "Wrong lifecycle")
        with self.assertRaises(CareerError) as application_error:
            case_store.create_application(self.home, target["case_id"], "Platform Engineer")

        self.assertEqual(project_error.exception.code, "INVALID_RELATIONSHIP")
        self.assertEqual(application_error.exception.code, "INVALID_RELATIONSHIP")

    def test_case_archive_restore_rejects_stale_hosts_and_never_hides_canonical_history(self) -> None:
        context = case_store.create_career_context(
            self.home, "Acme", context_kind="company", relationship="employer"
        )
        original_revision = context["updated_at"]
        archived = case_store.archive_case(
            self.home, context["case_id"], expected_updated_at=original_revision
        )
        with self.assertRaises(CareerError) as stale:
            case_store.restore_case(
                self.home, context["case_id"], expected_updated_at=original_revision
            )
        self.assertEqual(stale.exception.code, "REVISION_STALE")
        restored = case_store.restore_case(
            self.home, context["case_id"], expected_updated_at=archived["updated_at"]
        )
        review = gui_cases.propose_canonical_case(self.home, context["case_id"])
        confirmed = gui_cases.approve_canonical_case(
            self.home, context["case_id"], review["proposal"]["id"]
        )["case"]
        ledger_before = self.home.events.read_bytes()

        with self.assertRaises(CareerError) as immutable:
            case_store.archive_case(
                self.home,
                confirmed["case_id"],
                expected_updated_at=confirmed["updated_at"],
            )

        self.assertEqual(restored["status"], "active")
        self.assertEqual(immutable.exception.code, "CASE_ALREADY_CONFIRMED")
        self.assertEqual(self.home.events.read_bytes(), ledger_before)

    def test_archived_review_cannot_be_approved_until_restored(self) -> None:
        context = case_store.create_career_context(
            self.home, "Acme", context_kind="company", relationship="employer"
        )
        review = gui_cases.propose_canonical_case(self.home, context["case_id"])
        archived = case_store.archive_case(
            self.home,
            context["case_id"],
            expected_updated_at=case_store.get_case(self.home, context["case_id"])["updated_at"],
        )

        with self.assertRaises(CareerError) as blocked:
            gui_cases.approve_canonical_case(
                self.home, context["case_id"], review["proposal"]["id"]
            )

        self.assertEqual(archived["status"], "archived")
        self.assertEqual(blocked.exception.code, "INVALID_RELATIONSHIP")
        self.assertFalse(self.home.events.exists())

    def test_legacy_parentless_project_remains_readable_as_needing_context(self) -> None:
        legacy_id = "case-project-0000000000000001"
        path = case_store.cases_root(self.home) / f"{legacy_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "case_id": legacy_id,
                    "kind": "project",
                    "parent_ref": None,
                    "label": "Legacy project",
                    "status": "active",
                    "metadata": {"external_use": "unknown"},
                    "source_refs": [],
                    "created_at": "2026-08-12T00:00:00Z",
                    "updated_at": "2026-08-12T00:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        loaded = case_store.get_case(self.home, legacy_id)

        self.assertEqual(loaded["relationship_state"], "needs_context")
        self.assertIsNone(loaded["parent_ref"])

    def test_legacy_project_connection_rejects_a_stale_screen(self) -> None:
        context = case_store.create_career_context(
            self.home, "Acme", context_kind="company", relationship="employer"
        )
        legacy_id = "case-project-0000000000000001"
        path = case_store.cases_root(self.home) / f"{legacy_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "case_id": legacy_id,
            "kind": "project",
            "parent_ref": None,
            "label": "Legacy project",
            "status": "active",
            "metadata": {"external_use": "unknown"},
            "source_refs": [],
            "created_at": "2026-08-12T00:00:00Z",
            "updated_at": "2026-08-12T00:00:00Z",
        }) + "\n", encoding="utf-8")

        connected = case_store.assign_project_context(
            self.home,
            legacy_id,
            context["case_id"],
            expected_updated_at="2026-08-12T00:00:00Z",
        )
        with self.assertRaises(CareerError) as stale:
            case_store.assign_project_context(
                self.home,
                legacy_id,
                context["case_id"],
                expected_updated_at="2026-08-12T00:00:00Z",
            )

        self.assertEqual(stale.exception.code, "REVISION_STALE")
        self.assertEqual(connected["parent_ref"], context["case_id"])

    def test_confirmed_project_cannot_be_repaired_under_the_wrong_company(self) -> None:
        contexts = []
        for label in ("Acme", "Wrong Corp"):
            context = case_store.create_career_context(
                self.home, label, context_kind="company", relationship="employer"
            )
            review = gui_cases.propose_canonical_case(self.home, context["case_id"])
            gui_cases.approve_canonical_case(
                self.home, context["case_id"], review["proposal"]["id"]
            )
            contexts.append(case_store.get_case(self.home, context["case_id"]))
        project = case_store.create_project(self.home, contexts[0]["case_id"], "Payments")
        review = gui_cases.propose_canonical_case(self.home, project["case_id"])
        gui_cases.approve_canonical_case(self.home, project["case_id"], review["proposal"]["id"])
        started = tanaoroshi.start(self.home, case_ref=project["case_id"])
        saved = tanaoroshi.autosave(
            self.home,
            started["session"]["session_ref"],
            {"summary": "Reduced payment failures", "evidence": ["user confirmation"]},
            expected_revision=started["revision"],
        )
        proposed = tanaoroshi.submit(
            self.home,
            started["session"]["session_ref"],
            expected_revision=saved["revision"],
        )
        tanaoroshi.approve_session(
            self.home,
            started["session"]["session_ref"],
            proposed["proposal"]["id"],
            expected_revision=proposed["revision"],
        )
        record = case_store.get_case(self.home, project["case_id"])
        record.pop("relationship_state", None)
        record["parent_ref"] = None
        record["updated_at"] = "2026-08-12T00:00:00Z"
        case_store.case_path(self.home, project["case_id"]).write_text(
            json.dumps(record) + "\n", encoding="utf-8"
        )

        with self.assertRaises(CareerError) as wrong:
            case_store.assign_project_context(
                self.home,
                project["case_id"],
                contexts[1]["case_id"],
                expected_updated_at="2026-08-12T00:00:00Z",
            )

        self.assertEqual(wrong.exception.code, "INVALID_RELATIONSHIP")

    def test_confirmed_parent_chain_anchors_experience_server_side(self) -> None:
        employer = case_store.create_career_context(
            self.home, "Acme", context_kind="company", relationship="employer"
        )
        context_review = gui_cases.propose_canonical_case(self.home, employer["case_id"])
        self.assertFalse(self.home.events.exists())
        confirmed_context = gui_cases.approve_canonical_case(
            self.home, employer["case_id"], context_review["proposal"]["id"]
        )["case"]

        project = case_store.create_project(
            self.home, employer["case_id"], "Payments migration"
        )
        project_review = gui_cases.propose_canonical_case(self.home, project["case_id"])
        confirmed_project = gui_cases.approve_canonical_case(
            self.home, project["case_id"], project_review["proposal"]["id"]
        )["case"]

        started = tanaoroshi.start(self.home, case_ref=project["case_id"])
        saved = tanaoroshi.autosave(
            self.home,
            started["session"]["session_ref"],
            {
                "summary": "Improved the cutover",
                "context_id": "ctx-wrong",
                "primary_project_id": "prj-wrong",
                "non_work": True,
            },
            expected_revision=started["revision"],
        )

        self.assertEqual(saved["draft"]["context_id"], confirmed_context["metadata"]["context_id"])
        self.assertEqual(saved["draft"]["primary_project_id"], confirmed_project["metadata"]["project_id"])
        self.assertFalse(saved["draft"]["non_work"])

    def test_non_company_parent_produces_non_work_experience(self) -> None:
        context = case_store.create_career_context(
            self.home, "Open source", context_kind="open_source", relationship="non_work"
        )
        context_review = gui_cases.propose_canonical_case(self.home, context["case_id"])
        gui_cases.approve_canonical_case(
            self.home, context["case_id"], context_review["proposal"]["id"]
        )
        project = case_store.create_project(self.home, context["case_id"], "Maintainer onboarding")
        project_review = gui_cases.propose_canonical_case(self.home, project["case_id"])
        gui_cases.approve_canonical_case(
            self.home, project["case_id"], project_review["proposal"]["id"]
        )

        started = tanaoroshi.start(self.home, case_ref=project["case_id"])
        saved = tanaoroshi.autosave(
            self.home,
            started["session"]["session_ref"],
            {"summary": "Helped contributors", "non_work": False},
            expected_revision=started["revision"],
        )

        self.assertTrue(saved["draft"]["non_work"])
        self.assertEqual(started["session"]["subject"]["context_kind"], "open_source")

    def test_freelance_context_remains_work_without_a_company(self) -> None:
        context = case_store.create_career_context(
            self.home, "Independent consulting", context_kind="freelance", relationship="employer"
        )
        context_review = gui_cases.propose_canonical_case(self.home, context["case_id"])
        gui_cases.approve_canonical_case(
            self.home, context["case_id"], context_review["proposal"]["id"]
        )
        project = case_store.create_project(self.home, context["case_id"], "Client platform")
        project_review = gui_cases.propose_canonical_case(self.home, project["case_id"])
        gui_cases.approve_canonical_case(
            self.home, project["case_id"], project_review["proposal"]["id"]
        )

        started = tanaoroshi.start(self.home, case_ref=project["case_id"])
        saved = tanaoroshi.autosave(
            self.home,
            started["session"]["session_ref"],
            {"summary": "Delivered a client platform", "non_work": True},
            expected_revision=started["revision"],
        )

        self.assertFalse(saved["draft"]["non_work"])
        self.assertEqual(started["session"]["subject"]["context_kind"], "freelance")

    def test_case_bound_proposal_cannot_be_approved_or_rebound_outside_its_case(self) -> None:
        context = case_store.create_career_context(
            self.home, "Acme", context_kind="company", relationship="employer"
        )
        reviewed = gui_cases.propose_canonical_case(self.home, context["case_id"])
        proposal_id = reviewed["proposal"]["id"]

        with self.assertRaises(CareerError) as bypass:
            approvals.approve(self.home, proposal_id)
        self.assertEqual(bypass.exception.code, "CASE_APPROVAL_REQUIRED")
        with self.assertRaises(CareerError) as stale:
            case_store.link_pending_proposal(
                self.home,
                context["case_id"],
                "proposal-different",
                expected_proposal_id=None,
            )
        self.assertEqual(stale.exception.code, "REVISION_STALE")
        self.assertFalse(self.home.events.exists())


if __name__ == "__main__":
    unittest.main()
