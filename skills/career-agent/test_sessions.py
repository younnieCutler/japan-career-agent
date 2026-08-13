"""Contract tests for the resumable GUI 棚卸し session store."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

import persistence  # noqa: E402
import sessions  # noqa: E402
from models import CareerError  # noqa: E402
from vault import CareerVault, initialize_vault  # noqa: E402


class SessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.tempdir.name) / "vault"
        initialize_vault(self.vault_path)
        self.home = CareerVault(self.vault_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_autosave_survives_a_fresh_process_and_marks_unconfirmed_input(self) -> None:
        created = sessions.create_session(self.home)
        sessions.save_draft(
            self.home,
            created["session_id"],
            {"summary": "배포 장애를 복구했다", "non_work": False},
        )

        resumed = sessions.resume_session(
            CareerVault(self.vault_path), created["session_id"]
        )

        self.assertEqual(resumed["draft"]["summary"], "배포 장애를 복구했다")
        self.assertTrue(resumed["unconfirmed_input"])
        self.assertEqual(resumed["session"]["stage"], "experience")
        self.assertNotIn("page", json.dumps(resumed, ensure_ascii=False))

    def test_interrupted_checkpoint_keeps_the_last_completed_checkpoint(self) -> None:
        created = sessions.create_session(self.home)
        session_path = sessions.session_path(self.home, created["session_id"])
        before = session_path.read_text(encoding="utf-8")

        with patch.object(persistence.os, "replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                sessions.checkpoint_session(
                    self.home,
                    created["session_id"],
                    stage="review",
                    current_item_ref="experience_1",
                )

        self.assertEqual(session_path.read_text(encoding="utf-8"), before)
        self.assertEqual(sessions.load_session(self.home, created["session_id"])["stage"], "experience")
        self.assertEqual(list(session_path.parent.glob(".*.tmp")), [])

    def test_draft_writes_never_touch_canonical_state(self) -> None:
        state_files = {
            path: path.read_bytes()
            for path in self.home.state_dir.iterdir()
            if path.is_file()
        }
        created = sessions.create_session(self.home)
        sessions.save_draft(
            self.home,
            created["session_id"],
            {"summary": "학회 발표", "non_work": True},
        )

        self.assertEqual(
            state_files,
            {path: path.read_bytes() for path in self.home.state_dir.iterdir() if path.is_file()},
        )
        self.assertFalse(self.home.events.exists())
        self.assertFalse(self.home.proposals.exists())
        self.assertEqual(sessions.transient_root(self.home), (self.vault_path / "01-capture" / "gui").resolve())
        self.assertNotIn("02-state", str(sessions.session_path(self.home, created["session_id"])))
        self.assertNotIn(".career-agent", str(sessions.session_path(self.home, created["session_id"])))

    def test_storage_lifetimes_are_separate(self) -> None:
        paths = sessions.storage_paths(self.home)
        self.assertEqual(paths["sessions"].parent, (self.vault_path / "01-capture" / "gui").resolve())
        self.assertEqual(paths["drafts"].parent, (self.vault_path / "01-capture" / "gui").resolve())
        self.assertNotEqual(paths["sessions"], paths["drafts"])
        self.assertIn("transient", sessions.storage_lifetime("session"))
        self.assertIn("durable", sessions.storage_lifetime("case"))
        self.assertIn("durable", sessions.storage_lifetime("artifact"))
        self.assertIn("canonical", sessions.storage_lifetime("evidence"))

    def test_proposal_uses_strict_approval_and_repeated_approval_is_idempotent(self) -> None:
        created = sessions.create_session(self.home)
        sessions.save_draft(
            self.home,
            created["session_id"],
            {
                "summary": "배포 장애를 복구했다",
                "evidence": ["incident review"],
                "role": "운영 담당",
                "direct_actions": ["로그를 확인했다"],
                "non_work": False,
            },
        )
        proposal = sessions.create_proposal(self.home, created["session_id"])
        self.assertEqual(proposal["proposal"]["status"], "pending")
        self.assertFalse(self.home.events.exists())

        approved = sessions.approve_proposal(
            self.home, created["session_id"], proposal["proposal"]["id"]
        )
        repeated = sessions.approve_proposal(
            self.home, created["session_id"], proposal["proposal"]["id"]
        )

        self.assertTrue(approved["approved"])
        self.assertTrue(repeated["idempotent"])
        self.assertEqual(len(persistence.read_jsonl(self.home.events)), 1)
        self.assertEqual(sessions.load_session(self.home, created["session_id"])["stage"], "completed")

    def test_editing_a_draft_reproposes_it_instead_of_returning_the_stale_snapshot(self) -> None:
        """What the screen shows and what approval writes have to be the same text.

        A proposal is a snapshot of the draft at one moment. If the draft moves afterwards and the
        proposal does not, the user reads the new version and the ledger records the old one --
        a silent wrong fact in an evidence-first product.
        """
        created = sessions.create_session(self.home)
        session_id = created["session_id"]
        base = {
            "evidence": ["incident review"],
            "role": "운영 담당",
            "direct_actions": ["로그를 확인했다"],
            "non_work": False,
        }
        sessions.save_draft(self.home, session_id, {**base, "summary": "배포 장애를 복구했다"})
        first = sessions.create_proposal(self.home, session_id)

        sessions.save_draft(self.home, session_id, {**base, "summary": "결제 지연을 복구했다"})
        second = sessions.create_proposal(self.home, session_id)

        self.assertEqual(second["proposal"]["event"]["summary"], "결제 지연을 복구했다")
        approved = sessions.approve_proposal(self.home, session_id, second["proposal"]["id"])
        self.assertEqual(approved["event"]["summary"], "결제 지연을 복구했다")
        self.assertEqual(len(persistence.read_jsonl(self.home.events)), 1)
        self.assertEqual(first["proposal"]["id"], second["proposal"]["id"])

    def test_approving_a_snapshot_the_draft_has_outgrown_is_refused(self) -> None:
        """Re-proposing is a path, not a guarantee -- nothing forces a caller down it.

        The proposal id is stable for the session, so the approve button a client rendered before
        an autosave stays callable afterwards. Without a check at approval the older wording lands
        in the ledger while the newer one is what the user is reading.
        """
        created = sessions.create_session(self.home)
        session_id = created["session_id"]
        base = {"evidence": ["incident review"], "role": "운영 담당", "non_work": False}
        sessions.save_draft(self.home, session_id, {**base, "summary": "배포 장애를 복구했다"})
        proposal_id = sessions.create_proposal(self.home, session_id)["proposal"]["id"]

        sessions.save_draft(self.home, session_id, {**base, "summary": "결제 지연을 복구했다"})

        with self.assertRaises(CareerError) as refused:
            sessions.approve_proposal(self.home, session_id, proposal_id)

        self.assertEqual(refused.exception.code, "PROPOSAL_STALE")
        self.assertFalse(self.home.events.exists())
        self.assertEqual(sessions.load_session(self.home, session_id)["stage"], "experience")

        renewed = sessions.create_proposal(self.home, session_id)
        approved = sessions.approve_proposal(self.home, session_id, renewed["proposal"]["id"])

        self.assertEqual(approved["event"]["summary"], "결제 지연을 복구했다")
        self.assertEqual(len(persistence.read_jsonl(self.home.events)), 1)

    def test_the_screen_shows_the_snapshot_it_asks_the_user_to_approve(self) -> None:
        """The server sends the event; a button beside text the user never saw is unreviewable.

        And the snapshot has to leave the screen when the draft moves, so the browser cannot keep
        offering an approval the server will now refuse.
        """
        script = (Path(__file__).parent / "gui" / "static" / "screens.js").read_text(encoding="utf-8")
        dialog = script.split("function approvalDialog", 1)[1].split("async function reviewCase", 1)[0]
        editor = script.split("function careerDraftForm", 1)[1].split("function profileSummary", 1)[0]

        self.assertIn("snapshotView(event)", dialog)
        self.assertIn("await approveAction()", dialog)
        self.assertIn("approvalDialog(proposal.event", editor)
        self.assertIn("/api/workflows/propose", editor)
        self.assertIn("/api/workflows/approve", editor)
        self.assertLess(editor.index("/api/workflows/propose"), editor.index("/api/workflows/approve"))

    def test_an_unchanged_draft_reuses_the_pending_proposal(self) -> None:
        created = sessions.create_session(self.home)
        session_id = created["session_id"]
        sessions.save_draft(
            self.home,
            session_id,
            {"summary": "배포 장애를 복구했다", "evidence": ["incident review"], "non_work": False},
        )

        first = sessions.create_proposal(self.home, session_id)
        second = sessions.create_proposal(self.home, session_id)

        self.assertEqual(first["proposal"]["id"], second["proposal"]["id"])
        self.assertEqual(first["proposal"]["created_at"], second["proposal"]["created_at"])
        self.assertEqual(len(sessions._proposal_rows(self.home)), 1)

    def test_an_approved_session_is_closed_to_further_drafts_and_proposals(self) -> None:
        """The next experience belongs in the next session, not on top of an approved one."""
        created = sessions.create_session(self.home)
        session_id = created["session_id"]
        sessions.save_draft(
            self.home,
            session_id,
            {"summary": "배포 장애를 복구했다", "evidence": ["incident review"], "non_work": False},
        )
        proposal = sessions.create_proposal(self.home, session_id)
        sessions.approve_proposal(self.home, session_id, proposal["proposal"]["id"])

        with self.assertRaises(CareerError) as saving:
            sessions.save_draft(self.home, session_id, {"summary": "다른 경험", "non_work": False})
        with self.assertRaises(CareerError) as proposing:
            sessions.create_proposal(self.home, session_id)

        self.assertEqual(saving.exception.code, "SESSION_COMPLETED")
        self.assertEqual(proposing.exception.code, "SESSION_COMPLETED")
        self.assertEqual(len(persistence.read_jsonl(self.home.events)), 1)

    def test_active_sessions_are_discoverable_without_client_side_memory(self) -> None:
        """A random port gives the browser a new origin, so localStorage cannot carry the id."""
        first = sessions.create_session(self.home)
        sessions.save_draft(
            self.home, first["session_id"], {"summary": "배포 장애를 복구했다", "non_work": False}
        )

        listed = sessions.list_sessions(CareerVault(self.vault_path))

        self.assertEqual([row["session_id"] for row in listed["sessions"]], [first["session_id"]])

    def test_rejected_approval_leaves_canonical_state_unchanged(self) -> None:
        created = sessions.create_session(self.home)
        sessions.save_draft(
            self.home,
            created["session_id"],
            {
                "summary": "장애를 30% 줄였다",
                "outcome_state": "quantitative",
                "metrics": ["30%"],
            },
        )
        proposal = sessions.create_proposal(self.home, created["session_id"])
        before_state = self.home.state_toml.read_bytes()

        with self.assertRaises(CareerError):
            sessions.approve_proposal(
                self.home, created["session_id"], proposal["proposal"]["id"]
            )

        self.assertFalse(self.home.events.exists())
        self.assertEqual(self.home.state_toml.read_bytes(), before_state)
        stored = persistence.read_jsonl(self.home.proposals)[0]
        self.assertEqual(stored["status"], "pending")

    def test_proposal_and_approval_retries_do_not_duplicate_or_lose_session_link(self) -> None:
        created = sessions.create_session(self.home)
        sessions.save_draft(
            self.home,
            created["session_id"],
            {"summary": "재시도 가능한 기록", "evidence": ["review"], "non_work": False},
        )
        with patch.object(sessions, "_checkpoint_unlocked", side_effect=OSError("checkpoint interrupted")):
            with self.assertRaises(OSError):
                sessions.create_proposal(self.home, created["session_id"])
        retried = sessions.create_proposal(self.home, created["session_id"])
        self.assertEqual(len(persistence.read_jsonl(self.home.proposals)), 1)
        self.assertEqual(retried["proposal"]["status"], "pending")

        with patch.object(sessions, "_mark_approved_session", side_effect=OSError("checkpoint interrupted")):
            with self.assertRaises(OSError):
                sessions.approve_proposal(
                    self.home, created["session_id"], retried["proposal"]["id"]
                )
        repeated = sessions.approve_proposal(
            self.home, created["session_id"], retried["proposal"]["id"]
        )
        self.assertTrue(repeated["idempotent"])
        self.assertEqual(len(persistence.read_jsonl(self.home.events)), 1)
        self.assertEqual(sessions.load_session(self.home, created["session_id"])["stage"], "completed")

    def test_session_schema_versions_are_explicit_and_non_destructive(self) -> None:
        created = sessions.create_session(self.home)
        path = sessions.session_path(self.home, created["session_id"])
        original = json.loads(path.read_text(encoding="utf-8"))

        for value, message in ((999, "newer"), (None, "missing")):
            record = dict(original)
            if value is None:
                record.pop("session_schema_version")
            else:
                record["session_schema_version"] = value
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(CareerError, message):
                sessions.load_session(self.home, created["session_id"])
            self.assertEqual(path.read_text(encoding="utf-8"), json.dumps(record) + "\n")

        path.write_text(json.dumps(original) + "\n", encoding="utf-8")
        self.assertEqual(sessions.load_session(self.home, created["session_id"])["session_id"], created["session_id"])

    def test_v0_fixture_migrates_semantic_page_to_stage_without_rewriting(self) -> None:
        created = sessions.create_session(self.home)
        path = sessions.session_path(self.home, created["session_id"])
        current = json.loads(path.read_text(encoding="utf-8"))
        legacy = dict(current)
        legacy.pop("stage")
        legacy["session_schema_version"] = 0
        legacy["page"] = "review"
        legacy_bytes = (json.dumps(legacy) + "\n").encode("utf-8")
        path.write_bytes(legacy_bytes)

        resumed = sessions.resume_session(self.home, created["session_id"])

        self.assertEqual(resumed["session"]["stage"], "review")
        self.assertNotIn("page", resumed["session"])
        self.assertEqual(path.read_bytes(), legacy_bytes)

    def test_a_v0_session_resumes_with_its_own_v0_draft(self) -> None:
        """A real v0 vault has a v0 draft too; migrating only the session strands the pair.

        The session migration is worth nothing if `resume_session` then refuses the draft written
        beside it — which is what happens when the fixture bumps only one of the two files.
        """
        created = sessions.create_session(self.home)
        session_id = created["session_id"]
        sessions.save_draft(self.home, session_id, {"summary": "배포 장애를 복구했다", "non_work": False})

        for path, changes in (
            (sessions.session_path(self.home, session_id), {"page": "review"}),
            (sessions.draft_path(self.home, session_id), {}),
        ):
            record = json.loads(path.read_text(encoding="utf-8"))
            record["session_schema_version"] = 0
            record.pop("stage", None)
            record.update(changes)
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")

        resumed = sessions.resume_session(self.home, session_id)

        self.assertEqual(resumed["session"]["stage"], "review")
        self.assertEqual(resumed["draft"]["summary"], "배포 장애를 복구했다")


if __name__ == "__main__":
    unittest.main()
