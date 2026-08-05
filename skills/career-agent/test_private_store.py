#!/usr/bin/env python3
"""Private career-document store tests.

Covers docs/PRIVATE_CAREER_DATA_PRD.md phase 2 exit criteria: AC-01, AC-02, AC-03, AC-11, AC-12,
AC-23, AC-25. All fixtures are synthetic (AC-06).

    synthetic://test-fixtures
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import private_store  # noqa: E402
import runtime  # noqa: E402
from models import CareerError  # noqa: E402

RESUME_BYTES = b"%PDF-1.4 synthetic resume\n"


class PrivateStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name).resolve()
        self.home = private_store.PrivateHome(self.base / "private")
        self.source = self.base / "work" / "resume.pdf"
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(RESUME_BYTES)
        self._env = os.environ.pop(private_store.PRIVATE_ENV, None)

    def tearDown(self) -> None:
        if self._env is not None:
            os.environ[private_store.PRIVATE_ENV] = self._env
        else:
            os.environ.pop(private_store.PRIVATE_ENV, None)
        self._tmp.cleanup()

    def _import(self, **overrides):
        arguments = {"effective_from": "2026-07-15"}
        arguments.update(overrides)
        return private_store.import_document(self.home, self.source, "resume", **arguments)


class RootResolutionTest(PrivateStoreTest):
    def test_explicit_root_outside_a_worktree_is_accepted(self) -> None:
        """AC-01."""
        resolved = private_store.resolve_private_home(self.base / "private")
        self.assertEqual(resolved, (self.base / "private").resolve())
        self.assertIsNone(private_store.git_worktree_root(resolved))

    def test_root_inside_a_git_worktree_is_refused(self) -> None:
        """AC-02: the hard invariant, with an actionable error."""
        worktree = self.base / "repo"
        (worktree / ".git").mkdir(parents=True)
        with self.assertRaises(CareerError) as caught:
            private_store.resolve_private_home(worktree / "private")
        message = str(caught.exception)
        self.assertIn("Git worktree", message)
        self.assertIn(private_store.PRIVATE_ENV, message)

    def test_nested_directory_inside_a_worktree_is_refused(self) -> None:
        worktree = self.base / "repo"
        (worktree / ".git").mkdir(parents=True)
        with self.assertRaises(CareerError):
            private_store.resolve_private_home(worktree / "a" / "b" / "private")

    def test_linked_worktree_git_file_counts_as_a_worktree(self) -> None:
        worktree = self.base / "linked"
        worktree.mkdir()
        (worktree / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
        with self.assertRaises(CareerError):
            private_store.resolve_private_home(worktree / "private")

    def test_environment_variable_is_used_when_no_explicit_root(self) -> None:
        os.environ[private_store.PRIVATE_ENV] = str(self.base / "from-env")
        self.assertEqual(
            private_store.resolve_private_home(), (self.base / "from-env").resolve()
        )

    def test_vault_private_is_skipped_when_the_vault_is_inside_a_worktree(self) -> None:
        vault = self.base / "repo" / "vault"
        (self.base / "repo" / ".git").mkdir(parents=True)
        vault.mkdir(parents=True)
        resolved = private_store.resolve_private_home(None, vault)
        # Falls through to the user-local default rather than silently choosing tracked storage.
        self.assertNotEqual(resolved, (vault / "private").resolve())

    def test_vault_private_is_used_when_the_vault_is_outside_a_worktree(self) -> None:
        vault = self.base / "vault"
        vault.mkdir()
        self.assertEqual(
            private_store.resolve_private_home(None, vault), (vault / "private").resolve()
        )

    def test_no_user_specific_absolute_path_is_hardcoded(self) -> None:
        source = (SCRIPT_DIR / "private_store.py").read_text(encoding="utf-8")
        self.assertNotIn("C:\\Users", source)
        self.assertNotIn("/home/", source)


class ImportTest(PrivateStoreTest):
    def test_import_preserves_bytes_and_source(self) -> None:
        """AC-03: byte-exact import that does not move the original."""
        result = self._import()
        stored = self.home.path / result["storage_path"]
        self.assertEqual(stored.read_bytes(), RESUME_BYTES)
        self.assertEqual(result["sha256"], private_store.sha256_file(self.source))
        self.assertTrue(self.source.exists(), "import must not move or delete the source")
        self.assertTrue(result["source_preserved"])

    def test_import_does_not_promote_facts(self) -> None:
        """Section 5.4: importing proves the artifact exists, nothing more."""
        result = self._import()
        self.assertEqual(result["facts_requiring_confirmation"], [])
        record = private_store.documents(self.home)[0]
        self.assertFalse(record["verified_by_user"])

    def test_repeated_identical_import_is_idempotent(self) -> None:
        """AC-11."""
        first = self._import()
        second = self._import()
        self.assertEqual(first["document_id"], second["document_id"])
        self.assertTrue(second["duplicate"])
        current = [row for row in private_store.documents(self.home) if row["status"] == "current"]
        self.assertEqual(len(current), 1)

    def test_same_bytes_under_two_logical_keys_share_one_blob(self) -> None:
        """AC-25: one stored blob, two independent records."""
        general = self._import()
        company = private_store.import_document(
            self.home, self.source, "es",
            effective_from="2026-07-15", company="Synthetic Corp", purpose="application",
        )
        self.assertNotEqual(general["document_id"], company["document_id"])
        self.assertEqual(general["sha256"], company["sha256"])
        self.assertFalse(company["duplicate"])
        blobs = sorted(path.name for path in self.home.documents.rglob("*") if path.is_file())
        self.assertEqual(len(blobs), 2, "content-addressed per type, one file per stored blob")

    def test_es_for_one_company_does_not_supersede_another(self) -> None:
        """Section 7.2: version chains are scoped by logical identity."""
        first = private_store.import_document(
            self.home, self.source, "es", company="Alpha (Synthetic)", purpose="application",
        )
        other = self.base / "work" / "other.pdf"
        other.write_bytes(b"%PDF-1.4 different synthetic\n")
        second = private_store.import_document(
            self.home, other, "es", company="Beta (Synthetic)", purpose="application",
        )
        self.assertIsNone(first["supersedes"])
        self.assertIsNone(second["supersedes"])
        statuses = {row["document_id"]: row["status"] for row in private_store.documents(self.home)}
        self.assertEqual(statuses[first["document_id"]], "current")
        self.assertEqual(statuses[second["document_id"]], "current")

    def test_newer_document_supersedes_the_previous_one_for_the_same_key(self) -> None:
        first = self._import()
        newer = self.base / "work" / "resume-2027.pdf"
        newer.write_bytes(b"%PDF-1.4 newer synthetic resume\n")
        second = private_store.import_document(
            self.home, newer, "resume", effective_from="2027-01-10",
        )
        self.assertEqual(second["supersedes"], first["document_id"])
        statuses = {row["document_id"]: row["status"] for row in private_store.documents(self.home)}
        self.assertEqual(statuses[first["document_id"]], "superseded")
        self.assertEqual(statuses[second["document_id"]], "current")

    def test_impossible_effective_date_is_rejected(self) -> None:
        """Section 19.2: a real calendar date, not just the right shape."""
        with self.assertRaises(CareerError):
            self._import(effective_from="2026-99-99")

    def test_missing_source_preserves_state(self) -> None:
        """AC-12: a failed import records nothing."""
        with self.assertRaises(CareerError):
            private_store.import_document(self.home, self.base / "absent.pdf", "resume")
        self.assertEqual(private_store.documents(self.home), [])

    def test_unknown_document_type_is_rejected(self) -> None:
        with self.assertRaises(CareerError):
            private_store.import_document(self.home, self.source, "not-a-type")

    def test_missing_effective_date_does_not_block_import(self) -> None:
        """Section 19.3: keep the document, leave applicability Unknown."""
        result = private_store.import_document(self.home, self.source, "resume")
        self.assertIsNone(private_store.documents(self.home)[0]["effective_from"])
        self.assertEqual(result["status"], "current")


class DoctorTest(PrivateStoreTest):
    def test_doctor_runs_without_a_vault(self) -> None:
        """AC-23."""
        report = private_store.private_doctor(self.home.path)
        self.assertTrue(report["ok"])
        self.assertTrue(report["checks"]["git_boundary"]["ok"])

    def test_doctor_reports_an_unsafe_root_without_raising(self) -> None:
        worktree = self.base / "repo"
        (worktree / ".git").mkdir(parents=True)
        report = private_store.private_doctor(worktree / "private")
        self.assertFalse(report["ok"])
        self.assertFalse(report["checks"]["private_root"]["ok"])

    def test_doctor_counts_current_and_superseded(self) -> None:
        self._import()
        newer = self.base / "work" / "resume-2027.pdf"
        newer.write_bytes(b"%PDF-1.4 newer synthetic resume\n")
        private_store.import_document(self.home, newer, "resume", effective_from="2027-01-10")
        report = private_store.private_doctor(self.home.path)
        self.assertEqual(report["documents"]["current"], 1)
        self.assertEqual(report["documents"]["historical"], 1)

    def test_doctor_flags_a_missing_blob(self) -> None:
        result = self._import()
        (self.home.path / result["storage_path"]).unlink()
        report = private_store.private_doctor(self.home.path)
        self.assertFalse(report["ok"])
        self.assertEqual(report["documents"]["missing_blobs"], 1)

    def test_permission_state_is_honest_about_the_platform(self) -> None:
        private_store.initialize_private_home(self.home)
        state = private_store.permission_state(self.home)
        if os.name == "nt":
            self.assertFalse(state["enforced"])
            self.assertIn("not enforced", state["detail"])
        else:
            self.assertTrue(state["enforced"])


class CliTest(PrivateStoreTest):
    def _run(self, *arguments: str) -> subprocess.CompletedProcess:
        environment = dict(os.environ, CAREER_PRIVATE_HOME=str(self.home.path))
        environment.pop("CAREER_VAULT", None)
        return subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "career_agent.py"), *arguments],
            capture_output=True, text=True, check=False, env=environment,
        )

    def test_private_doctor_cli_needs_no_vault(self) -> None:
        """AC-23 through the actual CLI entry point."""
        result = self._run("private-doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("git_boundary", result.stdout)

    def test_private_import_and_list_cli(self) -> None:
        imported = self._run("private-import", str(self.source), "--type", "resume",
                             "--effective-from", "2026-07-15")
        self.assertEqual(imported.returncode, 0, imported.stderr)
        listed = self._run("private-list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("doc_", listed.stdout)
        self.assertTrue(self.source.exists())

    def test_private_list_returns_metadata_without_bodies(self) -> None:
        self._run("private-import", str(self.source), "--type", "resume")
        listed = self._run("private-list")
        self.assertNotIn("%PDF", listed.stdout, "document bodies must never be printed")

    def test_unsafe_root_fails_with_exit_code_two(self) -> None:
        worktree = self.base / "repo"
        (worktree / ".git").mkdir(parents=True)
        environment = dict(os.environ, CAREER_PRIVATE_HOME=str(worktree / "private"))
        environment.pop("CAREER_VAULT", None)
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "career_agent.py"), "private-import",
             str(self.source), "--type", "resume"],
            capture_output=True, text=True, check=False, env=environment,
        )
        self.assertEqual(result.returncode, 2)


class BoundaryTest(unittest.TestCase):
    def test_runtime_exposes_the_private_commands(self) -> None:
        parser = runtime.build_parser()
        actions = [
            action for action in parser._subparsers._group_actions[0].choices  # noqa: SLF001
        ]
        for command in ("private-doctor", "private-import", "private-list"):
            self.assertIn(command, actions)


if __name__ == "__main__":
    unittest.main()
