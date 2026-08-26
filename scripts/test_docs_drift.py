#!/usr/bin/env python3
"""Each drift rule must actually fail when the fact it guards moves.

A checker that passes on a real repository proves nothing on its own: it would also pass if every
rule were `return []`. These tests break one fact at a time, in a copy of the repository, and
require the matching rule to notice.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = "scripts/check_docs_drift.py"
# Only what the checker reads. Copying the whole repository would pull the Vault fixtures and the
# GUI bundle into every test.
NEEDED = (
    "pyproject.toml",
    "README.md",
    "README_ko.md",
    "README_ja.md",
    "docs",
    # Whole directory: the docs link to scripts by path, so a partial copy would report the
    # missing ones as broken links.
    "scripts",
    "packaging/npm/README.md",
    # Whole directories: the Gate D rule imports execution_plans, which pulls the runtime core, and
    # that reaches into _shared. Listing individual modules here would just track those imports.
    "_shared",
    "skills",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "LICENSE",
)


def _sandbox(destination: Path) -> None:
    for relative in NEEDED:
        source = ROOT / relative
        if not source.exists():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            # SKILL.md is what the skill-coverage rule counts; the rest of a skill is not read.
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(source, target)


def _run(workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, CHECKER],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )


class DocsDriftTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temporary.name) / "repo"
        self.workspace.mkdir()
        _sandbox(self.workspace)
        self.addCleanup(self._temporary.cleanup)

    def _edit(self, relative: str, old: str, new: str) -> None:
        path = self.workspace / relative
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, f"fixture no longer contains {old!r}")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_the_unmodified_tree_is_clean(self) -> None:
        """Without this, every test below could be passing for the wrong reason."""
        result = _run(self.workspace)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_python_version_the_package_does_not_support_is_caught(self) -> None:
        self._edit("README.md", "3.11%20%7C%203.12%20%7C%203.13", "3.9%20%7C%203.10")
        result = _run(self.workspace)
        self.assertEqual(result.returncode, 1)
        self.assertIn("badge advertises", result.stdout)

    def test_a_shipped_skill_missing_from_the_table_is_caught(self) -> None:
        self._edit("README.md", "`career-tanaoroshi`", "career-tanaoroshi")
        result = _run(self.workspace)
        self.assertEqual(result.returncode, 1)
        self.assertIn("career-tanaoroshi", result.stdout)

    def test_a_gate_d_root_the_policy_does_not_support_is_caught(self) -> None:
        self._edit(
            "_shared/agent_context/orchestration.md",
            "`tenshoku-strategy`;",
            "`tenshoku-strategy`, and `mock-interviewer`;",
        )
        result = _run(self.workspace)
        self.assertEqual(result.returncode, 1)
        self.assertIn("execution_plans supports", result.stdout)

    def test_a_stale_check_count_is_caught(self) -> None:
        """The exact failure this rule was written for: the runbook fell twenty checks behind."""
        self._edit(
            "scripts/run_all_checks.py",
            '("policy", (PYTHON, "scripts/check_policy.py")),',
            '("policy", (PYTHON, "scripts/check_policy.py")),\n'
            '    ("extra", (PYTHON, "scripts/check_policy.py")),',
        )
        result = _run(self.workspace)
        self.assertEqual(result.returncode, 1)
        self.assertIn("registers", result.stdout)

    def test_a_relative_link_in_the_pypi_description_is_caught(self) -> None:
        self._edit("README.md", "## Safety", "See [contributing](CONTRIBUTING.md).\n\n## Safety")
        result = _run(self.workspace)
        self.assertEqual(result.returncode, 1)
        self.assertIn("breaks on PyPI", result.stdout)

    def test_a_docs_link_that_resolves_to_nothing_is_caught(self) -> None:
        self._edit("docs/README.md", "(cli-reference.md)", "(cli-reference-renamed.md)")
        result = _run(self.workspace)
        self.assertEqual(result.returncode, 1)
        self.assertIn("resolves to nothing", result.stdout)

    def test_a_docs_page_no_hub_links_is_caught(self) -> None:
        (self.workspace / "docs" / "ORPHANED.md").write_text("# Orphan\n", encoding="utf-8")
        result = _run(self.workspace)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ORPHANED.md", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
