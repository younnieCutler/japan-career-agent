"""Regression tests for reproducible E2E artifact packaging."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

import e2e_artifact as artifact


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def clean_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch", "main", str(root)], check=True, capture_output=True)
    git(root, "config", "user.email", "e2e@example.invalid")
    git(root, "config", "user.name", "E2E Fixture")
    (root / "tracked.txt").write_text("clean\n", encoding="utf-8")
    git(root, "add", "tracked.txt")
    git(root, "commit", "-m", "fixture")


def skill_statuses() -> dict[str, dict[str, object]]:
    return {
        "runtime": {"status": "runtime_e2e_pass", "runtime_commands": ["matching_v3", "career_agent"]},
        "contract": {"status": "contract_audit_pass", "contract_checks": ["skill marker"]},
        "manual": {"status": "not_executable", "reason": "instruction-only skill without a local runtime"},
    }


class RepositoryIdentityTests(unittest.TestCase):
    def test_identity_records_clean_and_dirty_tree_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_git_repo(root)
            clean = artifact.repository_identity(root)
            self.assertTrue(clean["git_status_clean"])
            self.assertEqual(len(clean["repository_commit"]), 40)
            self.assertEqual(clean["git_status_porcelain"], [])

            (root / "tracked.txt").write_text("dirty\n", encoding="utf-8")
            dirty = artifact.repository_identity(root)
            self.assertFalse(dirty["git_status_clean"])
            self.assertNotEqual(clean["dirty_diff_sha256"], dirty["dirty_diff_sha256"])
            self.assertTrue(dirty["git_status_porcelain"])

    def test_runtime_identity_is_path_free(self) -> None:
        runtime = artifact.runtime_identity()
        self.assertIn(runtime["os"], {"Windows", "Linux", "Darwin"})
        self.assertTrue(runtime["python_version"])
        self.assertNotIn("\\", runtime["python_version"] or "")
        self.assertNotIn("/", runtime["node_version"] or "")

    def test_prepare_detached_worktree_uses_exact_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            worktree = root / "worktree"
            repo.mkdir()
            clean_git_repo(repo)
            commit = artifact.repository_identity(repo)["repository_commit"]
            prepared = artifact.prepare_detached_worktree(
                repo_root=repo,
                worktree=worktree,
                expected_commit=commit,
            )
            self.assertEqual(prepared["repository"]["repository_commit"], commit)
            self.assertTrue(prepared["repository"]["git_status_clean"])
            self.assertEqual(prepared["repository"]["repository_branch"], "(detached)")
            subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo, check=True)


class ContractClassificationTests(unittest.TestCase):
    def test_generic_pass_is_rejected_and_explicit_states_are_accepted(self) -> None:
        validated = artifact.validate_skill_statuses(skill_statuses())
        self.assertEqual(validated["runtime"]["status"], "runtime_e2e_pass")
        with self.assertRaises(artifact.ArtifactError):
            artifact.validate_skill_statuses({"skill": {"status": "PASS"}})

    def test_fixture_correction_is_visible_in_final_status(self) -> None:
        result = artifact.fixture_result_status(
            initial_failed_commands=["matching_parkminjun"],
            correction_kind="fixture",
            correction_reason="source_type was invalid; provenance remains synthetic",
            final_passed=True,
        )
        self.assertEqual(result["status"], "PASS_AFTER_FIXTURE_CORRECTION")
        with self.assertRaises(artifact.ArtifactError):
            artifact.fixture_result_status(
                initial_failed_commands=["first-run"],
                correction_kind="unknown",
                correction_reason=None,
                final_passed=True,
            )


class RedactionTests(unittest.TestCase):
    def test_known_and_generic_local_paths_are_found(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            source = root / "artifact"
            stage = root / "stage"
            source.mkdir()
            stage.mkdir()
            (source / "leak.txt").write_text(
                f"home={Path.home()}\nother=C:\\Users\\Other\\private\\file.txt\n",
                encoding="utf-8",
            )
            pairs = artifact._redaction_roots(repo, source, stage)
            findings = artifact.scan_text_artifacts(source, pairs)
            tokens = {finding["token"] for finding in findings}
            self.assertIn("<HOME>", tokens)
            self.assertIn("local_absolute_path", tokens)

    def test_redacted_copy_has_no_local_path_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            source = root / "artifact"
            stage = root / "stage"
            source.mkdir()
            pairs = artifact._redaction_roots(repo, source, stage)
            (source / "report.md").write_text(f"repo={repo}\nhome={Path.home()}\n", encoding="utf-8")
            artifact._copy_redacted_tree(source, stage, pairs)
            self.assertEqual(artifact.scan_text_artifacts(stage, pairs), [])
            text = (stage / "report.md").read_text(encoding="utf-8")
            self.assertIn("<REPOSITORY>", text)
            self.assertIn("<HOME>", text)
            self.assertFalse((stage / "report.md").read_bytes().startswith(b"\xef\xbb\xbf"))


class PackageTests(unittest.TestCase):
    def test_package_manifest_records_identity_runtime_status_and_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            artifact_root = root / "artifact"
            output = root / "artifact.zip"
            repo.mkdir()
            artifact_root.mkdir()
            clean_git_repo(repo)
            (artifact_root / "outputs").mkdir()
            (artifact_root / "outputs" / "commands.jsonl").write_text(
                json.dumps({"exit_code": 0, "cwd": str(repo)}) + "\n", encoding="utf-8"
            )
            (artifact_root / "README.md").write_text(f"repo={repo}\n", encoding="utf-8")

            result = artifact.package_artifact(
                artifact_root=artifact_root,
                output_zip=output,
                repo_root=repo,
                skill_statuses=skill_statuses(),
                expected_commit=artifact.repository_identity(repo)["repository_commit"],
            )
            self.assertTrue(output.is_file())
            self.assertEqual(result["entries"], len(result["manifest"]["files"]) + 1)
            manifest = result["manifest"]
            self.assertEqual(manifest["schema"], artifact.ARTIFACT_SCHEMA)
            self.assertTrue(manifest["repository"]["git_status_clean"])
            self.assertTrue(manifest["runtime"]["python_version"])
            self.assertIn("node_version", manifest["runtime"])
            self.assertEqual(manifest["redaction"]["status"], "PASS")
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                packaged = json.loads(
                    archive.read("artifact/artifact-manifest.json").decode("utf-8")
                )
            self.assertEqual(packaged["repository"]["repository_commit"], manifest["repository"]["repository_commit"])

    def test_dirty_tree_is_rejected_without_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            artifact_root = root / "artifact"
            output = root / "artifact.zip"
            repo.mkdir()
            artifact_root.mkdir()
            clean_git_repo(repo)
            (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(artifact.ArtifactError, "dirty"):
                artifact.package_artifact(
                    artifact_root=artifact_root,
                    output_zip=output,
                    repo_root=repo,
                    skill_statuses=skill_statuses(),
                )
            self.assertFalse(output.exists())

    def test_initial_command_failure_requires_correction_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            artifact_root = root / "artifact"
            output = root / "artifact.zip"
            repo.mkdir()
            (artifact_root / "outputs").mkdir(parents=True)
            clean_git_repo(repo)
            (artifact_root / "outputs" / "commands.jsonl").write_text(
                json.dumps({"exit_code": 2, "argv": ["matching"]}) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(artifact.ArtifactError, "correction"):
                artifact.package_artifact(
                    artifact_root=artifact_root,
                    output_zip=output,
                    repo_root=repo,
                    skill_statuses=skill_statuses(),
                )

    def test_manifest_metadata_with_an_unknown_user_path_fails_final_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            artifact_root = root / "artifact"
            output = root / "artifact.zip"
            repo.mkdir()
            artifact_root.mkdir()
            clean_git_repo(repo)
            statuses = skill_statuses()
            statuses["runtime"]["runtime_commands"] = [r"C:\Users\Other\private\command"]
            with self.assertRaisesRegex(artifact.ArtifactError, "redaction gate"):
                artifact.package_artifact(
                    artifact_root=artifact_root,
                    output_zip=output,
                    repo_root=repo,
                    skill_statuses=statuses,
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
