#!/usr/bin/env python3
"""Regression tests for the personal-career-document commit gate.

Covers docs/PRIVATE_CAREER_DATA_PRD.md §23.4 (Git safety) plus AC-05, AC-19, and AC-20.

All fixtures here are synthetic (AC-06); no real personal data appears in this file. That is
declared deliberately rather than left to chance -- this file necessarily contains resume-shaped
fixture text, so it must carry a synthetic marker to stay allowlisted by its own detector:

    synthetic://test-fixtures
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_private_data  # noqa: E402

REPO_ROOT = SCRIPT_DIR.parent


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=str(root), capture_output=True, text=True, check=True
    )
    return result.stdout


class TemporaryRepo:
    """A throwaway Git repository so staging tests never touch the real index."""

    def __enter__(self) -> Path:
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name).resolve()
        _git(self.root, "init", "--quiet")
        _git(self.root, "config", "user.email", "synthetic@example.invalid")
        _git(self.root, "config", "user.name", "Synthetic Fixture")
        self._previous_root = check_private_data.ROOT
        check_private_data.ROOT = self.root
        return self.root

    def __exit__(self, *exception: object) -> None:
        check_private_data.ROOT = self._previous_root
        self._directory.cleanup()


class captured_stderr:
    """Keep the gate's own BLOCKED report out of a passing test run's output."""

    def __enter__(self) -> "captured_stderr":
        self.text: list[str] = []
        self._previous = sys.stderr
        sys.stderr = type("Sink", (), {"write": lambda _s, item: self.text.append(item), "flush": lambda _s: None})()
        return self

    def __exit__(self, *exception: object) -> None:
        sys.stderr = self._previous

    def value(self) -> str:
        return "".join(self.text)


def write(root: Path, relative: str, content: str | bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


SYNTHETIC_RESUME = """# 職務経歴
氏名: 山田 花子
電話番号: 090-0000-0000
在籍期間: 2020年4月
"""


class RepositoryCleanTest(unittest.TestCase):
    """AC-19: the gate must be clean against the repository's own HEAD."""

    def test_repository_head_has_no_findings(self) -> None:
        findings = check_private_data.scan(staged=False)
        self.assertEqual(
            [item.path for item in findings], [],
            "the gate fires on its own repository; a gate that does that gets bypassed",
        )

    def test_prose_about_resumes_is_not_flagged(self) -> None:
        # The PRD itself contains "resume", "payslip", "JLPT N1" and a compensation figure.
        self.assertIsNone(check_private_data.classify("docs/PRIVATE_CAREER_DATA_PRD.md"))

    def test_schema_keys_are_not_flagged(self) -> None:
        self.assertIsNone(check_private_data.classify("_shared/schemas.yml"))

    def test_tracked_mock_profiles_are_treated_as_synthetic(self) -> None:
        self.assertIsNone(
            check_private_data.classify("skills/job-seeker-agent/mock/chuto-park-minjun.md")
        )


class IgnoreRuleTest(unittest.TestCase):
    """AC-20: the .gitignore layer covers the ordinary accident."""

    def _ignored(self, relative: str) -> bool:
        result = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
        )
        return result.returncode == 0

    def test_personal_document_paths_are_ignored(self) -> None:
        for relative in (
            "docs/resume.pdf", "skills/my-resume.docx", "scripts/履歴書.md",
            "_shared/職務経歴書.txt", "hooks/payslip.csv", "docs/cv.md",
            "skills/private/notes.md", "examples/payslip.pdf",
        ):
            with self.subTest(path=relative):
                self.assertTrue(self._ignored(relative))

    def test_source_and_synthetic_fixtures_stay_trackable(self) -> None:
        for relative in (
            "examples/demo-workspace/candidate-profile.example.yml",
            "examples/resume.example.pdf",
            "scripts/recv.py",
            "skills/career-agent/runtime.py",
            "docs/PRIVATE_CAREER_DATA_PRD.md",
        ):
            with self.subTest(path=relative):
                self.assertFalse(self._ignored(relative))


class CommitHookTest(unittest.TestCase):
    """The tracked hook must select a *working* interpreter (PRD section 15.3)."""

    def setUp(self) -> None:
        self.hook = REPO_ROOT / ".githooks" / "pre-commit"

    def test_hook_is_tracked_and_not_ignored(self) -> None:
        self.assertTrue(self.hook.is_file())
        result = subprocess.run(
            ["git", "check-ignore", "-q", ".githooks/pre-commit"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1, ".githooks/pre-commit must be trackable")

    def test_interpreter_is_probed_by_execution_not_by_name(self) -> None:
        # Regression: `command -v python3` resolves the Microsoft Store stub on Windows, which
        # exits non-zero. Because this gate fails closed, a name-only check blocked every commit.
        text = self.hook.read_text(encoding="utf-8")
        self.assertIn('-c ""', text)
        self.assertIn("fails closed", text)

    def test_hook_fails_closed_without_an_interpreter(self) -> None:
        self.assertIn("were NOT checked", self.hook.read_text(encoding="utf-8"))


class StagedGateTest(unittest.TestCase):
    def test_forced_add_is_blocked(self) -> None:
        """AC-05: protection must not depend on .gitignore alone."""
        with TemporaryRepo() as root:
            write(root, ".gitignore", "*.pdf\n")
            write(root, "resume.pdf", "%PDF-1.4 synthetic\n")
            _git(root, "add", "-f", "resume.pdf")
            with captured_stderr() as report:
                self.assertEqual(check_private_data.main(["--staged"]), 1)
            self.assertIn("BLOCKED", report.value())

    def test_ordinary_source_commit_passes(self) -> None:
        with TemporaryRepo() as root:
            write(root, "module.py", "def add(a, b):\n    return a + b\n")
            _git(root, "add", "module.py")
            self.assertEqual(check_private_data.main(["--staged"]), 0)

    def test_staged_bytes_are_checked_not_the_worktree_copy(self) -> None:
        """Stage a personal document, then overwrite the worktree copy with something harmless.

        A worktree-reading gate inspects the harmless version and waves the commit through while
        the personal bytes sit in the index and land in the commit.
        """
        with TemporaryRepo() as root:
            write(root, "notes.md", SYNTHETIC_RESUME)
            _git(root, "add", "notes.md")
            write(root, "notes.md", "just some harmless notes\n")
            with captured_stderr():
                self.assertEqual(check_private_data.main(["--staged"]), 1)

    def test_worktree_personal_content_does_not_mask_a_clean_staged_blob(self) -> None:
        """The mirror image: staged bytes are clean, so the commit is allowed."""
        with TemporaryRepo() as root:
            write(root, "notes.md", "harmless\n")
            _git(root, "add", "notes.md")
            write(root, "notes.md", SYNTHETIC_RESUME)
            self.assertEqual(check_private_data.main(["--staged"]), 0)

    def test_staged_deleted_worktree_file_is_still_checked(self) -> None:
        with TemporaryRepo() as root:
            write(root, "notes.md", SYNTHETIC_RESUME)
            _git(root, "add", "notes.md")
            (root / "notes.md").unlink()
            with captured_stderr():
                self.assertEqual(check_private_data.main(["--staged"]), 1)

    def test_unstaged_personal_file_does_not_block(self) -> None:
        with TemporaryRepo() as root:
            write(root, "keep.py", "value = 1\n")
            write(root, "resume.pdf", "%PDF-1.4 synthetic\n")
            _git(root, "add", "keep.py")
            self.assertEqual(check_private_data.main(["--staged"]), 0)


class AlreadyTrackedTest(unittest.TestCase):
    def test_tracked_personal_document_is_reported_with_disclosure_guidance(self) -> None:
        """§15.5: the report must say that pushed content is already disclosed."""
        with TemporaryRepo() as root:
            write(root, "notes.md", SYNTHETIC_RESUME)
            _git(root, "add", "-f", "notes.md")
            _git(root, "commit", "--quiet", "-m", "synthetic")
            findings = check_private_data.scan(staged=False)
            self.assertEqual([item.path for item in findings], ["notes.md"])

            with captured_stderr() as report:
                check_private_data._report(findings, staged=False)
            message = report.value()
            self.assertIn("ALREADY DISCLOSED", message)
            self.assertIn("does NOT remove it from history", message)


class ClassificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._repo = TemporaryRepo()
        self.root = self._repo.__enter__()

    def tearDown(self) -> None:
        self._repo.__exit__()

    def test_document_extension_is_high_confidence(self) -> None:
        write(self.root, "anything.docx", "synthetic")
        finding = check_private_data.classify("anything.docx")
        self.assertIsNotNone(finding)
        self.assertEqual(finding.confidence, "high")

    def test_generic_filename_with_personal_structure_is_detected(self) -> None:
        """§23.4: a generically named file with recognizable document structure."""
        write(self.root, "notes.md", SYNTHETIC_RESUME)
        finding = check_private_data.classify("notes.md")
        self.assertIsNotNone(finding)
        self.assertEqual(finding.confidence, "high")

    def test_single_weak_signal_is_ambiguous_not_promoted(self) -> None:
        """AC-04: an ambiguous document is not auto-classified as canonical evidence."""
        write(self.root, "note.md", "氏名: 山田 花子\n")
        finding = check_private_data.classify("note.md")
        self.assertIsNotNone(finding)
        self.assertEqual(finding.confidence, "ambiguous")

    def test_renamed_office_document_is_detected_by_container_shape(self) -> None:
        path = self.root / "notes.txt"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", "<w:document/>")
        finding = check_private_data.classify("notes.txt")
        self.assertIsNotNone(finding)
        self.assertEqual(finding.signal, "zip container shape")

    def test_declared_synthetic_fixtures_are_suppressed(self) -> None:
        write(self.root, "profile.example.md", SYNTHETIC_RESUME)
        write(self.root, "marked.md", SYNTHETIC_RESUME + "\nsynthetic://fixture\n")
        write(self.root, "declared.md", SYNTHETIC_RESUME + "\nprovenance: synthetic\n")
        for relative in ("profile.example.md", "marked.md", "declared.md"):
            with self.subTest(path=relative):
                self.assertIsNone(check_private_data.classify(relative))

    def test_fixture_directory_alone_does_not_suppress_detection(self) -> None:
        """A location is not a statement about content.

        Exempting examples/ tests/ fixtures/ mock/ wholesale turned them into blind spots: real
        personal data in examples/notes.md was invisible to an ordinary `git add`, while identical
        content one directory up was blocked.
        """
        for relative in (
            "examples/notes.md", "tests/notes.md", "fixtures/notes.md",
            "mock/notes.md", "skills/x/mocks/notes.md",
        ):
            with self.subTest(path=relative):
                write(self.root, relative, SYNTHETIC_RESUME)
                self.assertIsNotNone(check_private_data.classify(relative))

    def test_secret_pattern_is_detected(self) -> None:
        # Assembled at runtime so the literal never appears in tracked source: the release
        # bundler's own secret scan reads this file and would otherwise flag it. Same reason
        # policy_patterns.py builds its noqa pattern by concatenation.
        write(self.root, "config.txt", "AKIA" + "IOSFODNN7EXAMPLE\n")
        finding = check_private_data.classify("config.txt")
        self.assertIsNotNone(finding)
        self.assertEqual(finding.classification, "embedded secret")

    def test_binary_content_is_not_scanned_as_text(self) -> None:
        write(self.root, "blob.bin", b"\x00\x01\x02" + SYNTHETIC_RESUME.encode("utf-8"))
        self.assertIsNone(check_private_data.classify("blob.bin"))

    def test_oversized_file_is_classified_on_metadata_only(self) -> None:
        write(self.root, "big.md", "x" * (check_private_data.MAX_FILE_BYTES + 1))
        self.assertIsNone(check_private_data.classify("big.md"))

    def test_missing_path_does_not_raise(self) -> None:
        self.assertIsNone(check_private_data.classify("absent.md"))

    @unittest.skipIf(os.name == "nt", "symlink creation needs elevation on Windows")
    def test_symlink_is_not_followed(self) -> None:
        write(self.root, "real.md", SYNTHETIC_RESUME)
        (self.root / "link.md").symlink_to(self.root / "real.md")
        self.assertIsNone(check_private_data.classify("link.md"))


class DirectoryScanTest(unittest.TestCase):
    """`scan_directory` backs `private-doctor`'s stray report (PRD 13.1, AC-03)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_untracked_stray_is_found(self) -> None:
        write(self.root, "notes/履歴書.pdf", "x")
        findings, truncated = check_private_data.scan_directory(self.root)
        self.assertFalse(truncated)
        self.assertEqual([item.confidence for item in findings], ["high"])

    def test_cache_directories_are_skipped_everywhere(self) -> None:
        write(self.root, "node_modules/pkg/resume.pdf", "x")
        write(self.root, "a/b/__pycache__/resume.pdf", "x")
        findings, _ = check_private_data.scan_directory(self.root)
        self.assertEqual(findings, [])

    def test_repository_skips_do_not_apply_to_an_arbitrary_scan_root(self) -> None:
        """`data/` is this repository's ignored state; in ~/Documents it is just a folder."""
        write(self.root, "data/resume.pdf", "x")
        write(self.root, "career-home/resume.pdf", "x")
        findings, _ = check_private_data.scan_directory(self.root)
        self.assertEqual(len(findings), 2, [item.path for item in findings])

    def test_repository_skips_apply_at_the_top_of_a_worktree(self) -> None:
        (self.root / ".git").mkdir()
        write(self.root, "data/resume.pdf", "x")
        write(self.root, "docs/resume.pdf", "x")
        write(self.root, "docs/data/resume.pdf", "x")
        findings, _ = check_private_data.scan_directory(self.root)
        paths = sorted(item.path for item in findings)
        self.assertEqual(len(paths), 2, paths)
        self.assertTrue(all("docs" in path for path in paths), paths)

    def test_excluded_subtree_is_skipped(self) -> None:
        write(self.root, "private/blobs/resume.pdf", "x")
        write(self.root, "work/resume.pdf", "x")
        findings, _ = check_private_data.scan_directory(self.root, exclude=(self.root / "private",))
        self.assertEqual(len(findings), 1)
        self.assertIn("work", findings[0].path)

    def test_file_cap_stops_the_walk(self) -> None:
        for index in range(5):
            write(self.root, f"file{index}.txt", "harmless")
        original = check_private_data.MAX_SCAN_FILES
        check_private_data.MAX_SCAN_FILES = 2
        try:
            _, truncated = check_private_data.scan_directory(self.root)
        finally:
            check_private_data.MAX_SCAN_FILES = original
        self.assertTrue(truncated)


if __name__ == "__main__":
    unittest.main()
