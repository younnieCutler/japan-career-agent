"""Contract tests for the CLI view of resumable GUI sessions."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

import command_line  # noqa: E402
import sessions  # noqa: E402
from vault import CareerVault, initialize_vault  # noqa: E402


class SessionCliTests(unittest.TestCase):
    def test_sessions_json_reads_the_same_application_store_as_the_gui(self) -> None:
        self.assertNotIn("gui.server", sys.modules)
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


if __name__ == "__main__":
    unittest.main()
