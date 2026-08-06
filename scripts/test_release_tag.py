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
    (root / ".claude-plugin").mkdir(exist_ok=True)
    (root / ".codex-plugin").mkdir(exist_ok=True)
    for relative in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        (root / relative).write_text(json.dumps({"version": version}) + "\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(f"# Changelog\n\n## [{version}] — 2026-08-04\n", encoding="utf-8")
    (root / "README.md").write_text(f"Current release: `{version}`.\n", encoding="utf-8")
    (root / "README_ko.md").write_text(f"현재 릴리스: `{version}`.\n", encoding="utf-8")
    (root / "README_ja.md").write_text(f"現在のリリース: `{version}`。\n", encoding="utf-8")


def release_version_changed(root: Path, previous_ref: str) -> bool:
    """Mirror the workflow's previous-main-ref release version gate for fixture tests."""
    current = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    previous = json.loads(git(root, "show", f"{previous_ref}:.claude-plugin/plugin.json"))["version"]
    return current != previous


def publish_allowed(publish: str, github_ref: str, head_sha: str, origin_main_sha: str) -> bool:
    """Mirror the workflow gate that limits real publishing to current main."""
    return publish != "true" or (
        github_ref == "refs/heads/main" and head_sha == origin_main_sha
    )


class ReleaseTagTests(unittest.TestCase):
    def test_version_unchanged_main_commit_is_not_a_release_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "-b", "main")
            git(root, "config", "user.email", "test@example.invalid")
            git(root, "config", "user.name", "Release Test")
            write_release_files(root, "1.6.5")
            git(root, "add", ".")
            git(root, "commit", "-m", "release")
            previous_sha = git(root, "rev-parse", "HEAD")
            (root / "README.md").write_text("Current release: `1.6.5`. Typo fixed.\n", encoding="utf-8")
            git(root, "add", "README.md")
            git(root, "commit", "-m", "docs: fix typo")
            self.assertFalse(release_version_changed(root, previous_sha))

            write_release_files(root, "1.6.6")
            git(root, "add", ".")
            git(root, "commit", "-m", "release: bump")
            self.assertTrue(release_version_changed(root, previous_sha))

    def test_push_compares_event_before_when_head_parent_has_same_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "-b", "main")
            git(root, "config", "user.email", "test@example.invalid")
            git(root, "config", "user.name", "Release Test")
            write_release_files(root, "1.6.4")
            git(root, "add", ".")
            git(root, "commit", "-m", "release")
            previous_main_sha = git(root, "rev-parse", "HEAD")

            (root / "README.md").write_text("Current release: `1.6.4`. Docs update.\n", encoding="utf-8")
            git(root, "add", "README.md")
            git(root, "commit", "-m", "docs: update")
            write_release_files(root, "1.6.5")
            git(root, "add", ".")
            git(root, "commit", "-m", "release: bump")

            self.assertTrue(release_version_changed(root, previous_main_sha))
            self.assertNotEqual(git(root, "rev-parse", "HEAD^"), previous_main_sha)

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
            "workflow_dispatch:",
            "publish:",
            "dry_run:",
            'if [[ "$publish" == "true" ]]; then',
            'refs/heads/main',
            "HEAD must equal origin/main before publishing.",
            "contents: write",
            "python scripts/run_all_checks.py",
            "scripts/check_release_tag.py",
            "scripts/check_release_consistency.py --require-tag",
            "changed=false",
            "if: steps.release.outputs.changed == 'true'",
            "github-actions[bot]",
            "41898282+github-actions[bot]@users.noreply.github.com",
            "git tag --annotate",
            "git push origin",
            "gh release create",
        ):
            self.assertIn(marker, workflow)
        self.assertNotIn("branches: [main]", workflow)
        self.assertNotIn("github.event.before", workflow)
        self.assertLess(workflow.index("python scripts/run_all_checks.py"), workflow.index("git tag --annotate"))

    def test_publish_requires_current_main_head(self) -> None:
        self.assertFalse(publish_allowed("true", "refs/heads/agent/v17-11-canary-final", "abc", "abc"))
        self.assertFalse(publish_allowed("true", "refs/heads/main", "abc", "def"))
        self.assertTrue(publish_allowed("true", "refs/heads/main", "abc", "abc"))
        self.assertTrue(publish_allowed("false", "refs/heads/agent/v17-11-canary-final", "abc", "def"))


if __name__ == "__main__":
    unittest.main()
