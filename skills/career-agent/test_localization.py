"""Regression tests for immediate language routing and localized human UX."""

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
from localization import SUPPORTED_LANGUAGES, UX_TEXT  # noqa: E402


def run(vault: Path, command: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, "--vault", str(vault), *args],
        cwd=vault.parent,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


class LocalizationTests(unittest.TestCase):
    def test_catalog_keys_are_complete(self) -> None:
        expected = set(UX_TEXT[SUPPORTED_LANGUAGES[0]])
        self.assertEqual(set(UX_TEXT), set(SUPPORTED_LANGUAGES))
        for language in SUPPORTED_LANGUAGES:
            self.assertEqual(set(UX_TEXT[language]), expected, language)

    def test_chat_response_language_is_a_hard_gate_each_turn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "vault"
            setup = run(vault, "setup", "--track", "chuto", "--language", "ko")
            self.assertEqual(setup.returncode, 0, setup.stderr)
            fixtures = (
                ("面接の準備をしたい", "状態:", ("상태:", "State:")),
                ("그럼 이력서는?", "상태:", ("状態:", "State:")),
                ("Can you review my resume?", "State:", ("상태:", "状態:")),
            )
            for message, marker, forbidden_markers in fixtures:
                result = run(vault, "run", "--mode", "chat", "--message", message, "--format", "human")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(marker, result.stdout)
                for forbidden in forbidden_markers:
                    self.assertNotIn(forbidden, result.stdout)
            event_json = run(vault, "run", "--mode", "chat", "--message", "Prepare an interview", "--format", "json")
            event_payload = json.loads(event_json.stdout)
            self.assertEqual(event_payload["ux"]["next"]["actions"][1]["label"], "Confirm")

    def test_status_and_guided_preserve_heartbeat_action_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "heartbeat-vault"
            self.assertEqual(run(vault, "setup", "--track", "chuto", "--language", "ko").returncode, 0)
            heartbeat = run(vault, "run", "--mode", "heartbeat", "--format", "json")
            self.assertEqual(heartbeat.returncode, 0, heartbeat.stderr)

            status = json.loads(run(vault, "status", "--format", "json").stdout)
            self.assertEqual(status["pending_kind"], "heartbeat")
            self.assertEqual(status["ux"]["next"]["actions"][1]["label"], "확인 완료로 처리")
            status_human = run(vault, "status", "--format", "human")
            self.assertIn("확인 완료로 처리", status_human.stdout)
            self.assertIn("확정된 경력 정보는 바뀌지 않고", status_human.stdout)

            guided_human = run(vault, "guided", "--format", "human")
            self.assertIn("확인 완료로 처리", guided_human.stdout)
            self.assertNotIn("확인하기", guided_human.stdout)

            event_vault = Path(directory) / "event-vault"
            self.assertEqual(run(event_vault, "setup", "--track", "chuto", "--language", "ko").returncode, 0)
            event = run(event_vault, "run", "--mode", "chat", "--message", "prepare interview", "--format", "json")
            self.assertEqual(event.returncode, 0, event.stderr)
            event_status = json.loads(run(event_vault, "status", "--format", "json").stdout)
            self.assertEqual(event_status["pending_kind"], "event")
            self.assertEqual(event_status["ux"]["next"]["actions"][1]["label"], "확정하기")

    def test_profile_language_is_used_by_message_free_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "vault"
            setup = run(vault, "setup", "--track", "chuto", "--language", "ja")
            self.assertEqual(setup.returncode, 0, setup.stderr)
            for command in ("status", "proposals", "guided"):
                result = run(vault, command, "--format", "human")
                self.assertEqual(result.returncode, 0, (command, result.stderr))
                self.assertIn("状態", result.stdout, command)
                self.assertNotIn("State:", result.stdout, command)

    def test_korean_human_output_does_not_leak_internal_terms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "vault"
            self.assertEqual(run(vault, "setup", "--track", "chuto", "--language", "ko").returncode, 0)
            result = run(vault, "status", "--format", "human")
            self.assertEqual(result.returncode, 0, result.stderr)
            lowered = result.stdout.casefold()
            for forbidden in ("proposal", "canonical state", "heartbeat proposal", "projection", "needs_confirmation", "approve proposal"):
                self.assertNotIn(forbidden, lowered)

    def test_unknown_and_conflict_keep_domain_labels_on_first_display(self) -> None:
        sys.path.insert(0, str(SCRIPT.parent))
        from ux import attach, render_human  # noqa: E402

        unknown = render_human(attach("personal-profile", {"skills": {"x": {"state": "unknown"}}}, language="ko"))
        conflict = render_human(attach("personal-profile", {"skills": {"x": {"state": "conflict"}}}, language="ja"))
        self.assertIn("확인되지 않음 (Unknown)", unknown)
        self.assertIn("情報の矛盾 (Conflict)", conflict)

    def test_heartbeat_approval_is_queue_only_and_localized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "vault"
            self.assertEqual(run(vault, "setup", "--track", "chuto", "--language", "ko").returncode, 0)
            heartbeat = run(vault, "run", "--mode", "heartbeat", "--format", "json")
            self.assertEqual(heartbeat.returncode, 0, heartbeat.stderr)
            heartbeat_payload = json.loads(heartbeat.stdout)
            self.assertEqual(heartbeat_payload["ux"]["next"]["actions"][1]["label"], "확인 완료로 처리")
            proposals = json.loads(run(vault, "proposals", "--format", "json").stdout)
            proposal_id = next(item["id"] for item in proposals["proposals"] if item["kind"] == "heartbeat")
            human = run(vault, "approve", proposal_id, "--format", "human")
            self.assertEqual(human.returncode, 0, human.stderr)
            self.assertIn("확정된 경력 정보는 바뀌지 않았습니다", human.stdout)
            self.assertIn("확인 대기 목록", human.stdout)

            run(vault, "run", "--mode", "heartbeat", "--format", "json")
            proposals = json.loads(run(vault, "proposals", "--format", "json").stdout)
            second_id = next(item["id"] for item in proposals["proposals"] if item["kind"] == "heartbeat")
            events = vault / "02-state" / "events.jsonl"
            state = vault / "02-state" / "career-state.toml"
            events_before = events.read_bytes() if events.exists() else b""
            state_before = state.read_bytes()
            approved = run(vault, "approve", second_id, "--format", "json")
            self.assertEqual(approved.returncode, 0, approved.stderr)
            payload = json.loads(approved.stdout)
            self.assertFalse(payload["applied"])
            self.assertEqual(events_before, events.read_bytes() if events.exists() else b"")
            self.assertEqual(state_before, state.read_bytes())


if __name__ == "__main__":
    unittest.main()
