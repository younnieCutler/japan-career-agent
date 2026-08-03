"""Failure-injection checks for Career Vault snapshot writers."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

import career_agent  # noqa: E402


class StateDurabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def assert_no_temp_files(self, directory: Path) -> None:
        self.assertEqual(list(directory.glob(".*.tmp")), [])

    def test_json_temp_write_failure_preserves_previous_valid_file(self) -> None:
        path = self.root / "state.json"
        path.write_text('{"old": true}\n', encoding="utf-8")

        with patch.object(career_agent.os, "fsync", side_effect=OSError("temp write failed")):
            with self.assertRaises(OSError):
                career_agent.write_json(path, {"new": True})

        self.assertEqual(path.read_text(encoding="utf-8"), '{"old": true}\n')
        self.assert_no_temp_files(self.root)

    def test_json_replace_failure_preserves_previous_valid_file(self) -> None:
        path = self.root / "state.json"
        path.write_text('{"old": true}\n', encoding="utf-8")

        with patch.object(career_agent.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                career_agent.write_json(path, {"new": True})

        self.assertEqual(path.read_text(encoding="utf-8"), '{"old": true}\n')
        self.assert_no_temp_files(self.root)

    def test_toml_failures_preserve_previous_valid_file(self) -> None:
        path = self.root / "state.toml"
        path.write_text('stage = "old"\n', encoding="utf-8")

        with patch.object(career_agent.os, "fsync", side_effect=OSError("temp write failed")):
            with self.assertRaises(OSError):
                career_agent.write_toml(path, {"stage": "new"})
        self.assertEqual(path.read_text(encoding="utf-8"), 'stage = "old"\n')

        with patch.object(career_agent.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                career_agent.write_toml(path, {"stage": "new"})
        self.assertEqual(path.read_text(encoding="utf-8"), 'stage = "old"\n')
        self.assert_no_temp_files(self.root)

    def test_jsonl_rewrite_uses_the_same_atomic_writer(self) -> None:
        path = self.root / "proposals.jsonl"
        path.write_text('{"old":true}\n', encoding="utf-8")

        with patch.object(career_agent.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                career_agent.write_jsonl(path, [{"new": True}])

        self.assertEqual(path.read_text(encoding="utf-8"), '{"old":true}\n')
        self.assert_no_temp_files(self.root)

    def test_state_retry_leaves_valid_source_of_truth_and_refreshes_cache(self) -> None:
        home = career_agent.CareerVault(self.root / "vault")
        home.ensure_runtime()
        home.write_state({"track": "chuto", "stage": "old"})
        old_json = home.state.read_text(encoding="utf-8")

        original_replace = career_agent.os.replace
        calls = 0

        def fail_json_replace(source: str | bytes | Path, target: str | bytes | Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("cache replace failed")
            original_replace(source, target)

        with patch.object(career_agent.os, "replace", side_effect=fail_json_replace):
            with self.assertRaises(OSError):
                home.write_state({"track": "chuto", "stage": "new"})

        self.assertEqual(home.load_state()["stage"], "new")
        self.assertEqual(home.state.read_text(encoding="utf-8"), old_json)
        self.assert_no_temp_files(home.state.parent)

        home.write_state({"track": "chuto", "stage": "new"})
        self.assertEqual(home.load_state()["stage"], "new")
        self.assert_no_temp_files(home.state.parent)


if __name__ == "__main__":
    unittest.main()
