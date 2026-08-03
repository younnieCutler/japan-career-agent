"""Failure-injection and workspace-resolution checks for pipeline_store.py (PERSIST-001/WORK-001)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pipeline_store  # noqa: E402


class AtomicWriteDurabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def assert_no_temp_files(self, directory: Path) -> None:
        self.assertEqual(list(directory.glob("*.tmp-*")), [])

    def test_fsync_failure_preserves_previous_valid_file_and_cleans_up_temp(self) -> None:
        path = self.root / "pipeline.yml"
        path.write_text("companies: []\n", encoding="utf-8")

        with patch.object(pipeline_store.os, "fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                pipeline_store.atomic_write(path, {"companies": [{"slug": "x"}]})

        self.assertEqual(path.read_text(encoding="utf-8"), "companies: []\n")
        self.assert_no_temp_files(self.root)

    def test_replace_failure_preserves_previous_valid_file_and_cleans_up_temp(self) -> None:
        path = self.root / "pipeline.yml"
        path.write_text("companies: []\n", encoding="utf-8")

        with patch.object(pipeline_store.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                pipeline_store.atomic_write(path, {"companies": [{"slug": "x"}]})

        self.assertEqual(path.read_text(encoding="utf-8"), "companies: []\n")
        self.assert_no_temp_files(self.root)

    def test_retry_after_failure_leaves_valid_state(self) -> None:
        path = self.root / "pipeline.yml"

        with patch.object(pipeline_store.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                pipeline_store.upsert_company(path, "gao", {"name": "GAO", "stage": 1})

        self.assertFalse(path.exists())
        self.assert_no_temp_files(self.root)

        pipeline_store.upsert_company(path, "gao", {"name": "GAO", "stage": 1})
        data = pipeline_store.load(path)
        self.assertEqual(data["companies"][0]["slug"], "gao")
        self.assert_no_temp_files(self.root)


class WorkspaceResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self._old_env = os.environ.get("CAREER_WORKSPACE")

    def tearDown(self) -> None:
        self.tempdir.cleanup()
        if self._old_env is None:
            os.environ.pop("CAREER_WORKSPACE", None)
        else:
            os.environ["CAREER_WORKSPACE"] = self._old_env

    def test_explicit_argument_wins_over_env_and_cwd(self) -> None:
        explicit = self.root / "explicit"
        explicit.mkdir()
        os.environ["CAREER_WORKSPACE"] = str(self.root / "from-env")
        resolved = pipeline_store.resolve_workspace(str(explicit))
        self.assertEqual(resolved, explicit.resolve())

    def test_env_var_wins_over_cwd_when_no_explicit_argument(self) -> None:
        from_env = self.root / "from-env"
        os.environ["CAREER_WORKSPACE"] = str(from_env)
        resolved = pipeline_store.resolve_workspace(None)
        self.assertEqual(resolved, from_env.resolve())

    def test_cwd_is_the_final_fallback(self) -> None:
        os.environ.pop("CAREER_WORKSPACE", None)
        cwd = Path.cwd().resolve()
        self.assertEqual(pipeline_store.resolve_workspace(None), cwd)

    def test_resolve_pipeline_path_appends_data_pipeline_yml(self) -> None:
        explicit = self.root / "ws"
        self.assertEqual(
            pipeline_store.resolve_pipeline_path(str(explicit)),
            explicit.resolve() / "data" / "pipeline.yml",
        )


if __name__ == "__main__":
    unittest.main()
