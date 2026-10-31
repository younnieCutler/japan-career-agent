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

        workspace = root / "smoke-workspace"
        workspace.mkdir()
        pipeline_script = root / "scripts" / "pipeline.py"
        upsert_res = subprocess.run(
            [
                sys.executable,
                str(pipeline_script),
                "upsert",
                "acme-corp",
                "--json",
                '{"name":"Acme Corp","stage":1}',
            ],
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if upsert_res.returncode != 0 or "upsert: acme-corp" not in upsert_res.stdout:
            raise RuntimeError(f"pipeline upsert smoke failed: {upsert_res.stderr or upsert_res.stdout}")
        doc_script = root / "scripts" / "document.py"
        model = _run(doc_script, "model", "acme-corp", cwd=workspace)
        if model.get("mode") != "document-model" or not model.get("ok"):
            raise RuntimeError("document model smoke did not return document-model")


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
