#!/usr/bin/env python3
"""Own the release version, and write it into the files that only carry a copy.

`pyproject.toml` is the single source of truth. Everything else that names the release version --
the two plugin manifests, the npm bootstrapper, the SBOM -- is a generated copy, and nothing should
read a version *from* those files: doing so is what made `.claude-plugin/plugin.json` the de-facto
master while the docs claimed pyproject was.

`canonical_version()` is the one reader. `build_release.py`, `build_sbom.py` and
`check_version_bump.py` call it rather than parsing a manifest of their own, so there is exactly one
place that knows where the version lives.

`scripts/check_release_consistency.py` stays the gate. This is the fix for what it reports.
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
# Generated copies. Order is cosmetic; each is rewritten independently.
TARGETS = (
    ROOT / ".claude-plugin" / "plugin.json",
    ROOT / ".codex-plugin" / "plugin.json",
    ROOT / "packaging" / "npm" / "package.json",
)
# Rewriting one line keeps indentation, key order and the trailing newline as they are; a
# json.loads/json.dumps round trip reformats the whole file and buries the change in noise.
JSON_VERSION = re.compile(r"^(\s*\"version\"\s*:\s*\")([^\"]*)(\")", re.MULTILINE)
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


class VersionError(Exception):
    """The canonical version is missing or malformed."""


def version_from_pyproject(text: str) -> str:
    """The release version declared in the given pyproject.toml contents.

    Takes text rather than a path so a caller comparing against another git ref can pass
    `git show <ref>:pyproject.toml` through the same parser.
    """
    try:
        version = tomllib.loads(text)["project"]["version"]
    except (tomllib.TOMLDecodeError, KeyError) as exc:
        raise VersionError(f"pyproject.toml: cannot read project version ({exc})") from exc
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise VersionError(f"pyproject.toml: invalid release version {version!r}")
    return version


def canonical_version() -> str:
    """The release version, read from the file that owns it."""
    return version_from_pyproject(PYPROJECT.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report copies that disagree with pyproject instead of rewriting them",
    )
    args = parser.parse_args()
    try:
        version = canonical_version()
    except VersionError as exc:
        print(f"version sync errors:\n{exc}")
        return 1

    stale: list[str] = []
    written: list[str] = []
    for path in TARGETS:
        text = path.read_text(encoding="utf-8")
        match = JSON_VERSION.search(text)
        if match is None:
            stale.append(f"{path.relative_to(ROOT)}: no version field")
            continue
        if match.group(2) == version:
            continue
        name = str(path.relative_to(ROOT))
        if args.check:
            stale.append(f"{name}: {match.group(2)} != pyproject {version}")
            continue
        path.write_text(JSON_VERSION.sub(rf"\g<1>{version}\g<3>", text, count=1), encoding="utf-8")
        written.append(name)

    # The SBOM carries the version too, so a bump that stopped at the manifests would leave
    # `build_sbom.py --check` failing. Regenerating it here is what makes "bump pyproject, run this"
    # the whole procedure. Only on write: verifying the SBOM is `build_sbom.py --check`'s job, and
    # it already runs in the matrix -- repeating it here would be two owners for one fact.
    if not args.check:
        # Deferred, not module scope: build_sbom reads the version through canonical_version().
        import build_sbom  # noqa: PLC0415 -- avoids a circular import

        document = build_sbom.build_document(
            ROOT / "requirements.lock", ROOT / "requirements-dev.lock"
        )
        payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        sbom = ROOT / "sbom.cdx.json"
        if sbom.read_text(encoding="utf-8") != payload:
            sbom.write_text(payload, encoding="utf-8", newline="\n")
            written.append("sbom.cdx.json")

    if stale:
        print("version sync errors:")
        print("\n".join(stale))
        return 1
    if args.check:
        print(f"version sync: v{version} (copies agree)")
        return 0
    print(f"version sync: v{version} -> {', '.join(written) if written else 'already in step'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
