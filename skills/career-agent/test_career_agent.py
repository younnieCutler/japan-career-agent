import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "career-agent" / "career_agent.py"


def run(home: Path, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--home", str(home), *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def output(result: subprocess.CompletedProcess[str]) -> dict:
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class CareerAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.home = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_chat_proposes_and_approval_persists_event(self) -> None:
        proposed = output(run(self.home, "run", "--mode", "chat", "--message", "신졸이고 学チカ 경험을 정리하고 싶어요"))
        self.assertEqual(proposed["track"], "shinsotsu")
        self.assertEqual(proposed["stage"], "学チカ・自己PR素材")
        self.assertEqual(proposed["language"], "ko")
        self.assertEqual(proposed["skill"]["references"], ["references/shinsotsu.md"])
        proposal_id = proposed["proposal"]["id"]
        failed = run(self.home, "approve", proposal_id)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("require evidence", failed.stderr)

        approved = output(run(self.home, "approve", proposal_id, "--evidence", "사용자 메시지에 学チカ 경험을 정리하고 싶다고 명시됨"))
        self.assertEqual(approved["event"]["status"], "confirmed")
        self.assertEqual(len((self.home / "events.jsonl").read_text().splitlines()), 1)

    def test_numeric_claim_without_evidence_is_rejected(self) -> None:
        proposed = output(run(self.home, "run", "--mode", "chat", "--track", "chuto", "--message", "売上を30%改善した"))
        failed = run(self.home, "approve", proposed["proposal"]["id"])
        self.assertEqual(failed.returncode, 2)
        self.assertIn("numeric claim", failed.stderr)

    def test_ambiguous_track_stops_before_creating_proposal(self) -> None:
        result = output(run(self.home, "run", "--mode", "chat", "--message", "I need help with my career"))
        self.assertTrue(result["needs_confirmation"])
        self.assertFalse((self.home / "proposals.jsonl").exists())

    def test_heartbeat_is_capped_and_discover_deduplicates(self) -> None:
        proposed = output(run(self.home, "run", "--mode", "chat", "--message", "中途で面接の締切を確認したい"))
        output(run(self.home, "approve", proposed["proposal"]["id"], "--evidence", "面接の締切を確認したい", "--deadline", "2099-01-01"))
        heartbeat = output(run(self.home, "run", "--mode", "heartbeat"))
        self.assertLessEqual(len(heartbeat["actions"]), 3)
        self.assertIn("estimated_minutes", heartbeat["actions"][0])
        postings = json.dumps([
            {"company": "A", "role": "Data", "url": "https://example.com/a"},
            {"company": "A", "role": "Data", "url": "https://example.com/a"},
        ], ensure_ascii=False)
        first = output(run(self.home, "run", "--mode", "discover", input_text=postings))
        second = output(run(self.home, "run", "--mode", "discover", input_text=postings))
        self.assertEqual(first["added"], 1)
        self.assertEqual(first["duplicates"], 1)
        self.assertEqual(second["duplicates"], 2)
        self.assertFalse(second["auto_apply"])

    def test_invalid_tool_input_safe_stops_without_side_effects(self) -> None:
        failed = run(self.home, "run", "--mode", "discover", input_text=json.dumps({"company": "missing url"}))
        self.assertEqual(failed.returncode, 2)
        error = json.loads(failed.stderr)
        self.assertTrue(error["safe_stop"])
        self.assertFalse(error["external_side_effect"])

    def test_rollback_restores_version(self) -> None:
        proposed = output(run(self.home, "run", "--mode", "chat", "--message", "中途の面接を準備する"))
        approved = output(run(self.home, "approve", proposed["proposal"]["id"], "--evidence", "中途の面接を準備する"))
        rolled = output(run(self.home, "rollback", approved["version"]))
        self.assertTrue(rolled["rolled_back"])
        self.assertEqual(rolled["state"]["last_event_id"], approved["event"]["id"])


if __name__ == "__main__":
    unittest.main()
