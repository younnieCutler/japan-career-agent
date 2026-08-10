#!/usr/bin/env python3
"""Build a clean, source-identified release archive and verification bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from e2e_artifact import _path_variants


ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp|github_pat|sk)-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


class ReleaseBuildError(ValueError):
    """Raised when a source tree is not safe or reproducible enough to package."""


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=str(ROOT), capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise ReleaseBuildError(result.stderr.strip() or f"git {' '.join(arguments)} failed")
    return result.stdout


def _tracked_files() -> list[str]:
    output = _git("ls-files", "-z")
    paths = [item for item in output.split("\0") if item]
    if paths != sorted(paths):
        paths.sort()
    return paths


def _assert_clean(expected_commit: str | None) -> str:
    status = _git("status", "--porcelain=v1", "--untracked-files=all").strip()
    if status:
        raise ReleaseBuildError("release requires a clean working tree")
    commit = _git("rev-parse", "HEAD").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ReleaseBuildError(f"invalid source commit: {commit!r}")
    if expected_commit and expected_commit != commit:
        raise ReleaseBuildError(f"source commit {commit} does not match expected {expected_commit}")
    return commit


def _relative_path(path: str) -> Path:
    candidate = (ROOT / path).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise ReleaseBuildError(f"tracked path escapes repository: {path}") from exc
    return candidate


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_entries(paths: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    local_paths = {
        variant.lower()
        for root in (ROOT.resolve(), Path.home().resolve())
        for variant in _path_variants(root)
    }
    for relative in paths:
        path = _relative_path(relative)
        if path.is_symlink():
            raise ReleaseBuildError(f"symlink is not allowed in release source: {relative}")
        data = path.read_bytes()
        if b"\x00" not in data:
            text = data.decode("utf-8", errors="replace")
            lowered_text = text.lower()
            if any(local_path in lowered_text for local_path in local_paths):
                raise ReleaseBuildError(f"local path leaked into release source content: {relative}")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    raise ReleaseBuildError(f"secret-like material found in release source: {relative}")
        entries.append({"path": relative.replace("\\", "/"), "size": len(data), "sha256": _hash_bytes(data)})
    return entries


def _source_tree_hash(entries: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(entry["size"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(entry["sha256"].encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _write_zip(path: Path, source_paths: list[str]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in source_paths:
            source = _relative_path(relative)
            info = zipfile.ZipInfo(relative.replace("\\", "/"), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_wheel(output_dir: Path, commit: str, version: str) -> Path:
    """Build the PyPI wheel into the release bundle so both channels ship one verified build.

    `SOURCE_DATE_EPOCH` is pinned to the commit's own timestamp: without it the wheel embeds the
    build time and two builds of the same commit produce different bytes, which would make the
    recorded digest meaningless and break the bundle's reproducibility claim.
    """
    timestamp = _git("show", "-s", "--format=%ct", commit).strip()
    if not timestamp.isdigit():
        raise ReleaseBuildError(f"cannot read commit timestamp for {commit}")
    environment = {**os.environ, "SOURCE_DATE_EPOCH": timestamp}
    staging = output_dir / "_wheel"
    result = subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--wheel", "--outdir", str(staging), str(ROOT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    if result.returncode:
        raise ReleaseBuildError(f"wheel build failed: {result.stderr.strip() or result.stdout.strip()}")
    wheels = sorted(staging.glob("*.whl"))
    if len(wheels) != 1:
        raise ReleaseBuildError(f"expected exactly one wheel, found {[wheel.name for wheel in wheels]}")
    if f"-{version}-" not in wheels[0].name:
        raise ReleaseBuildError(f"wheel {wheels[0].name} does not carry release version {version}")
    destination = output_dir / wheels[0].name
    shutil.copyfile(wheels[0], destination)
    shutil.rmtree(staging)
    return destination


def _write_checksums(path: Path, files: list[Path]) -> None:
    lines = [f"{_sha256_file(file)}  {file.name}" for file in files]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def build(output_dir: Path, expected_commit: str | None = None) -> dict[str, Any]:
    commit = _assert_clean(expected_commit)
    manifest_path = ROOT / ".claude-plugin" / "plugin.json"
    version = json.loads(manifest_path.read_text(encoding="utf-8"))["version"]
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise ReleaseBuildError(f"invalid plugin version: {version!r}")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.resolve().is_relative_to(ROOT.resolve()):
        output_dir = output_dir.resolve()
    source_paths = _tracked_files()
    entries = _source_entries(source_paths)
    artifact = output_dir / f"japan-career-agent-v{version}.zip"
    _write_zip(artifact, source_paths)
    sbom_source = ROOT / "sbom.cdx.json"
    if not sbom_source.is_file():
        raise ReleaseBuildError("tracked sbom.cdx.json is required before release packaging")
    sbom = output_dir / "sbom.cdx.json"
    shutil.copyfile(sbom_source, sbom)
    wheel = _build_wheel(output_dir, commit, version)
    manifest = {
        "format_version": 1,
        "product": "japan-career-agent",
        "version": version,
        "source_commit": commit,
        "git_status_clean": True,
        "source_tree_sha256": _source_tree_hash(entries),
        "files": entries,
        "artifact": {"name": artifact.name, "size": artifact.stat().st_size, "sha256": _sha256_file(artifact)},
        "sbom": {"name": sbom.name, "size": sbom.stat().st_size, "sha256": _sha256_file(sbom)},
        "wheel": {"name": wheel.name, "size": wheel.stat().st_size, "sha256": _sha256_file(wheel)},
    }
    manifest_file = output_dir / "release-manifest.json"
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    checksums = output_dir / "SHA256SUMS"
    _write_checksums(checksums, [artifact, sbom, wheel, manifest_file])
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="release")
    parser.add_argument("--expected-commit")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    try:
        manifest = build(output_dir, args.expected_commit)
    except (OSError, ReleaseBuildError, json.JSONDecodeError) as exc:
        print(f"release build: FAIL ({exc})")
        return 1
    print(f"release build: PASS ({manifest['artifact']['name']}, source {manifest['source_commit']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
