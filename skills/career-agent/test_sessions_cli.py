"""Contract tests for the CLI view of resumable GUI sessions."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

import command_line  # noqa: E402
import case_store  # noqa: E402
import persistence  # noqa: E402
import sessions  # noqa: E402
from gui import cases as gui_cases, tanaoroshi  # noqa: E402
from vault import CareerVault, initialize_vault  # noqa: E402


class SessionCliTests(unittest.TestCase):
    @staticmethod
    def invoke(argv: list[str]) -> tuple[int, dict]:
        output = io.StringIO()
        error = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = command_line.main(argv)
        return code, json.loads(output.getvalue() or error.getvalue())

    def test_gui_start_failure_has_a_localized_human_recovery(self) -> None:
        expected = {
            "ko": "로컬 화면을 열지 못했습니다",
            "ja": "ローカル画面を開けませんでした",
            "en": "The local interface could not open",
        }
        for language, message in expected.items():
            with self.subTest(language=language):
                output = io.StringIO()
                error = io.StringIO()
                with patch("gui.server.create_server", side_effect=PermissionError("bind denied")):
                    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                        code = command_line.main([
                            "ui", "--no-browser", "--language", language, "--format", "human",
                        ])

                self.assertEqual(code, 2)
                self.assertEqual(output.getvalue(), "")
                self.assertIn(message, error.getvalue())
                self.assertNotIn("GUI_START_FAILED", error.getvalue())
                self.assertNotIn("PermissionError", error.getvalue())

    def test_sessions_json_reads_the_same_application_store_as_the_gui(self) -> None:
        boundary = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                (
                    f"import sys; sys.path.insert(0, {str(ROOT / 'skills' / 'career-agent')!r}); "
                    "import command_line; print('gui.server' in sys.modules)"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(boundary.stdout.strip(), "False")
        with tempfile.TemporaryDirectory() as directory:
            vault_path = Path(directory) / "vault"
            initialize_vault(vault_path)
            home = CareerVault(vault_path)
            created = sessions.create_session(home)
            sessions.checkpoint_session(home, created["session_id"], stage="review")
            before = {
                path.relative_to(vault_path).as_posix(): path.read_bytes()
                for path in vault_path.rglob("*")
                if path.is_file()
            }

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = command_line.main(
                    ["sessions", "--vault", str(vault_path), "--format", "json"]
                )

            after = {
                path.relative_to(vault_path).as_posix(): path.read_bytes()
                for path in vault_path.rglob("*")
                if path.is_file()
            }

        self.assertEqual(exit_code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["mode"], "sessions")
        self.assertTrue(result["read_only"])
        self.assertEqual(result["sessions"][0]["session_id"], created["session_id"])
        self.assertEqual(result["sessions"][0]["stage"], "review")
        self.assertEqual(before, after)

    def test_claude_codex_and_cli_handoff_without_a_session_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault_path = Path(directory) / "vault"
            initialize_vault(vault_path)
            common = ["--vault", str(vault_path), "--format", "json"]

            started_code, started = self.invoke([
                "workflow", "start", "--workflow", "career_inventory",
                "--entrypoint", "claude", *common,
            ])
            resumed_code, resumed = self.invoke([
                "workflow", "resume", "--workflow", "career_inventory",
                "--entrypoint", "codex", *common,
            ])
            saved_code, saved = self.invoke([
                "workflow", "save", "--workflow", "career_inventory",
                "--entrypoint", "codex", "--revision", str(resumed["revision"]),
                "--json", json.dumps({"summary": "Cross-host draft", "non_work": False}),
                *common,
            ])
            home = CareerVault(vault_path)
            gui_list = tanaoroshi.active(home)
            gui_ref = gui_list["sessions"][0]["session_ref"]
            gui_resumed = tanaoroshi.resume(home, gui_ref)
            gui_saved = tanaoroshi.autosave(
                home,
                gui_ref,
                {"summary": "GUI continued draft", "non_work": False},
                expected_revision=gui_resumed["revision"],
            )
            cli_code, cli_resumed = self.invoke([
                "workflow", "resume", "--workflow", "career_inventory",
                "--entrypoint", "cli", *common,
            ])
            stale_code, stale = self.invoke([
                "workflow", "save", "--workflow", "career_inventory",
                "--entrypoint", "codex", "--revision", str(saved["revision"]),
                "--json", json.dumps({"summary": "Stale browser", "non_work": False}),
                *common,
            ])

        self.assertEqual((started_code, resumed_code, saved_code, cli_code), (0, 0, 0, 0))
        self.assertEqual(started["session"]["started_by"], "claude")
        self.assertEqual(resumed["session"]["session_id"], started["session"]["session_id"])
        self.assertEqual(saved["session"]["last_entrypoint"], "codex")
        self.assertEqual(gui_resumed["draft"]["summary"], "Cross-host draft")
        self.assertEqual(gui_saved["session"]["last_entrypoint"], "gui")
        self.assertEqual(cli_resumed["draft"]["summary"], "GUI continued draft")
        self.assertNotEqual(stale_code, 0)
        self.assertEqual(stale["error_code"], "REVISION_STALE")

    def test_cross_entrypoint_review_commits_exactly_the_gui_snapshot_without_an_id_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault_path = Path(directory) / "vault"
            initialize_vault(vault_path)
            home = CareerVault(vault_path)
            context = case_store.create_career_context(
                home, "Acme", context_kind="company", relationship="employer"
            )
            context_review = gui_cases.propose_canonical_case(home, context["case_id"])
            context = gui_cases.approve_canonical_case(
                home, context["case_id"], context_review["proposal"]["id"]
            )["case"]
            project = case_store.create_project(home, context["case_id"], "Payments")
            project_review = gui_cases.propose_canonical_case(home, project["case_id"])
            project = gui_cases.approve_canonical_case(
                home, project["case_id"], project_review["proposal"]["id"]
            )["case"]
            common = ["--vault", str(vault_path), "--format", "json"]

            _, started = self.invoke([
                "workflow", "start", "--workflow", "career_inventory",
                "--entrypoint", "claude", "--case-ref", project["case_id"], *common,
            ])
            _, partial = self.invoke([
                "workflow", "save", "--workflow", "career_inventory",
                "--entrypoint", "claude", "--revision", str(started["revision"]),
                "--json", json.dumps({"summary": "Improved payment handoff", "non_work": False}),
                *common,
            ])
            _, discovered = self.invoke([
                "workflow", "resume", "--workflow", "career_inventory",
                "--entrypoint", "codex", *common,
            ])
            draft = {
                "summary": "Improved payment handoff",
                "role": "owner",
                "direct_actions": ["rewrote the cutover runbook"],
                "individual_contribution": "designed and tested the new handoff",
                "outcome_state": "qualitative",
                "team_result": "fewer repeated questions",
                "evidence": ["reviewed runbook"],
                "confidentiality": {"contains_confidential": False, "external_use": "allowed"},
            }
            _, saved = self.invoke([
                "workflow", "save", "--workflow", "career_inventory",
                "--entrypoint", "codex", "--revision", str(discovered["revision"]),
                "--json", json.dumps(draft), *common,
            ])
            _, proposed = self.invoke([
                "workflow", "propose", "--workflow", "career_inventory",
                "--entrypoint", "cli", "--revision", str(saved["revision"]), *common,
            ])
            proposal_session = sessions.load_session(home, started["session"]["session_id"])
            canonical_before = persistence.read_jsonl(home.events)

            visible = tanaoroshi.active(home)
            self.assertEqual(len(visible["sessions"]), 1)
            gui_ref = visible["sessions"][0]["session_ref"]
            gui_review = tanaoroshi.submit(
                home, gui_ref, expected_revision=proposed["revision"]
            )
            reviewed_event = gui_review["proposal"]["event"]
            self.assertEqual(reviewed_event, proposed["proposal"]["event"])
            self.assertEqual(persistence.read_jsonl(home.events), canonical_before)

            approved = tanaoroshi.approve_session(
                home,
                gui_ref,
                gui_review["proposal"]["id"],
                expected_revision=gui_review["revision"],
            )
            canonical_after = persistence.read_jsonl(home.events)
            completed_session = sessions.load_session(home, gui_ref)

        self.assertEqual(started["session"]["started_by"], "claude")
        self.assertEqual(partial["session"]["last_entrypoint"], "claude")
        self.assertEqual(discovered["draft"]["summary"], "Improved payment handoff")
        self.assertEqual(saved["session"]["last_entrypoint"], "codex")
        self.assertEqual(proposal_session["last_entrypoint"], "cli")
        self.assertEqual(approved["event"], {**reviewed_event, "status": "confirmed"})
        self.assertEqual(canonical_after[-1], approved["event"])
        self.assertEqual(completed_session["last_entrypoint"], "gui")

    def test_multiple_cli_workflows_are_selected_by_visible_context_without_an_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault_path = Path(directory) / "vault"
            initialize_vault(vault_path)
            common = ["--vault", str(vault_path), "--format", "json"]
            _, first = self.invoke([
                "workflow", "start", "--workflow", "career_inventory",
                "--entrypoint", "claude", "--subject-json",
                json.dumps({"context_label": "Acme", "project_label": "Payments"}), *common,
            ])
            _, second = self.invoke([
                "workflow", "start", "--workflow", "career_inventory",
                "--entrypoint", "codex", "--subject-json",
                json.dumps({"context_label": "Beta", "project_label": "Search"}), *common,
            ])
            ambiguous_code, ambiguous = self.invoke([
                "workflow", "resume", "--workflow", "career_inventory", *common,
            ])
            selected_code, selected = self.invoke([
                "workflow", "resume", "--workflow", "career_inventory",
                "--context", "Beta / Search", *common,
            ])
            saved_code, saved = self.invoke([
                "workflow", "save", "--workflow", "career_inventory",
                "--context", "Beta / Search", "--entrypoint", "cli",
                "--revision", str(selected["revision"]),
                "--json", json.dumps({"summary": "Selected by visible context", "non_work": False}),
                *common,
            ])
            human = io.StringIO()
            with contextlib.redirect_stdout(human):
                human_code = command_line.main([
                    "sessions", "--vault", str(vault_path), "--format", "human",
                ])
            ambiguous_human = io.StringIO()
            ignored_stdout = io.StringIO()
            with contextlib.redirect_stdout(ignored_stdout), contextlib.redirect_stderr(ambiguous_human):
                ambiguous_human_code = command_line.main([
                    "workflow", "resume", "--workflow", "career_inventory",
                    "--vault", str(vault_path), "--format", "human",
                ])

        self.assertNotEqual(ambiguous_code, 0)
        self.assertEqual(ambiguous["error_code"], "SESSION_AMBIGUOUS")
        self.assertEqual((selected_code, saved_code), (0, 0))
        self.assertNotEqual(first["session"]["session_id"], second["session"]["session_id"])
        self.assertEqual(selected["session"]["session_id"], second["session"]["session_id"])
        self.assertEqual(saved["draft"]["summary"], "Selected by visible context")
        self.assertEqual(human_code, 0)
        self.assertEqual(ambiguous_human_code, 2)
        for output in (human.getvalue(), ambiguous_human.getvalue()):
            self.assertIn("Acme / Payments", output)
            self.assertIn("Beta / Search", output)
            self.assertIn("--context", output)
            self.assertNotIn(first["session"]["session_id"], output)
            self.assertNotIn(second["session"]["session_id"], output)


if __name__ == "__main__":
    unittest.main()
