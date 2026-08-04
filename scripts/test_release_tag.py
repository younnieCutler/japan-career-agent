#!/usr/bin/env python3
"""Focused tests for immutable release tag validation and workflow wiring."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import check_release_tag


ROOT = Path(__file__).resolve().parents[1]


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, encoding="utf-8", capture_output=True, check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


def write_release_files(root: Path, version: str) -> None:
    (root / ".claude-plugin").mkdir()
    (root / ".codex-plugin").mkdir()
    for relative in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        (root / relative).write_text(json.dumps({"version": version}) + "\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(f"# Changelog\n\n## [{version}] — 2026-08-04\n", encoding="utf-8")
    (root / "README.md").write_text(f"Current release: `{version}`.\n", encoding="utf-8")
    (root / "README_ko.md").write_text(f"현재 릴리스: `{version}`.\n", encoding="utf-8")
    (root / "README_ja.md").write_text(f"現在のリリース: `{version}`。\n", encoding="utf-8")


class ReleaseTagTests(unittest.TestCase):
    def test_annotated_tag_matches_release_identity_and_sha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "-b", "main")
            git(root, "config", "user.email", "test@example.invalid")
            git(root, "config", "user.name", "Release Test")
            write_release_files(root, "1.6.4")
            git(root, "add", ".")
            git(root, "commit", "-m", "fixture")
            sha = git(root, "rev-parse", "HEAD")
            git(root, "tag", "-a", "v1.6.4", "-m", "Release v1.6.4")
            self.assertEqual(check_release_tag.validate_release_tag(root, "v1.6.4", sha), [])

            git(root, "commit", "--allow-empty", "-m", "unreleased change")
            new_sha = git(root, "rev-parse", "HEAD")
            errors = check_release_tag.validate_release_tag(root, "v1.6.4", new_sha)
            self.assertTrue(any("points to" in error for error in errors), errors)

    def test_metadata_and_tag_name_mismatches_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "-b", "main")
            git(root, "config", "user.email", "test@example.invalid")
            git(root, "config", "user.name", "Release Test")
            write_release_files(root, "1.6.4")
            git(root, "add", ".")
            git(root, "commit", "-m", "fixture")
            git(root, "tag", "-a", "v1.6.3", "-m", "Release v1.6.3")
            errors = check_release_tag.validate_release_tag(root, "v1.6.3")
            self.assertTrue(any("declared version" in error for error in errors), errors)

    def test_workflow_runs_checks_before_immutable_tag_and_release(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        for marker in (
            "branches: [main]",
            "contents: write",
            "python scripts/run_all_checks.py",
            "scripts/check_release_tag.py",
            "git tag --annotate",
            "git push origin",
            "gh release create",
        ):
            self.assertIn(marker, workflow)


if __name__ == "__main__":
    unittest.main()
