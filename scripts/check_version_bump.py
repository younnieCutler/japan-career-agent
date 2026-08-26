#!/usr/bin/env python3
"""Fail a PR that changes behavior without bumping the release version.

`check_release_consistency.py` only verifies that whatever version IS declared is
consistent across the manifests/README/CHANGELOG. It says nothing about whether a bump
should have happened at all, and that gap let a real hardening PR merge as an unversioned
"1.6.2" (README.md#L63's `1.6.2` bullet list gained a whole new paragraph of behavior
changes with no CHANGELOG entry or version bump). This script closes that gap: any PR
that touches a non-test, non-doc file under skills/, _shared/, scripts/, or hooks/ must
also change `pyproject.toml`'s `version` field relative to the base branch. That file is the
single source of truth; the plugin and npm manifests are generated copies and are not read here.

Skips cleanly (exit 0) whenever there is nothing to compare against — a shallow local
clone without `origin/main` fetched, or a push that lands exactly on `origin/main` (e.g.
CI re-running after a squash-merge). It is not a hard gate on every git operation, only on
an actual PR diff.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sync_version import VersionError, version_from_pyproject

ROOT = Path(__file__).resolve().parent.parent
BASE_REF = "origin/main"
CANONICAL = "pyproject.toml"

SUBSTANTIVE_ROOTS = ("skills/", "_shared/", "scripts/", "hooks/")
EXEMPT_SUFFIXES = (".md",)


def _git(*args: str) -> str:
    # Explicit UTF-8: `text=True` alone decodes with the locale codec, and pyproject.toml is not
    # ASCII. On a Japanese Windows shell that is a cp932 UnicodeDecodeError rather than a version.
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout.strip()


def _base_is_available() -> bool:
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", BASE_REF],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def changed_files() -> list[str]:
    # Plain two-dot diff (tree comparison), not three-dot/merge-base: CI checkouts are shallow
    # (fetch-depth 1) and may not share enough history to compute a merge-base even though both
    # commit objects themselves are present after fetching each ref.
    output = _git("diff", "--name-only", BASE_REF, "HEAD")
    return [line for line in output.splitlines() if line.strip()]


def is_substantive(path: str) -> bool:
    if path.endswith(EXEMPT_SUFFIXES):
        return False
    if not path.startswith(SUBSTANTIVE_ROOTS):
        return False
    name = Path(path).name
    if name.startswith("test_") or "/tests/" in f"/{path}":
        return False
    return True


def declared_version(ref: str) -> str | None:
    """The canonical version at a git ref, parsed the same way as the worktree's."""
    try:
        text = _git("show", f"{ref}:{CANONICAL}")
    except subprocess.CalledProcessError:
        return None
    try:
        return version_from_pyproject(text)
    except VersionError:
        return None


def main() -> int:
    if not _base_is_available():
        print(f"version bump check: skipped ({BASE_REF} not available locally)")
        return 0

    files = changed_files()
    if not files:
        print("version bump check: skipped (no diff against origin/main)")
        return 0

    substantive = sorted(f for f in files if is_substantive(f))
    if not substantive:
        print("version bump check: skipped (no substantive skills/_shared/scripts/hooks changes)")
        return 0

    base_version = declared_version(BASE_REF)
    head_version = declared_version("HEAD")
    if base_version is not None and base_version == head_version:
        print("version bump check: FAILED", file=sys.stderr)
        print(
            f"{len(substantive)} substantive file(s) changed but {CANONICAL}'s version "
            f"is still {head_version!r}:",
            file=sys.stderr,
        )
        for path in substantive:
            print(f"  {path}", file=sys.stderr)
        print(
            "\nBump the version in pyproject.toml, run scripts/sync_version.py to write it into "
            "the plugin and npm manifests, add a CHANGELOG.md entry, update the release-channel "
            "section in docs/upgrading.md (and _ko/_ja), then run "
            "scripts/check_release_consistency.py.\n"
            "If this change is genuinely docs/test-only, move it out of skills/_shared/scripts/"
            "hooks or rename it to test_*.",
            file=sys.stderr,
        )
        return 1

    print(f"version bump check: {base_version} -> {head_version} ({len(substantive)} substantive file(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
