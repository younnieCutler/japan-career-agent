#!/usr/bin/env python3
"""Write the canonical pyproject version into the manifests that duplicate it.

`pyproject.toml` owns the release version. The two plugin manifests and the npm bootstrapper carry
their own copy because their formats have nowhere else to read it from, and keeping four files in
step by hand is how they drifted before. This propagates one number; it decides nothing.

`scripts/check_release_consistency.py` stays the gate. This is the fix for what it reports.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
# Same three files check_release_consistency.py compares against pyproject.
TARGETS = (
    ROOT / ".claude-plugin" / "plugin.json",
    ROOT / ".codex-plugin" / "plugin.json",
    ROOT / "packaging" / "npm" / "package.json",
)
PYPROJECT_VERSION = re.compile(r"^version = \"([^\"]+)\"", re.MULTILINE)
# Rewriting one line keeps indentation, key order and the trailing newline as they are; a
# json.loads/json.dumps round trip reformats the whole file and buries the change in noise.
JSON_VERSION = re.compile(r"^(\s*\"version\"\s*:\s*\")([^\"]*)(\")", re.MULTILINE)
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def canonical_version() -> str:
    """The release version, read from the file that owns it."""
    match = PYPROJECT_VERSION.search(PYPROJECT.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit("pyproject.toml: missing project version")
    version = match.group(1)
    if not VERSION_PATTERN.fullmatch(version):
        raise SystemExit(f"pyproject.toml: invalid release version {version!r}")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report manifests that disagree with pyproject instead of rewriting them",
    )
    args = parser.parse_args()
    version = canonical_version()

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

    if stale:
        print("version sync errors:")
        print("\n".join(stale))
        return 1
    if args.check:
        print(f"version sync: v{version} (manifests agree)")
        return 0
    print(f"version sync: v{version} -> {', '.join(written) if written else 'already in step'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
