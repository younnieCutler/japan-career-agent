import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "career-agent" / "career_agent.py"


def run(vault: Path, command: str, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, "--vault", str(vault), *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def output(result: subprocess.CompletedProcess[str]) -> dict:
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class CareerAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault = Path(self.tempdir.name) / "career-vault"
        output(run(self.vault, "init"))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def set_profile(self, **values: str | int) -> None:
        lines = [f'{key} = {json.dumps(value, ensure_ascii=False)}' for key, value in values.items()]
        (self.vault / "00-control" / "career-profile.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_init_creates_vault_contract_and_missing_vault_safe_stops(self) -> None:
        for directory in ("00-control", "01-capture", "02-state", "03-active", "04-evidence", "05-playbooks", "06-reference", "07-archive"):
            self.assertTrue((self.vault / directory).is_dir())
        self.assertTrue((self.vault / "00-control" / "career-profile.toml").exists())
        self.assertTrue((self.vault / "02-state" / "career-state.toml").exists())

        failed = subprocess.run([sys.executable, str(SCRIPT), "status"], text=True, capture_output=True, check=False)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("CAREER_VAULT is required", failed.stderr)

    def test_shinsotsu_requires_graduation_year_then_proposes_event(self) -> None:
        missing = output(run(self.vault, "run", "--mode", "chat", "--track", "shinsotsu", "--message", "신졸이고 가쿠치카 경험을 정리하고 싶어요"))
        self.assertTrue(missing["needs_confirmation"])
        self.assertIn("graduation_year", missing["question"])
        self.assertFalse((self.vault / "02-state" / "proposals.jsonl").exists())

        self.set_profile(track="shinsotsu", graduation_year=2027, target_role="LLMOps Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "신졸이고 가쿠치카 경험을 정리하고 싶어요"))
        self.assertEqual(proposed["track"], "shinsotsu")
        self.assertEqual(proposed["stage"], "学チカ・自己PR素材")
        self.assertEqual(proposed["flow_phase"], "preparation")
        self.assertEqual(proposed["language"], "ko")
        self.assertEqual(proposed["skill"]["references"], ["references/shinsotsu.md"])

    def test_chuto_japanese_request_routes_to_chuto_and_approval_persists(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "転職の面接を準備したい"))
        self.assertEqual(proposed["track"], "chuto")
        self.assertEqual(proposed["stage"], "面接")
        self.assertEqual(proposed["flow_phase"], "interview")
        self.assertEqual(proposed["language"], "ja")
        proposal_id = proposed["proposal"]["id"]

        failed = run(self.vault, "approve", proposal_id)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("require evidence", failed.stderr)
        approved = output(run(self.vault, "approve", proposal_id, "--evidence", "転職の面接を準備したい"))
        self.assertEqual(approved["event"]["status"], "confirmed")
        self.assertTrue((self.vault / "02-state" / "events.jsonl").exists())
        self.assertTrue((self.vault / "02-state" / "career-state.toml").exists())

    def test_numeric_claim_without_evidence_is_rejected(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "売上を30%改善した"))
        failed = run(self.vault, "approve", proposed["proposal"]["id"])
        self.assertEqual(failed.returncode, 2)
        self.assertIn("numeric claim", failed.stderr)

    def test_heartbeat_is_capped_and_discover_deduplicates(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "中途で面接の締切を確認したい"))
        output(run(self.vault, "approve", proposed["proposal"]["id"], "--evidence", "面接の締切を確認したい", "--deadline", "2099-01-01"))
        heartbeat = output(run(self.vault, "run", "--mode", "heartbeat"))
        self.assertLessEqual(len(heartbeat["actions"]), 3)
        self.assertIn("estimated_minutes", heartbeat["actions"][0])
        self.assertIn("flow_phase", heartbeat["actions"][0])
        postings = json.dumps([
            {"company": "A", "role": "Data", "url": "https://example.com/a"},
            {"company": "A", "role": "Data", "url": "https://example.com/a"},
        ], ensure_ascii=False)
        first = output(run(self.vault, "run", "--mode", "discover", input_text=postings))
        second = output(run(self.vault, "run", "--mode", "discover", input_text=postings))
        self.assertEqual(first["added"], 1)
        self.assertEqual(first["duplicates"], 1)
        self.assertEqual(second["duplicates"], 2)
        self.assertFalse(second["auto_apply"])

    def test_context_selector_excludes_capture_and_archive_bodies(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        trusted = self.vault / "05-playbooks" / "interview.md"
        trusted.write_text(
            "---\nagent_read: true\nagent_scope: chuto\nagent_stage: 面接\nstatus: verified\nsource_type: curated_practice\nreviewed_on: 2026-08-01\n---\n\n# Interview\n\nUseful private body.\n",
            encoding="utf-8",
        )
        capture = self.vault / "01-capture" / "raw.md"
        capture.write_text("---\nagent_read: true\n---\nRaw VTT must stay out.", encoding="utf-8")
        archive = self.vault / "07-archive" / "old.md"
        archive.write_text("---\nagent_read: true\n---\nOld personal example.", encoding="utf-8")
        legacy = self.vault / "03-projects" / "old.md"
        legacy.parent.mkdir()
        legacy.write_text("---\nagent_read: true\n---\nLegacy PARA material.", encoding="utf-8")

        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "中途で面接を準備したい"))
        self.assertEqual([item["path"] for item in proposed["context"]], ["05-playbooks/interview.md"])
        self.assertNotIn("Useful private body", json.dumps(proposed, ensure_ascii=False))
        indexed = output(run(self.vault, "index"))
        self.assertEqual(indexed["indexed"], 1)

        shared = output(run(self.vault, "context", "--stage", "面接"))
        self.assertTrue(shared["read_only"])
        self.assertFalse(shared["note_bodies_included"])
        self.assertEqual(shared["profile"]["target_role"], "Platform Engineer")
        self.assertEqual([item["path"] for item in shared["context"]], ["05-playbooks/interview.md"])

    def test_doctor_reports_profile_and_expired_reference_problems(self) -> None:
        incomplete = output(run(self.vault, "doctor"))
        self.assertTrue(incomplete["ok"])
        self.assertTrue(any("profile.track" in warning for warning in incomplete["warnings"]))
        self.set_profile(track="shinsotsu", graduation_year=2027, target_role="LLMOps Engineer", career_status="invalid")
        invalid = output(run(self.vault, "doctor"))
        self.assertFalse(invalid["ok"])
        self.assertTrue(any("career_status" in error for error in invalid["errors"]))

    def test_invalid_tool_input_safe_stops_and_rollback_restores_state(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        failed = run(self.vault, "run", "--mode", "discover", input_text=json.dumps({"company": "missing url"}))
        self.assertEqual(failed.returncode, 2)
        error = json.loads(failed.stderr)
        self.assertTrue(error["safe_stop"])
        self.assertFalse(error["external_side_effect"])

        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "中途の面接を準備する"))
        approved = output(run(self.vault, "approve", proposed["proposal"]["id"], "--evidence", "中途の面接を準備する"))
        state_path = self.vault / "02-state" / "career-state.toml"
        state_path.write_text(state_path.read_text(encoding="utf-8").replace('stage = "面接"', 'stage = "退職・入社準備"'), encoding="utf-8")
        self.assertEqual(output(run(self.vault, "status"))["state"]["stage"], "退職・入社準備")
        rolled = output(run(self.vault, "rollback", approved["version"]))
        self.assertTrue(rolled["rolled_back"])
        self.assertEqual(rolled["state"]["last_event_id"], approved["event"]["id"])

    def test_approve_failure_logs_trajectory(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "売上を30%改善した"))
        failed = run(self.vault, "approve", proposed["proposal"]["id"])
        self.assertEqual(failed.returncode, 2)

        trajectories = read_jsonl(self.vault / "02-state" / "trajectories.jsonl")
        last = trajectories[-1]
        self.assertEqual(last["mode"], "approve")
        self.assertFalse(last["verify"]["passed"])
        self.assertTrue(last["correct"]["escalated_to_user"])

    def test_discover_drops_invalid_postings_but_keeps_the_rest(self) -> None:
        postings = json.dumps([
            {"company": "A", "role": "Data", "url": "https://example.com/a"},
            {"company": "B", "role": "Data"},
        ], ensure_ascii=False)
        result = output(run(self.vault, "run", "--mode", "discover", input_text=postings))
        self.assertEqual(result["added"], 1)
        self.assertEqual(result["dropped"], 1)

        trajectories = read_jsonl(self.vault / "02-state" / "trajectories.jsonl")
        last = trajectories[-1]
        self.assertEqual(last["correct"]["action"], "dropped_invalid_postings")
        self.assertEqual(last["correct"]["dropped"], 1)

    def test_chat_repeated_missing_info_flags_retry(self) -> None:
        self.set_profile(track="shinsotsu", target_role="LLMOps Engineer", career_status="active")
        message = "신졸이고 가쿠치카 경험을 정리하고 싶어요"
        first = output(run(self.vault, "run", "--mode", "chat", "--message", message))
        output(run(self.vault, "run", "--mode", "chat", "--message", message))
        third = output(run(self.vault, "run", "--mode", "chat", "--message", message))
        self.assertNotIn("asked before", first["question"])
        self.assertIn("asked before", third["question"])

    def test_generic_followup_keeps_current_stage_instead_of_resetting(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "内定をもらったので条件を確認したい"))
        self.assertEqual(proposed["stage"], "内定・条件交渉")
        output(run(self.vault, "approve", proposed["proposal"]["id"], "--evidence", "内定をもらったので条件を確認したい"))

        followup = output(run(self.vault, "run", "--mode", "chat", "--message", "다음에 뭘 해야 해?"))
        self.assertEqual(followup["stage"], "内定・条件交渉")

    def test_context_selector_excludes_expired_notes(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        trusted = self.vault / "05-playbooks" / "interview.md"
        trusted.write_text(
            "---\nagent_read: true\nagent_scope: chuto\nagent_stage: 面接\nstatus: verified\nsource_type: curated_practice\nreviewed_on: 2026-08-01\n---\n\n# Interview\n\nUseful.\n",
            encoding="utf-8",
        )
        expired = self.vault / "05-playbooks" / "old-interview.md"
        expired.write_text(
            "---\nagent_read: true\nagent_scope: chuto\nagent_stage: 面接\nstatus: verified\nsource_type: curated_practice\nreviewed_on: 2020-01-01\nexpires_on: 2020-06-01\n---\n\n# Old Interview\n\nStale.\n",
            encoding="utf-8",
        )
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "中途で面接を準備したい"))
        self.assertEqual([item["path"] for item in proposed["context"]], ["05-playbooks/interview.md"])

    def test_heartbeat_surfaces_profile_deadline(self) -> None:
        self.set_profile(
            track="chuto",
            target_role="Data Engineer",
            career_status="active",
            current_company_end_date=(date.today() + timedelta(days=3)).isoformat(),
        )
        heartbeat = output(run(self.vault, "run", "--mode", "heartbeat"))
        reasons = [action["reason"] for action in heartbeat["actions"]]
        self.assertIn("profile_deadline", reasons)


if __name__ == "__main__":
    unittest.main()
