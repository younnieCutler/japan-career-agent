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
    # The npm bootstrapper installs `japan-career-agent==<its own version>`. If it falls behind,
    # `npx japan-career-agent@X` installs something that is not X, and nothing at runtime notices.
    ROOT / "packaging" / "npm" / "package.json",
)
# The wheel carries the same release. `uvx japan-career-agent` and the plugin must not be able to
# be two different builds of two different versions.
PYPROJECT_VERSION_PATTERN = re.compile(r"^version = \"([^\"]+)\"", re.MULTILINE)
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
CHANGELOG_HEADING = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)

# The release-channel section names two moving numbers in prose: the source version and the ref the
# stable marketplace channel points at. It sat stale for two releases, telling readers the two
# matched while the marketplace actually installed something older — the one thing that section
# exists to answer. Both numbers are now read from the files that own them.
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
# The section moved off the README entry pages and into the upgrade docs, one per language. The
# check follows it: a translation that keeps an old number is the same failure as an English one.
RELEASE_CHANNEL_HEADINGS = {
    ROOT / "docs" / "upgrading.md": "## Release channels",
    ROOT / "docs" / "upgrading_ko.md": "## 릴리스 채널",
    ROOT / "docs" / "upgrading_ja.md": "## リリースチャンネル",
}


def _section(text: str, heading: str) -> str | None:
    start = text.find(heading)
    if start < 0:
        return None
    body = text[start + len(heading):]
    ends = [position for position in (body.find("\n### "), body.find("\n## ")) if position >= 0]
    return body if not ends else body[: min(ends)]


def _names(section: str, value: str) -> bool:
    """Whether the section names this exact version or ref, not one it is a prefix of.

    `v1.18.1` is a substring of `v1.18.10`, so a plain containment test would report a section
    that has already moved ahead of the file it is being compared against as still matching.
    """
    return re.search(rf"(?<![\w.]){re.escape(value)}(?![\w.])", section) is not None


def _marketplace_ref() -> str | None:
    try:
        source = json.loads(MARKETPLACE.read_text(encoding="utf-8"))["plugins"][0]["source"]
        return source["ref"] if isinstance(source, dict) else None
    except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError):
        return None


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

    pyproject = ROOT / "pyproject.toml"
    pyproject_match = PYPROJECT_VERSION_PATTERN.search(pyproject.read_text(encoding="utf-8"))
    if pyproject_match is None:
        errors.append("pyproject.toml: missing project version")
    else:
        manifest_versions.append(pyproject_match.group(1))

    release_version = manifest_versions[0] if manifest_versions else None
    if manifest_versions and len(set(manifest_versions)) != 1:
        errors.append(f"release version mismatch across manifests: {manifest_versions}")

    changelog = ROOT / "CHANGELOG.md"
    changelog_matches = CHANGELOG_HEADING.finditer(changelog.read_text(encoding="utf-8"))
    changelog_match = next(changelog_matches, None)
    if changelog_match is None:
        errors.append("CHANGELOG.md: missing top release heading")
    elif release_version is not None and changelog_match.group(1) != release_version:
        errors.append(
            f"CHANGELOG.md: top release {changelog_match.group(1)!r} != manifest {release_version!r}"
        )

    marketplace_ref = _marketplace_ref()
    if marketplace_ref is None:
        errors.append(f"{MARKETPLACE.relative_to(ROOT)}: cannot read the stable marketplace ref")
    for path, heading in RELEASE_CHANNEL_HEADINGS.items():
        section = _section(path.read_text(encoding="utf-8"), heading)
        if section is None:
            errors.append(f"{path.name}: missing release-channel section {heading!r}")
            continue
        if marketplace_ref is not None and not _names(section, marketplace_ref):
            errors.append(
                f"{path.name}: release-channel section does not name the marketplace ref {marketplace_ref!r}"
            )
        if release_version is not None and not _names(section, release_version):
            errors.append(
                f"{path.name}: release-channel section does not name the source version {release_version!r}"
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
