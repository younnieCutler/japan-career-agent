#!/usr/bin/env python3
"""Smoke-test an unpacked release bundle as a third-party installation."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from verify_release import verify


def _run(script: Path, *args: str, cwd: Path) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(script), *args, "--format", "json"],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("Career Agent smoke command did not return an object")
    return value


def smoke(bundle: Path) -> None:
    manifest_path = bundle / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = bundle / manifest["artifact"]["name"]
    sbom = bundle / manifest["sbom"]["name"]
    verified = verify(manifest_path, bundle / "SHA256SUMS", artifact, sbom)
    with tempfile.TemporaryDirectory(prefix="career-agent-release-smoke-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(artifact) as archive:
            archive.extractall(root)
        claude_manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        codex_manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        if claude_manifest.get("version") != verified["version"] or codex_manifest.get("version") != verified["version"]:
            raise RuntimeError("unpacked plugin manifests do not match the release version")
        marketplace = json.loads((root / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        source = marketplace["plugins"][0]["source"]
        if not re.fullmatch(r"v\d+\.\d+\.\d+", str(source.get("ref", ""))):
            raise RuntimeError("stable marketplace source is not immutable")

        vault = root / "smoke-vault"
        workspace = root / "smoke-workspace"
        workspace.mkdir()
        script = root / "skills" / "career-agent" / "career_agent.py"
        setup = _run(script, "setup", "--vault", str(vault), "--track", "chuto", "--target-role", "Data Engineer", cwd=workspace)
        if setup.get("mode") != "setup":
            raise RuntimeError("setup smoke did not return setup mode")
        status = _run(script, "status", "--vault", str(vault), cwd=workspace)
        if status.get("event_count") != 0 or status.get("pending_proposals") != 0:
            raise RuntimeError("fresh status smoke is not empty")
        guided = _run(script, "guided", "--vault", str(vault), cwd=workspace)
        if guided.get("mode") != "guided" or not guided.get("ok"):
            raise RuntimeError("guided smoke did not return a usable menu")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    try:
        smoke(args.bundle.resolve())
    except (OSError, RuntimeError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        print(f"release install smoke: FAIL ({exc})")
        return 1
    print("release install smoke: PASS (unpack, manifest, setup, status, guided)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
