#!/usr/bin/env python3
"""Verify that an immutable Git tag identifies the repository's declared release."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
TAG_PATTERN = re.compile(r"^v(\d+\.\d+\.\d+)$")
CHANGELOG_HEADING = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)
README_RELEASE_PATTERNS = {
    "README.md": re.compile(r"^Current release:\s*`([^`]+)`\.", re.MULTILINE),
    "README_ko.md": re.compile(r"^현재 릴리스:\s*`([^`]+)`\.", re.MULTILINE),
    "README_ja.md": re.compile(r"^現在のリリース:\s*`([^`]+)`。", re.MULTILINE),
}
MANIFESTS = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json")


class ReleaseTagError(RuntimeError):
    """Raised when the local release metadata cannot be inspected."""


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise ReleaseTagError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _declared_version(root: Path) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    versions: list[str] = []
    for relative in MANIFESTS:
        path = root / relative
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{relative}: cannot read manifest ({exc})")
            continue
        version = document.get("version")
        if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
            errors.append(f"{relative}: invalid version {version!r}")
            continue
        versions.append(version)
    if versions and len(set(versions)) != 1:
        errors.append(f"plugin manifest version mismatch: {versions}")
    return (versions[0] if versions else None), errors


def validate_release_tag(root: Path, tag: str, expected_sha: str | None = None) -> list[str]:
    """Return deterministic consistency errors for ``tag``; an empty list means valid."""
    root = root.resolve()
    errors: list[str] = []
    version, metadata_errors = _declared_version(root)
    errors.extend(metadata_errors)
    if version is None:
        return errors

    tag_match = TAG_PATTERN.fullmatch(tag)
    if tag_match is None:
        errors.append(f"tag must be vX.Y.Z, got {tag!r}")
    elif tag_match.group(1) != version:
        errors.append(f"tag {tag!r} != declared version v{version}")

    changelog_match = CHANGELOG_HEADING.search((root / "CHANGELOG.md").read_text(encoding="utf-8"))
    if changelog_match is None:
        errors.append("CHANGELOG.md: missing top release heading")
    elif changelog_match.group(1) != version:
        errors.append(f"CHANGELOG.md: top release {changelog_match.group(1)!r} != {version!r}")

    for relative, pattern in README_RELEASE_PATTERNS.items():
        match = pattern.search((root / relative).read_text(encoding="utf-8"))
        if match is None:
            errors.append(f"{relative}: missing current release marker")
        elif match.group(1) != version:
            errors.append(f"{relative}: current release {match.group(1)!r} != {version!r}")

    try:
        tag_sha = _git(root, "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
    except ReleaseTagError as exc:
        errors.append(f"tag {tag!r} is missing or invalid: {exc}")
        return errors

    try:
        target_sha = _git(root, "rev-parse", "--verify", expected_sha or "HEAD")
    except ReleaseTagError as exc:
        errors.append(f"target commit is invalid: {exc}")
        return errors
    if tag_sha != target_sha:
        errors.append(f"tag {tag!r} points to {tag_sha}, expected {target_sha}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="immutable release tag, e.g. v1.6.4")
    parser.add_argument("--sha", help="expected commit/ref; defaults to HEAD")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        errors = validate_release_tag(args.repo, args.tag, args.sha)
    except (OSError, ReleaseTagError) as exc:
        print(f"release tag check: {exc}", file=sys.stderr)
        return 1
    if errors:
        print("release tag consistency errors:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    target = args.sha or _git(args.repo, "rev-parse", "HEAD")
    resolved = _git(args.repo, "rev-parse", "--verify", f"refs/tags/{args.tag}^{{commit}}")
    print(f"release tag consistency: {args.tag} -> {resolved} (target {target})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
