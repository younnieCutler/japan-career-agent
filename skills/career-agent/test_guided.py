"""Deterministic tests for the P1 guided thin frontend."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "career-agent" / "career_agent.py"
sys.path.insert(0, str(SCRIPT.parent))
from guided import build_summary, derive_actions, resolve_choice  # noqa: E402


def run(vault: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--vault", str(vault)],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def payload(result: subprocess.CompletedProcess[str]) -> dict:
    if result.stdout.strip():
        return json.loads(result.stdout)
    return json.loads(result.stderr)


class GuidedFrontendTests(unittest.TestCase):
    def test_action_derivation_preserves_empty_unknown_and_conflict_states(self) -> None:
        fresh = build_summary(
            initialized=False,
            vault="/tmp/vault",
            workspace={"path": "/tmp/work", "exists": True},
        )
        fresh_ids = [item["id"] for item in derive_actions(fresh)]
        self.assertEqual(fresh_ids[:2], ["complete_setup", "inspect_status"])
        self.assertIn("exit", fresh_ids)

        review = build_summary(
            initialized=True,
            vault="/tmp/vault",
            profile={"track": "chuto"},
            state={},
            workspace={"path": "/tmp/work", "exists": True},
            personal_profile={
                "skills": {"python": {"state": "unknown", "reason": "missing evidence"}},
                "values": {"work_style": {"state": "conflict", "reason": "two sources disagree"}},
            },
        )
        review_ids = [item["id"] for item in derive_actions(review)]
        self.assertIn("inspect_unknown", review_ids)
        self.assertIn("inspect_conflict", review_ids)
        self.assertNotIn("approve_proposal", review_ids)

    def test_choice_resolution_is_stable_and_rejects_unknown_ids(self) -> None:
        actions = derive_actions(
            build_summary(
                initialized=True,
                vault="/tmp/vault",
                profile={"track": "chuto"},
                workspace={"path": "/tmp/work", "exists": True},
            )
        )
        self.assertEqual(resolve_choice("1", actions), "inspect_status")
        self.assertEqual(resolve_choice("q", actions), "exit")
        self.assertIsNone(resolve_choice("recommend_company", actions))

    def test_fresh_menu_is_read_only_and_setup_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            work = root / "workspace"
            work.mkdir()
            result = run(vault, "guided", cwd=work)
            self.assertEqual(result.returncode, 0, result.stderr)
            menu = json.loads(result.stdout)
            self.assertEqual(menu["mode"], "guided")
            self.assertEqual(menu["guided"]["state"], "needs_input")
            self.assertEqual(menu["guided"]["available_actions"][0]["id"], "complete_setup")
            self.assertFalse(menu["state_changed"])
            self.assertFalse(vault.exists())

    def test_invalid_and_cancel_choices_are_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            work = root / "workspace"
            work.mkdir()
            setup = run(vault, "setup", "--track", "chuto", cwd=work)
            self.assertEqual(setup.returncode, 0, setup.stderr)
            events_path = vault / "02-state" / "events.jsonl"
            before = events_path.read_bytes() if events_path.exists() else b""

            invalid = run(vault, "guided", "--choice", "not-an-action", cwd=work)
            self.assertEqual(invalid.returncode, 2)
            invalid_payload = json.loads(invalid.stdout)
            self.assertEqual(invalid_payload["selection"]["status"], "invalid")
            self.assertFalse(invalid_payload["state_changed"])
            self.assertTrue(invalid_payload["guided"]["available_actions"])

            cancelled = run(vault, "guided", "--choice", "cancel", cwd=work)
            self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
            self.assertEqual(json.loads(cancelled.stdout)["selection"]["status"], "cancelled")
            after = events_path.read_bytes() if events_path.exists() else b""
            self.assertEqual(before, after)

    def test_pending_approval_requires_confirmation_and_uses_canonical_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            work = root / "workspace"
            work.mkdir()
            self.assertEqual(run(vault, "setup", "--track", "chuto", cwd=work).returncode, 0)
            proposed = run(
                vault,
                "run",
                "--mode",
                "chat",
                "--message",
                "prepare interview",
                cwd=work,
            )
            self.assertEqual(proposed.returncode, 0, proposed.stderr)
            proposal_id = json.loads(proposed.stdout)["proposal"]["id"]

            no_confirm = run(vault, "guided", "--choice", "approve_proposal", cwd=work)
            self.assertEqual(no_confirm.returncode, 0, no_confirm.stderr)
            no_confirm_payload = json.loads(no_confirm.stdout)
            self.assertEqual(no_confirm_payload["selection"]["status"], "confirmation_required")
            self.assertFalse(no_confirm_payload["state_changed"])
            self.assertEqual(json.loads(run(vault, "status", cwd=work).stdout)["pending_proposals"], 1)

            approved = run(
                vault,
                "guided",
                "--choice",
                "approve_proposal",
                "--proposal-id",
                proposal_id,
                "--confirm",
                "--evidence",
                "prepare interview",
                cwd=work,
            )
            self.assertEqual(approved.returncode, 0, approved.stderr)
            approved_payload = json.loads(approved.stdout)
            self.assertEqual(approved_payload["selection"]["status"], "completed")
            self.assertTrue(approved_payload["state_changed"])
            self.assertEqual(approved_payload["action_result"]["event"]["status"], "confirmed")
            self.assertEqual(approved_payload["guided"]["summary"]["pending_proposals"], 0)


if __name__ == "__main__":
    unittest.main()
