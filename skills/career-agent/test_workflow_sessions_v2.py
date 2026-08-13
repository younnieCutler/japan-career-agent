"""Contracts for host-neutral workflow sessions and honest draft states."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

import sessions  # noqa: E402
import approvals  # noqa: E402
import case_store  # noqa: E402
import experiences  # noqa: E402
import persistence  # noqa: E402
from gui import cases as gui_cases  # noqa: E402
from models import CareerError  # noqa: E402
from vault import CareerVault, initialize_vault  # noqa: E402


class WorkflowSessionV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.tempdir.name) / "vault"
        initialize_vault(self.vault_path)
        self.home = CareerVault(self.vault_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def confirmed_project(
        self, context_label: str, project_label: str, *, kind: str = "company"
    ) -> tuple[dict, dict]:
        context = case_store.create_career_context(
            self.home,
            context_label,
            context_kind=kind,
            relationship="employer" if kind == "company" else "non_work",
        )
        reviewed = gui_cases.propose_canonical_case(self.home, context["case_id"])
        context = gui_cases.approve_canonical_case(
            self.home, context["case_id"], reviewed["proposal"]["id"]
        )["case"]
        project = case_store.create_project(self.home, context["case_id"], project_label)
        reviewed = gui_cases.propose_canonical_case(self.home, project["case_id"])
        project = gui_cases.approve_canonical_case(
            self.home, project["case_id"], reviewed["proposal"]["id"]
        )["case"]
        return context, project

    def test_new_session_carries_host_neutral_semantic_state(self) -> None:
        created = sessions.create_session(
            self.home,
            workflow="career_inventory",
            entrypoint="codex",
            subject={
                "context_label": "Acme",
                "project_label": "Payments migration",
                "experience_label": "Cutover",
            },
        )

        self.assertEqual(created["session_schema_version"], 2)
        self.assertEqual(created["workflow"], "career_inventory")
        self.assertEqual(created["stage"], "experience")
        self.assertEqual(created["status"], "draft")
        self.assertEqual(created["revision"], 0)
        self.assertEqual(created["started_by"], "codex")
        self.assertEqual(created["last_entrypoint"], "codex")
        self.assertEqual(created["subject"]["project_label"], "Payments migration")
        self.assertEqual(created["next_action"], "continue")
        self.assertNotIn("transcript", json.dumps(created))
        self.assertNotIn("conversation", json.dumps(created))

    def test_stale_host_cannot_overwrite_a_newer_draft(self) -> None:
        created = sessions.create_session(self.home, entrypoint="gui")
        session_id = created["session_id"]
        saved = sessions.save_draft(
            self.home,
            session_id,
            {"summary": "newer text", "non_work": False},
            expected_revision=0,
            entrypoint="codex",
        )

        with self.assertRaises(CareerError) as stale:
            sessions.save_draft(
                self.home,
                session_id,
                {"summary": "stale browser text", "non_work": False},
                expected_revision=0,
                entrypoint="gui",
            )

        self.assertEqual(stale.exception.code, "REVISION_STALE")
        self.assertEqual(saved["revision"], 1)
        resumed = sessions.resume_session(self.home, session_id)
        self.assertEqual(resumed["revision"], 1)
        self.assertEqual(resumed["draft"]["summary"], "newer text")
        self.assertEqual(resumed["session"]["last_entrypoint"], "codex")

    def test_real_entrypoints_cannot_review_an_unplaced_experience(self) -> None:
        for entrypoint in ("claude", "codex", "cli", "gui"):
            created = sessions.create_session(self.home, entrypoint=entrypoint)
            saved = sessions.save_draft(
                self.home,
                created["session_id"],
                {"summary": f"Unplaced {entrypoint}", "evidence": ["user note"], "non_work": False},
                expected_revision=0,
                entrypoint=entrypoint,
            )
            with self.assertRaises(CareerError) as unplaced:
                sessions.create_proposal(
                    self.home,
                    created["session_id"],
                    expected_revision=saved["revision"],
                    entrypoint=entrypoint,
                )
            self.assertEqual(unplaced.exception.code, "CONTEXT_REQUIRED")
        self.assertFalse(self.home.events.exists())

    def test_unplaced_draft_can_be_connected_once_with_stale_write_protection(self) -> None:
        context, project = self.confirmed_project("Open Source", "Contributor onboarding", kind="open_source")
        _, wrong_project = self.confirmed_project("Wrong Corp", "Wrong project")
        created = sessions.create_session(
            self.home,
            entrypoint="claude",
            subject={"context_label": "Unverified label", "project_label": "Unverified project"},
        )
        saved = sessions.save_draft(
            self.home,
            created["session_id"],
            {"summary": "Helped new contributors", "evidence": ["maintainer notes"], "non_work": False},
            expected_revision=0,
            entrypoint="codex",
        )
        assigned = sessions.assign_session_project(
            self.home,
            created["session_id"],
            project["case_id"],
            expected_revision=saved["revision"],
            entrypoint="gui",
        )

        self.assertEqual(assigned["session"]["subject"]["context_label"], "Open Source")
        self.assertEqual(assigned["session"]["subject"]["project_label"], "Contributor onboarding")
        self.assertEqual(assigned["draft"]["context_id"], context["metadata"]["context_id"])
        self.assertTrue(assigned["draft"]["non_work"])
        with self.assertRaises(CareerError) as stale:
            sessions.assign_session_project(
                self.home,
                created["session_id"],
                wrong_project["case_id"],
                expected_revision=saved["revision"],
                entrypoint="cli",
            )
        self.assertEqual(stale.exception.code, "REVISION_STALE")
        with self.assertRaises(CareerError) as wrong:
            sessions.assign_session_project(
                self.home,
                created["session_id"],
                wrong_project["case_id"],
                expected_revision=assigned["revision"],
                entrypoint="cli",
            )
        self.assertEqual(wrong.exception.code, "REVISION_STALE")

    def test_multiple_workflows_are_all_discoverable_with_human_context(self) -> None:
        first = sessions.create_session(
            self.home,
            workflow="career_inventory",
            subject={"context_label": "Acme", "project_label": "Payments"},
        )
        second = sessions.create_session(
            self.home,
            workflow="self_analysis",
            subject={"profile_label": "Career values"},
        )

        listed = sessions.list_sessions(self.home)

        self.assertEqual(listed["count"], 2)
        self.assertEqual(
            {row["session_id"] for row in listed["sessions"]},
            {first["session_id"], second["session_id"]},
        )
        for row in listed["sessions"]:
            self.assertIn("display_context", row)
            self.assertIn("remaining_work", row)
            self.assertIn("review_status", row)

    def test_v1_tanaoroshi_session_migrates_in_memory_without_rewrite(self) -> None:
        created = sessions.create_session(self.home)
        path = sessions.session_path(self.home, created["session_id"])
        legacy = {
            "session_id": created["session_id"],
            "session_schema_version": 1,
            "workflow": "tanaoroshi",
            "stage": "experience_evidence",
            "case_ref": None,
            "current_item_ref": None,
            "missing_fields": ["role"],
            "completed": [],
            "draft_ref": created["draft_ref"],
            "proposal_refs": [],
            "updated_at": created["updated_at"],
        }
        original = (json.dumps(legacy) + "\n").encode()
        path.write_bytes(original)

        resumed = sessions.resume_session(self.home, created["session_id"])

        self.assertEqual(resumed["session"]["workflow"], "career_inventory")
        self.assertEqual(resumed["session"]["stage"], "experience")
        self.assertEqual(resumed["session"]["revision"], 0)
        self.assertEqual(path.read_bytes(), original)

    def test_a_newer_session_schema_is_refused_without_rewrite(self) -> None:
        created = sessions.create_session(self.home)
        path = sessions.session_path(self.home, created["session_id"])
        future = {**created, "session_schema_version": sessions.CURRENT_SESSION_SCHEMA_VERSION + 1}
        original = (json.dumps(future) + "\n").encode()
        path.write_bytes(original)

        with self.assertRaises(CareerError) as refused:
            sessions.resume_session(self.home, created["session_id"])

        self.assertEqual(refused.exception.code, "SESSION_SCHEMA_NEWER")
        self.assertEqual(path.read_bytes(), original)

    def test_metrics_are_optional_and_input_state_is_not_canonical_state(self) -> None:
        qualitative = {
            "summary": "Reduced handoff confusion",
            "outcome_state": "qualitative",
            "team_result": "Fewer repeated questions",
            "non_work": False,
        }
        not_measured = {
            "summary": "Improved the runbook",
            "outcome_state": "not_measured",
            "non_work": False,
        }

        self.assertNotIn("metrics", sessions.missing_fields(qualitative))
        self.assertNotIn("metrics", sessions.missing_fields(not_measured))
        qualitative_states = {row["field"]: row["status"] for row in sessions.field_status(qualitative)}
        not_measured_states = {row["field"]: row["status"] for row in sessions.field_status(not_measured)}
        self.assertNotIn("Confirmed", qualitative_states.values())
        self.assertEqual(qualitative_states["outcome"], "entered")
        self.assertEqual(not_measured_states["metrics"], "not_applicable")

    def test_qualitative_claim_can_use_explicit_approval_without_material_evidence(self) -> None:
        _, project = self.confirmed_project("Acme", "Runbook")
        created = sessions.create_session(
            self.home, case_ref=project["case_id"], entrypoint="gui"
        )
        saved = sessions.save_draft(
            self.home,
            created["session_id"],
            {
                "summary": "Clarified the handoff",
                "role": "owner",
                "direct_actions": ["rewrote the guide"],
                "individual_contribution": "designed the structure",
                "outcome_state": "qualitative",
                "team_result": "fewer repeated questions",
                "confidentiality": {"contains_confidential": False, "external_use": "allowed"},
            },
            expected_revision=0,
            entrypoint="gui",
        )
        proposed = sessions.create_proposal(
            self.home,
            created["session_id"],
            expected_revision=saved["revision"],
            entrypoint="gui",
        )

        self.assertEqual(proposed["proposal"]["event"]["evidence"], ["user_confirmation"])
        approved = sessions.approve_proposal(
            self.home,
            created["session_id"],
            proposed["proposal"]["id"],
            expected_revision=proposed["revision"],
            entrypoint="gui",
        )
        claim = experiences.list_experiences(self.home)["claims"][-1]

        self.assertTrue(approved["approved"])
        self.assertEqual(claim["evidence_count"], 1)
        self.assertEqual(claim["material_evidence_count"], 0)

    def test_user_confirmation_never_substitutes_for_quantitative_evidence(self) -> None:
        _, project = self.confirmed_project("Acme", "Latency")
        created = sessions.create_session(self.home, case_ref=project["case_id"])
        saved = sessions.save_draft(
            self.home,
            created["session_id"],
            {
                "summary": "Reduced latency by 20%",
                "role": "owner",
                "direct_actions": ["changed the cache policy"],
                "individual_contribution": "designed the change",
                "outcome_state": "quantitative",
                "team_result": "Latency fell by 20%",
                "metrics": ["20%"],
                "confidentiality": {"contains_confidential": False, "external_use": "allowed"},
            },
            expected_revision=0,
        )
        proposed = sessions.create_proposal(
            self.home, created["session_id"], expected_revision=saved["revision"]
        )
        before = persistence.read_jsonl(self.home.events)

        with self.assertRaises(CareerError):
            sessions.approve_proposal(
                self.home,
                created["session_id"],
                proposed["proposal"]["id"],
                expected_revision=proposed["revision"],
            )

        self.assertEqual(persistence.read_jsonl(self.home.events), before)

    def test_semantic_checkpoints_keep_the_paired_revision_coherent(self) -> None:
        created = sessions.create_session(self.home, entrypoint="claude")
        saved = sessions.save_draft(
            self.home,
            created["session_id"],
            {"summary": "A draft", "non_work": False},
            expected_revision=0,
            entrypoint="codex",
        )
        checked = sessions.checkpoint_session(
            self.home,
            created["session_id"],
            current_item_ref="experience",
            expected_revision=saved["revision"],
            entrypoint="cli",
        )

        resumed = sessions.resume_session(self.home, created["session_id"])

        self.assertEqual(resumed["revision"], checked["revision"])
        self.assertFalse(resumed["write_recovery_required"])
        self.assertEqual(resumed["session"]["last_entrypoint"], "cli")

    def test_stale_review_cannot_be_approved_and_generic_approve_cannot_bypass_session(self) -> None:
        _, project = self.confirmed_project("Acme", "Runbook")
        canonical_before = persistence.read_jsonl(self.home.events)
        created = sessions.create_session(
            self.home, case_ref=project["case_id"], entrypoint="claude"
        )
        session_id = created["session_id"]
        complete = {
            "summary": "Improved handoff clarity",
            "role": "owner",
            "direct_actions": ["rewrote the runbook"],
            "individual_contribution": "designed the structure",
            "outcome_state": "qualitative",
            "team_result": "fewer repeated questions",
            "evidence": ["reviewed runbook"],
            "confidentiality": {"contains_confidential": False, "external_use": "allowed"},
            "non_work": False,
        }
        saved = sessions.save_draft(
            self.home, session_id, complete, expected_revision=0, entrypoint="codex"
        )
        proposed = sessions.create_proposal(
            self.home,
            session_id,
            expected_revision=saved["revision"],
            entrypoint="cli",
        )
        proposal_id = proposed["proposal"]["id"]
        with self.assertRaises(CareerError) as bypass:
            approvals.approve(self.home, proposal_id)
        self.assertEqual(bypass.exception.code, "SESSION_APPROVAL_REQUIRED")

        newer = sessions.save_draft(
            self.home,
            session_id,
            {**complete, "summary": "Newer wording"},
            expected_revision=proposed["revision"],
            entrypoint="codex",
        )
        with self.assertRaises(CareerError) as stale:
            sessions.approve_proposal(
                self.home,
                session_id,
                proposal_id,
                expected_revision=proposed["revision"],
                entrypoint="gui",
            )
        self.assertEqual(stale.exception.code, "REVISION_STALE")
        self.assertEqual(sessions.resume_session(self.home, session_id)["revision"], newer["revision"])
        self.assertEqual(persistence.read_jsonl(self.home.events), canonical_before)

    def test_archive_is_recoverable_and_keeps_the_draft(self) -> None:
        created = sessions.create_session(self.home)
        saved = sessions.save_draft(
            self.home,
            created["session_id"],
            {"summary": "Keep this", "non_work": False},
            expected_revision=0,
            entrypoint="gui",
        )
        archived = sessions.archive_session(
            self.home,
            created["session_id"],
            expected_revision=saved["revision"],
            entrypoint="gui",
        )
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(sessions.list_sessions(self.home)["count"], 0)

        restored = sessions.restore_session(
            self.home,
            created["session_id"],
            expected_revision=archived["revision"],
            entrypoint="codex",
        )
        resumed = sessions.resume_session(self.home, created["session_id"])
        self.assertEqual(restored["status"], "draft")
        self.assertEqual(resumed["draft"]["summary"], "Keep this")
        self.assertFalse(resumed["write_recovery_required"])

    def test_self_analysis_uses_the_canonical_profile_and_shared_approval_path(self) -> None:
        profile_state = self.home.load_profile()
        profile_state["track"] = "chuto"
        persistence.write_toml(self.home.profile, profile_state)
        profile = {
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
            "career_theme": "Build dependable systems",
        }
        created = sessions.create_session(
            self.home,
            workflow="self_analysis",
            entrypoint="claude",
            subject={"profile_label": "Career values"},
        )
        saved = sessions.save_draft(
            self.home,
            created["session_id"],
            {"profile": profile},
            expected_revision=0,
            entrypoint="codex",
        )
        proposed = sessions.create_proposal(
            self.home,
            created["session_id"],
            expected_revision=saved["revision"],
            entrypoint="cli",
        )
        reviewed = proposed["proposal"]["event"]
        self.assertEqual(reviewed["career_context"]["career_theme"], "Build dependable systems")
        self.assertFalse(self.home.events.exists())

        approved = sessions.approve_proposal(
            self.home,
            created["session_id"],
            proposed["proposal"]["id"],
            expected_revision=proposed["revision"],
            entrypoint="gui",
        )
        self.assertEqual(approved["event"], {**reviewed, "status": "confirmed"})
        self.assertEqual(sessions.load_session(self.home, created["session_id"])["status"], "completed")

        changed = sessions.create_session(
            self.home,
            workflow="self_analysis",
            entrypoint="claude",
            subject={"profile_label": "Career values"},
        )
        changed_saved = sessions.save_draft(
            self.home,
            changed["session_id"],
            {"profile": {**profile, "career_theme": "Lead dependable systems"}},
            expected_revision=0,
            entrypoint="codex",
        )
        changed_proposal = sessions.create_proposal(
            self.home,
            changed["session_id"],
            expected_revision=changed_saved["revision"],
            entrypoint="gui",
        )
        self.assertEqual(changed_proposal["review_before"]["career_theme"], "Build dependable systems")
        self.assertEqual(
            changed_proposal["proposal"]["event"]["career_context"]["career_theme"],
            "Lead dependable systems",
        )


if __name__ == "__main__":
    unittest.main()
