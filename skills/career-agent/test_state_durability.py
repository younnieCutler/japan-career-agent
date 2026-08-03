"""Failure-injection checks for Career Vault snapshot writers."""

from __future__ import annotations

import sys
import tempfile
import threading
import time
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


class VaultLockCoverageTests(unittest.TestCase):
    """PERSIST-005: writers that share a Vault must serialize against `vault_lock`.

    Proves the lock is real (not just present) by holding it in the main thread and
    checking a background call to the writer waits for release before completing.
    """

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.home = career_agent.CareerVault(self.root / "vault")
        self.home.ensure_runtime()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _assert_blocks_then_completes(self, target) -> None:
        completed = threading.Event()

        def worker() -> None:
            target()
            completed.set()

        with career_agent.vault_lock(self.home):
            thread = threading.Thread(target=worker)
            thread.start()
            time.sleep(0.2)
            self.assertFalse(completed.is_set(), "writer ran without waiting for the vault lock")
        thread.join(timeout=2)
        self.assertTrue(completed.is_set(), "writer never completed after the lock was released")

    def test_run_index_waits_for_vault_lock(self) -> None:
        self._assert_blocks_then_completes(lambda: career_agent.run_index(self.home))

    def test_restore_state_waits_for_vault_lock(self) -> None:
        self.home.write_state({"track": "chuto", "stage": "s0"})
        version = self.home.save_state({"track": "chuto", "stage": "s0"})
        self._assert_blocks_then_completes(lambda: career_agent.restore_state(self.home, version))


if __name__ == "__main__":
    unittest.main()
