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
        self.assertEqual(resumed["session"]["stage"], "experience_evidence")
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
        self.assertEqual(sessions.load_session(self.home, created["session_id"])["stage"], "experience_evidence")
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

    def test_rejected_approval_leaves_canonical_state_unchanged(self) -> None:
        created = sessions.create_session(self.home)
        sessions.save_draft(self.home, created["session_id"], {"summary": "증거 없는 메모"})
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

        for value, message in ((999, "newer"), (None, "missing"), (0, "migration")):
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


if __name__ == "__main__":
    unittest.main()
