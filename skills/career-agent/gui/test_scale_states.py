"""Representative NEW, ACTIVE, and HEAVY Vault contracts for the product GUI."""

from __future__ import annotations

import json
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

import case_store  # noqa: E402
import experiences  # noqa: E402
import sessions  # noqa: E402
from gui import cases as gui_cases  # noqa: E402
from _test_client import FRONTEND_SRC  # noqa: E402
from gui.views_read import applications_payload, career_overview_payload, timeline_payload  # noqa: E402
from vault import CareerVault, initialize_vault  # noqa: E402


class GuiScaleStateTests(unittest.TestCase):
    def home(self) -> CareerVault:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "vault"
        initialize_vault(root)
        return CareerVault(root)

    @staticmethod
    def approve_case(home: CareerVault, record: dict) -> dict:
        reviewed = gui_cases.propose_canonical_case(home, record["case_id"])
        return gui_cases.approve_canonical_case(
            home, record["case_id"], reviewed["proposal"]["id"]
        )["case"]

    def populate(
        self,
        home: CareerVault,
        *,
        employers: int,
        projects: int,
        experiences_count: int,
        applications: int,
    ) -> None:
        contexts = []
        for index in range(employers):
            context = case_store.create_career_context(
                home,
                f"Example Employer {index + 1}",
                context_kind="company",
                relationship="employer",
                role="Platform Engineer",
                period={
                    "from": f"20{18 + index:02d}-04",
                    "to": None if index == employers - 1 else f"20{19 + index:02d}-03",
                    "current": index == employers - 1,
                },
            )
            contexts.append(self.approve_case(home, context))

        project_rows = []
        for index in range(projects):
            context = contexts[index % len(contexts)]
            project = case_store.create_project(
                home,
                context["case_id"],
                f"Service reliability project {index + 1}",
                role="owner" if index % 3 == 0 else "contributor",
                period={
                    "from": f"202{index % 6}-0{index % 9 + 1}",
                    "to": None,
                    "current": index % 5 == 0,
                },
                external_use="unknown" if index % 5 == 0 else "allowed",
            )
            project_rows.append(self.approve_case(home, project))

        for index in range(experiences_count):
            project = project_rows[index % len(project_rows)]
            created = sessions.create_session(home, case_ref=project["case_id"], entrypoint="gui")
            outcome_state = ("qualitative", "not_measured", "quantitative", "unknown")[index % 4]
            confidentiality = (
                {"contains_confidential": True, "external_use": "blocked"}
                if index % 9 == 0
                else {"contains_confidential": True, "external_use": "unknown"}
                if index % 9 == 1
                else {"contains_confidential": False, "external_use": "allowed"}
            )
            draft = {
                "summary": f"Improved service handoff {index + 1}",
                "work_date": f"202{index % 6}-{index % 12 + 1:02d}",
                "role": "engineer",
                "direct_actions": ["Reworked the operating procedure"],
                "individual_contribution": "I designed and documented the change",
                "outcome_state": outcome_state,
                "evidence": [
                    "Dashboard showed 12 minutes" if outcome_state == "quantitative" else "Reviewed runbook"
                ],
                "confidentiality": confidentiality,
            }
            if outcome_state == "qualitative":
                draft["team_result"] = "Fewer repeated handoff questions"
            elif outcome_state == "quantitative":
                draft["team_result"] = "Recovery time fell"
                draft["metrics"] = ["12 minutes"]
            saved = sessions.save_draft(
                home,
                created["session_id"],
                draft,
                expected_revision=0,
                entrypoint="gui",
            )
            proposed = sessions.create_proposal(
                home,
                created["session_id"],
                expected_revision=saved["revision"],
                entrypoint="gui",
            )
            sessions.approve_proposal(
                home,
                created["session_id"],
                proposed["proposal"]["id"],
                expected_revision=proposed["revision"],
                entrypoint="gui",
            )

        for index in range(4):
            created = sessions.create_session(
                home, case_ref=project_rows[index % len(project_rows)]["case_id"], entrypoint="claude"
            )
            draft = {
                "summary": f"Interrupted draft {index + 1}",
                "evidence": ["User note"],
                "role": "engineer",
                "direct_actions": ["Investigated the issue"],
                "individual_contribution": "I led the investigation",
                "outcome_state": "not_measured",
                "confidentiality": {"contains_confidential": False, "external_use": "unknown"},
            }
            saved = sessions.save_draft(
                home,
                created["session_id"],
                draft,
                expected_revision=0,
                entrypoint="codex",
            )
            if index % 2:
                sessions.create_proposal(
                    home,
                    created["session_id"],
                    expected_revision=saved["revision"],
                    entrypoint="cli",
                )
        sessions.create_session(
            home,
            workflow="self_analysis",
            entrypoint="claude",
            subject={"profile_label": "Career values"},
        )

        for index in range(applications):
            company = case_store.create_company(home, f"Target Company {index + 1}")
            case_store.create_application(home, company["case_id"], f"Role {index + 1}")

    def test_new_vault_has_distinct_empty_state_data(self) -> None:
        home = self.home()

        career = career_overview_payload(home)

        self.assertEqual(career["summary"]["contexts"], 0)
        self.assertEqual(career["contexts"], [])
        self.assertEqual(applications_payload(home)["companies"], [])
        self.assertEqual(timeline_payload(home)["sections"], [])

    def test_active_vault_preserves_mixed_lifecycle_and_trust_states(self) -> None:
        home = self.home()
        self.populate(home, employers=3, projects=10, experiences_count=32, applications=5)

        career = career_overview_payload(home)
        active = sessions.list_sessions(home)
        claims = experiences.list_experiences(home)["claims"]

        self.assertEqual(career["summary"]["contexts"], 3)
        self.assertEqual(career["summary"]["projects"], 10)
        self.assertEqual(career["summary"]["experiences"], 32)
        self.assertEqual({row["status"] for row in active["sessions"]}, {"draft", "review_pending"})
        self.assertIn("not_measured", {row.get("outcome_state") for row in claims})
        self.assertIn("quantitative", {row.get("outcome_state") for row in claims})
        self.assertTrue(any(row.get("contains_confidential") for row in claims))
        self.assertTrue(any(row.get("detail", {}).get("individual_contribution") for row in claims if not row.get("contains_confidential")))
        self.assertTrue(all(row.get("detail") is None for row in claims if row.get("contains_confidential")))
        public_experiences = [
            experience
            for context in career["contexts"]
            for project in context["projects"]
            for experience in project["experiences"]
        ]
        self.assertTrue(any(row.get("detail", {}).get("team_result") for row in public_experiences))
        self.assertTrue(all(not row.get("detail") for row in public_experiences if row["contains_confidential"]))
        applications = applications_payload(home)
        self.assertEqual(len(applications["companies"]), 5)
        confidential_options = [
            row for row in applications["evidence_options"] if row["contains_confidential"]
        ]
        self.assertTrue(confidential_options)
        self.assertTrue(all(row["label"] is None for row in confidential_options))
        self.assertTrue(all(row["work_date"] for row in confidential_options))

    def test_heavy_vault_avoids_n_plus_one_scans_and_unbounded_primary_lists(self) -> None:
        home = self.home()
        self.populate(home, employers=5, projects=25, experiences_count=80, applications=20)
        original_read = experiences.read_jsonl

        started = time.perf_counter()
        with patch.object(experiences, "read_jsonl", wraps=original_read) as ledger_reads:
            career = career_overview_payload(home)
            timeline = timeline_payload(home)
            application_rows = applications_payload(home)
        elapsed = time.perf_counter() - started

        self.assertEqual(career["summary"]["contexts"], 5)
        self.assertEqual(career["summary"]["projects"], 25)
        self.assertEqual(career["summary"]["experiences"], 80)
        self.assertEqual(len(application_rows["companies"]), 20)
        self.assertEqual(len([row for row in timeline["sections"] if row["kind"] == "experience"]), 80)
        self.assertLessEqual(ledger_reads.call_count, 5)
        self.assertLess(elapsed, 5.0)
        self.assertLess(len(json.dumps(career, ensure_ascii=False)), 1_000_000)

        self.assert_client_rendering_is_bounded()

    def assert_client_rendering_is_bounded(self) -> None:
        """A Vault this size must not become one DOM node per row.

        This used to be asserted as the literal `let limit = 8` in each screen, which broke on any
        rename and said nothing about screens that forgot to slice at all. The guarantee is that
        list rendering goes through one capped helper, so no screen can quietly opt out.
        """
        # The lists that grow with the Vault, and where each is bounded. Lists inside one
        # record — a company's applications, a project's experiences — are bounded by the record
        # the user opened, so they are deliberately not on this list.
        unbounded_by_nature = (
            ("screens/Career.jsx", "matches.slice(0, shown)"),
            ("screens/Applications.jsx", "matches.slice(0, shown)"),
            ("screens/Applications.jsx", "rows.slice(0, shown)"),
            ("screens/Chronology.jsx", "rows.slice(0, shown)"),
            ("screens/Home.jsx", "items.slice(0, 4)"),
            ("screens/Applications.jsx", "matches.slice(0, 20)"),
        )
        for name, bound in unbounded_by_nature:
            with self.subTest(screen=name, bound=bound):
                self.assertIn(bound, (FRONTEND_SRC / name).read_text(encoding="utf-8"))

        for name in ("Career.jsx", "Applications.jsx", "Chronology.jsx"):
            with self.subTest(screen=name):
                source = (FRONTEND_SRC / "screens" / name).read_text(encoding="utf-8")
                page_size = int(re.search(r"PAGE_SIZE = (\d+)", source).group(1))
                self.assertLessEqual(page_size, 50, "a page of rows should stay scannable")
                # A cap with no way past it would hide records rather than bound them.
                self.assertIn("action.show_more", source)


if __name__ == "__main__":
    unittest.main()
