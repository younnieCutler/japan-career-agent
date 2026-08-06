#!/usr/bin/env python3
"""Keep the current release identity aligned across manifests and public docs."""

from __future__ import annotations

import json
import re
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = (
    ROOT / ".claude-plugin" / "plugin.json",
    ROOT / ".codex-plugin" / "plugin.json",
)
README_RELEASE_PATTERNS = {
    ROOT / "README.md": re.compile(r"^Current release:\s*`([^`]+)`\.", re.MULTILINE),
    ROOT / "README_ko.md": re.compile(r"^현재 릴리스:\s*`([^`]+)`\.", re.MULTILINE),
    ROOT / "README_ja.md": re.compile(r"^現在のリリース:\s*`([^`]+)`。", re.MULTILINE),
}
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
CHANGELOG_HEADING = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-tag",
        action="store_true",
        help="also require the immutable v<version> tag to exist in the current checkout",
    )
    args = parser.parse_args()
    errors: list[str] = []
    manifest_versions: list[str] = []

    for path in MANIFESTS:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: cannot read JSON ({exc})")
            continue
        version = document.get("version")
        if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
            errors.append(f"{path.relative_to(ROOT)}: invalid release version {version!r}")
            continue
        manifest_versions.append(version)

    release_version = manifest_versions[0] if manifest_versions else None
    if manifest_versions and len(set(manifest_versions)) != 1:
        errors.append(f"plugin manifest version mismatch: {manifest_versions}")

    changelog = ROOT / "CHANGELOG.md"
    changelog_matches = CHANGELOG_HEADING.finditer(changelog.read_text(encoding="utf-8"))
    changelog_match = next(changelog_matches, None)
    if changelog_match is None:
        errors.append("CHANGELOG.md: missing top release heading")
    elif release_version is not None and changelog_match.group(1) != release_version:
        errors.append(
            f"CHANGELOG.md: top release {changelog_match.group(1)!r} != manifest {release_version!r}"
        )

    for path, pattern in README_RELEASE_PATTERNS.items():
        match = pattern.search(path.read_text(encoding="utf-8"))
        if match is None:
            errors.append(f"{path.name}: missing current release marker")
        elif release_version is not None and match.group(1) != release_version:
            errors.append(
                f"{path.name}: current release {match.group(1)!r} != manifest {release_version!r}"
            )

    if args.require_tag and release_version is not None:
        tag = f"v{release_version}"
        tag_check = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/tags/{tag}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if tag_check.returncode != 0:
            errors.append(f"missing immutable release tag: {tag}")

    if errors:
        print("release consistency errors:")
        print("\n".join(errors))
        return 1
    print(f"release consistency: v{release_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
