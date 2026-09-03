"""Deterministic tests for the P1 guided thin frontend."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "career-agent" / "career_agent.py"
sys.path.insert(0, str(SCRIPT.parent))
import command_line  # noqa: E402
from guided import build_summary, derive_actions, render_human, resolve_choice  # noqa: E402
from guided_flow import run_guided  # noqa: E402
from vault import CareerVault  # noqa: E402


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

    def test_interactive_start_task_collects_message_and_confirmation_in_one_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            work = root / "workspace"
            work.mkdir()
            self.assertEqual(run(vault, "setup", "--track", "chuto", cwd=work).returncode, 0)
            with (
                unittest.mock.patch("builtins.input", side_effect=["start_task", "prepare interview", "yes"]),
                unittest.mock.patch.object(sys, "stdout", new=io.StringIO()),
            ):
                result = run_guided(
                    CareerVault(vault), workspace=work, as_of="2026-09-03", interactive=True,
                )
            self.assertEqual(result["selection"]["status"], "completed")
            self.assertEqual(result["selection"]["action"], "start_task")
            self.assertEqual(result["action_result"]["proposal"]["status"], "pending")
            self.assertEqual(result["guided"]["summary"]["pending_proposals"], 1)

    def test_interactive_blank_task_cancels_without_creating_a_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            work = root / "workspace"
            work.mkdir()
            self.assertEqual(run(vault, "setup", "--track", "chuto", cwd=work).returncode, 0)
            with (
                unittest.mock.patch("builtins.input", side_effect=["start_task", ""]),
                unittest.mock.patch.object(sys, "stdout", new=io.StringIO()),
            ):
                result = run_guided(
                    CareerVault(vault), workspace=work, as_of="2026-09-03", interactive=True,
                )
            self.assertEqual(result["selection"]["status"], "cancelled")
            self.assertEqual(json.loads(run(vault, "status", cwd=work).stdout)["pending_proposals"], 0)

    def test_empty_vault_leads_with_existing_history_capture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            work = root / "workspace"
            work.mkdir()
            self.assertEqual(run(vault, "setup", "--track", "chuto", cwd=work).returncode, 0)

            menu = json.loads(run(vault, "guided", cwd=work).stdout)
            self.assertTrue(menu["guided"]["summary"]["bootstrap_suggested"])
            self.assertEqual(menu["guided"]["available_actions"][0]["id"], "capture_history")
            self.assertIn(
                "start_task",
                [action["id"] for action in menu["guided"]["available_actions"]],
            )

    def test_existing_history_capture_stays_unplaced_and_non_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            work = root / "workspace"
            work.mkdir()
            self.assertEqual(run(vault, "setup", "--track", "chuto", cwd=work).returncode, 0)
            events_path = vault / "02-state" / "events.jsonl"
            before = events_path.read_bytes() if events_path.exists() else b""

            captured = run(
                vault,
                "guided",
                "--choice",
                "capture_history",
                "--message",
                "Legacy resume text\nBuilt internal tooling and supported releases.",
                "--confirm",
                cwd=work,
            )
            self.assertEqual(captured.returncode, 0, captured.stderr)
            result = json.loads(captured.stdout)
            self.assertEqual(result["selection"]["status"], "completed")
            self.assertEqual(result["selection"]["action"], "capture_history")
            self.assertEqual(result["action_result"]["session"]["workflow"], "career_inventory")
            self.assertIsNone(result["action_result"]["session"]["case_ref"])
            self.assertEqual(
                result["action_result"]["draft"]["evidence"],
                ["Legacy resume text\nBuilt internal tooling and supported releases."],
            )
            self.assertTrue(result["action_result"]["project_required_before_review"])
            self.assertFalse(result["state_changed"])
            self.assertTrue(result["guided"]["summary"]["bootstrap_suggested"])
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

    def test_all_write_actions_require_confirmation_before_dispatch(self) -> None:
        scenarios = (
            ("complete_setup", "SETUP_REQUIRED"),
            ("start_task", "GUIDED_CONFIRMATION_REQUIRED"),
            ("approve_proposal", "PENDING_PROPOSAL"),
            ("restore_state", "STATE_RECOVERY_REQUIRED"),
        )
        for action, reason_code in scenarios:
            with self.subTest(action=action):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    vault = root / "vault"
                    work = root / "workspace"
                    work.mkdir()
                    extra: tuple[str, ...] = ()
                    if action != "complete_setup":
                        setup = run(vault, "setup", "--track", "chuto", cwd=work)
                        self.assertEqual(setup.returncode, 0, setup.stderr)
                    if action in {"approve_proposal", "restore_state"}:
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
                        if action == "approve_proposal":
                            extra = ("--proposal-id", proposal_id)
                        else:
                            approved = run(
                                vault,
                                "approve",
                                proposal_id,
                                "--evidence",
                                "prepare interview",
                                cwd=work,
                            )
                            self.assertEqual(approved.returncode, 0, approved.stderr)

                    result = run(vault, "guided", "--choice", action, *extra, cwd=work)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    guided = json.loads(result.stdout)
                    self.assertEqual(guided["selection"]["status"], "confirmation_required")
                    self.assertFalse(guided["state_changed"])
                    self.assertFalse(guided.get("write_performed", False))
                    self.assertEqual(guided["ux"]["reason"]["code"], reason_code)


class OnboardingDisplayTests(unittest.TestCase):
    def summary(self, **profile: object) -> dict:
        return build_summary(
            initialized=True,
            vault="/tmp/vault",
            profile={"track": "chuto", **profile},
            state={},
            workspace={"path": "/tmp/work", "exists": True},
        )

    def test_onboarding_is_reported_separately_from_setup(self) -> None:
        onboarding = self.summary(career_status="onboarding")
        self.assertTrue(onboarding["onboarding"])
        # Onboarding is normal use, not a broken install: setup stays complete and unblocked.
        self.assertTrue(onboarding["setup_complete"])
        self.assertNotIn("setup", onboarding["major_blockers"])
        self.assertFalse(self.summary(career_status="active")["onboarding"])

    def test_human_output_shows_onboarding_and_an_unknown_target_role(self) -> None:
        result = {
            "guided": {
                "state": "ready",
                "summary": self.summary(career_status="onboarding"),
                "available_actions": [],
            },
            "ux": {"language": "en"},
        }
        human = render_human(result)
        self.assertIn("Onboarding: in progress", human)
        self.assertIn("Target role: not confirmed yet (Unknown)", human)

        confirmed = dict(result)
        confirmed["guided"] = dict(result["guided"])
        confirmed["guided"]["summary"] = self.summary(career_status="active", target_role="Data Engineer")
        done = render_human(confirmed)
        self.assertIn("Onboarding: complete", done)
        self.assertIn("Target role: Data Engineer", done)


class OutputFormatDefaultTests(unittest.TestCase):
    """A person at a terminal gets the human projection; every machine caller still gets JSON."""

    def _default(self, *, stdin: bool, stdout: bool) -> str:
        with (
            unittest.mock.patch.object(sys.stdin, "isatty", return_value=stdin),
            unittest.mock.patch.object(sys.stdout, "isatty", return_value=stdout),
        ):
            return command_line._default_output_format()

    def test_only_a_terminal_on_both_streams_defaults_to_human(self) -> None:
        self.assertEqual(self._default(stdin=True, stdout=True), "human")
        # A pipe, a redirect, or a subprocess leaves at least one of these false, and every machine
        # caller is one of those: a plugin host runs this with pipes, `$(...)` captures stdout, and
        # this test suite itself reads stdout through subprocess.
        self.assertEqual(self._default(stdin=True, stdout=False), "json")
        self.assertEqual(self._default(stdin=False, stdout=True), "json")
        self.assertEqual(self._default(stdin=False, stdout=False), "json")

    def test_a_subprocess_still_receives_json_without_asking_for_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            vault = root / "vault"
            run(vault, "setup", "--track", "chuto", "--target-role", "Data Engineer", cwd=workspace)
            # No --format: this is exactly how a plugin host invokes the runtime.
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "guided", "--vault", str(vault)],
                cwd=workspace, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(json.loads(result.stdout).get("mode"), "guided")

    def test_an_explicit_format_still_wins_over_the_terminal(self) -> None:
        with unittest.mock.patch.object(sys.stdin, "isatty", return_value=True), \
             unittest.mock.patch.object(sys.stdout, "isatty", return_value=True):
            parser = command_line.build_parser()
            arguments = parser.parse_args(["guided", "--vault", "x", "--format", "json"])
            self.assertEqual(arguments.output_format, "json")


if __name__ == "__main__":
    unittest.main()
