"""Skill-First Gate A-C: registry, selection, and the skill-open/skill-report lifecycle."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "career-agent" / "career_agent.py"
CAREER_ROOT = ROOT / "skills" / "career-agent"
SKILLS_ROOT = ROOT / "skills"
if str(CAREER_ROOT) not in sys.path:
    sys.path.insert(0, str(CAREER_ROOT))

import models  # noqa: E402
import skill_registry  # noqa: E402
import validation  # noqa: E402
from models import CareerError  # noqa: E402
from routing import select_skill  # noqa: E402


def run(vault: Path, command: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, "--vault", str(vault), *args],
        text=True, encoding="utf-8", capture_output=True, check=False,
    )


def output(result: subprocess.CompletedProcess[str]) -> dict:
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class RegistryTests(unittest.TestCase):
    def test_registry_discovers_all_thirteen_skill_directories(self) -> None:
        entries = skill_registry.discover(SKILLS_ROOT)
        names = {entry["skill"] for entry in entries}
        on_disk = {p.name for p in SKILLS_ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}
        self.assertEqual(names, on_disk)
        self.assertEqual(len(entries), 13)

    def test_every_discovered_skill_has_an_execution_class(self) -> None:
        for entry in skill_registry.discover(SKILLS_ROOT):
            self.assertIn(entry["execution"], {"deterministic", "hybrid", "host_required"})

    def test_directory_missing_from_skill_execution_raises(self) -> None:
        original = dict(models.SKILL_EXECUTION)
        try:
            models.SKILL_EXECUTION.pop("career-document")
            with self.assertRaises(CareerError):
                skill_registry.discover(SKILLS_ROOT)
        finally:
            models.SKILL_EXECUTION.clear()
            models.SKILL_EXECUTION.update(original)

    def test_find_unknown_skill_raises(self) -> None:
        with self.assertRaises(CareerError):
            skill_registry.find(SKILLS_ROOT, "not-a-real-skill")


class SelectionTests(unittest.TestCase):
    def test_select_skill_is_selected_not_completed(self) -> None:
        selection = select_skill(SKILLS_ROOT, None, skill_override="career-document")
        self.assertEqual(selection["status"], "selected")
        self.assertIsNone(selection["invocation"])
        self.assertEqual(selection["execution"], "host_required")
        validation.validate_skill_selection(selection)

    def test_host_required_invoke_with_carries_an_entrypoint_placeholder(self) -> None:
        # career-document is host_required. A caller running invoke_with unedited must not get a
        # silent "unsupported" that reads as an answer -- it must fail loudly on the placeholder.
        selection = select_skill(SKILLS_ROOT, None, skill_override="career-document")
        self.assertEqual(
            selection["invoke_with"], "skill-open --skill career-document --entrypoint HOST",
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT)] + selection["invoke_with"].split(),
            text=True, encoding="utf-8", capture_output=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_entrypoint_placeholder_fails_loudly_through_a_real_shell_too(self) -> None:
        # The old `<claude|codex>` placeholder used shell metacharacters (`<`, `|`, `>`): a caller
        # pasting invoke_with into an actual shell hit redirection/piping instead of argparse's
        # rejection. `HOST` has none, so a shell run and an argv-list run must fail the same way.
        selection = select_skill(SKILLS_ROOT, None, skill_override="career-document")
        self.assertFalse(set(selection["invoke_with"]) & set("<>|&;$`\"'\\"))
        command = f"{sys.executable} {SCRIPT} {selection['invoke_with']}"
        result = subprocess.run(
            command, shell=True, text=True, encoding="utf-8", capture_output=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_hybrid_skill_invoke_with_also_carries_an_entrypoint_placeholder(self) -> None:
        # career-maintenance is hybrid, not host_required -- but skill-open's --entrypoint still
        # defaults to "cli". Without this hint, a host following invoke_with literally would record
        # entrypoint: cli for a Skill invocation the host itself actually carried out.
        selection = select_skill(SKILLS_ROOT, None, skill_override="career-maintenance")
        self.assertEqual(
            selection["invoke_with"], "skill-open --skill career-maintenance --entrypoint HOST",
        )

    def test_deterministic_skill_invoke_with_carries_no_entrypoint_hint(self) -> None:
        # career-agent runs inside this CLI process itself, so --entrypoint cli's default is
        # already true for it -- no placeholder needed.
        selection = select_skill(SKILLS_ROOT, None, skill_override="career-agent")
        self.assertEqual(selection["invoke_with"], "skill-open --skill career-agent")


class SkillInvocationCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault = Path(self.tempdir.name) / "career-vault"
        output(run(self.vault, "init"))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def set_profile(self, **values: str) -> None:
        lines = [f'{key} = {json.dumps(value, ensure_ascii=False)}' for key, value in values.items()]
        (self.vault / "00-control" / "career-profile.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_host_required_skill_opened_from_cli_is_unsupported_and_leaves_nothing_open(self) -> None:
        opened = output(run(self.vault, "skill-open", "--skill", "career-document"))
        self.assertEqual(opened["status"], "unsupported")
        self.assertEqual(opened["error"], "host_required")
        self.assertEqual(opened["available_hosts"], ["claude", "codex"])
        doctor = output(run(self.vault, "doctor"))
        self.assertEqual(doctor["ok"], True)
        self.assertFalse(any("never reported" in warning for warning in doctor["warnings"]))

    def test_host_required_skill_opened_from_claude_starts_and_appears_open(self) -> None:
        opened = output(run(
            self.vault, "skill-open", "--skill", "career-document", "--entrypoint", "claude",
        ))
        self.assertEqual(opened["status"], "started")
        status_result = output(run(self.vault, "status"))
        open_ids = {row["invocation_id"] for row in status_result["open_skill_invocations"]}
        self.assertIn(opened["invocation_id"], open_ids)
        doctor = output(run(self.vault, "doctor"))
        self.assertEqual(doctor["ok"], True)
        self.assertTrue(any("never reported" in warning for warning in doctor["warnings"]))

    def test_deterministic_skill_opens_from_cli_without_being_unsupported(self) -> None:
        opened = output(run(self.vault, "skill-open", "--skill", "career-agent"))
        self.assertEqual(opened["status"], "started")

    def test_skill_report_with_no_started_record_is_refused(self) -> None:
        failed = run(self.vault, "skill-report", "skillinv-doesnotexist", "--status", "completed")
        self.assertEqual(failed.returncode, 2)
        self.assertIn("unknown skill invocation", failed.stderr)

    def test_second_terminal_report_on_a_closed_invocation_is_refused(self) -> None:
        opened = output(run(
            self.vault, "skill-open", "--skill", "career-document", "--entrypoint", "claude",
        ))
        invocation_id = opened["invocation_id"]
        output(run(
            self.vault, "skill-report", invocation_id, "--status", "completed",
            "--summary", "generated the 職務経歴書",
        ))
        failed = run(self.vault, "skill-report", invocation_id, "--status", "failed", "--error", "retry")
        self.assertEqual(failed.returncode, 2)
        self.assertIn("already closed", failed.stderr)

    def test_completed_report_without_summary_is_refused(self) -> None:
        # completed != selected only means something if completed carries evidence it happened.
        opened = output(run(
            self.vault, "skill-open", "--skill", "career-document", "--entrypoint", "claude",
        ))
        failed = run(self.vault, "skill-report", opened["invocation_id"], "--status", "completed")
        self.assertEqual(failed.returncode, 2)
        self.assertIn("non-empty summary", failed.stderr)

    def test_failed_report_without_error_is_refused(self) -> None:
        opened = output(run(
            self.vault, "skill-open", "--skill", "career-document", "--entrypoint", "claude",
        ))
        failed = run(self.vault, "skill-report", opened["invocation_id"], "--status", "failed")
        self.assertEqual(failed.returncode, 2)
        self.assertIn("non-empty error", failed.stderr)

    def test_reported_invocation_closes_and_leaves_status_empty(self) -> None:
        opened = output(run(
            self.vault, "skill-open", "--skill", "career-document", "--entrypoint", "claude",
        ))
        output(run(
            self.vault, "skill-report", opened["invocation_id"], "--status", "completed",
            "--summary", "generated the 職務経歴書", "--artifact", "career-docs/shokumu.html",
        ))
        status_result = output(run(self.vault, "status"))
        self.assertEqual(status_result["open_skill_invocations"], [])
        rows = read_jsonl(self.vault / "02-state" / "invocations.jsonl")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["status"], "started")
        self.assertEqual(rows[1]["status"], "completed")
        self.assertEqual(rows[1]["artifacts"], ["career-docs/shokumu.html"])

    def test_skills_command_lists_every_skill_without_a_vault(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "skills"],
            text=True, encoding="utf-8", capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["skills"]), 13)

    def test_chat_trajectory_gains_selection_only_not_invocation_or_verification(self) -> None:
        # A trajectory records what select_skill() returned for the turn, never a claim that the
        # Skill ran: skill-open takes no trajectory id and report_invocation never writes back to
        # a trajectory, so an `invocation` or `verification` key here could only ever be a
        # placeholder nothing writes to. Confirms neither one leaked back in.
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        output(run(self.vault, "run", "--mode", "chat", "--message", "면접 준비해줘"))
        trajectory = read_jsonl(self.vault / "02-state" / "trajectories.jsonl")[-1]
        self.assertIn("selection", trajectory)
        self.assertNotIn("invocation", trajectory)
        self.assertNotIn("verification", trajectory)
        self.assertEqual(trajectory["selection"], trajectory["act"]["skill"])


if __name__ == "__main__":
    unittest.main()
