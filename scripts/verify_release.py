#!/usr/bin/env python3
"""Verify release manifest, checksums, SBOM identity, and archive contents."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


HEX64 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")

# The product was renamed to `japan-career-agent` in 2.1.0. Bundles published under the old name
# are already downloaded and signed; refusing them here would mean this verifier could no longer
# check the very releases people still hold. The name a bundle carries is an identity to match,
# not a version to advance, so both remain valid forever.
PRODUCT_NAMES = ("japan-career-agent", "japan-recruit-ai-agent")


class ReleaseVerificationError(ValueError):
    """Raised when a release bundle fails an identity or content check."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReleaseVerificationError(f"{path.name} must contain an object")
    return value


def _check_name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or Path(value).name != value:
        raise ReleaseVerificationError(f"{label} must be a plain filename")
    return value


def _check_manifest(manifest: dict[str, Any]) -> None:
    required = {"format_version", "product", "version", "source_commit", "git_status_clean", "source_tree_sha256", "files", "artifact", "sbom"}
    # `wheel` arrived in 2.1.0 with the PyPI channel. It is optional rather than required so this
    # verifier still accepts the 2.0.x bundles that predate it; an unknown key stays a hard error,
    # because a manifest carrying something this contract does not describe was not built by it.
    if set(manifest) - {"wheel"} != required:
        raise ReleaseVerificationError("manifest keys do not match the release contract")
    if manifest["format_version"] != 1 or manifest["product"] not in PRODUCT_NAMES:
        raise ReleaseVerificationError("manifest identity is invalid")
    if not isinstance(manifest["version"], str) or not re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]):
        raise ReleaseVerificationError("manifest version is invalid")
    if not isinstance(manifest["source_commit"], str) or not COMMIT.fullmatch(manifest["source_commit"]):
        raise ReleaseVerificationError("manifest source_commit is invalid")
    if manifest["git_status_clean"] is not True:
        raise ReleaseVerificationError("official release cannot be built from a dirty tree")
    if not isinstance(manifest["source_tree_sha256"], str) or not HEX64.fullmatch(manifest["source_tree_sha256"]):
        raise ReleaseVerificationError("manifest source tree digest is invalid")
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        raise ReleaseVerificationError("manifest files must be a non-empty list")
    seen: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "size", "sha256"}:
            raise ReleaseVerificationError("manifest file entry is invalid")
        path = entry["path"]
        pure = PurePosixPath(path) if isinstance(path, str) else PurePosixPath("")
        if not isinstance(path, str) or pure.is_absolute() or ".." in pure.parts or path in seen:
            raise ReleaseVerificationError(f"unsafe or duplicate manifest path: {path!r}")
        seen.add(path)
        if (
            not isinstance(entry["size"], int)
            or entry["size"] < 0
            or not isinstance(entry["sha256"], str)
            or not HEX64.fullmatch(entry["sha256"])
        ):
            raise ReleaseVerificationError(f"invalid manifest digest entry: {path!r}")
    for key in ("artifact", "sbom", "wheel"):
        if key not in manifest:
            continue
        value = manifest[key]
        if not isinstance(value, dict) or set(value) != {"name", "size", "sha256"}:
            raise ReleaseVerificationError(f"manifest {key} identity is invalid")
        _check_name(value["name"], f"manifest {key}.name")
        if (
            not isinstance(value["size"], int)
            or value["size"] < 0
            or not isinstance(value["sha256"], str)
            or not HEX64.fullmatch(value["sha256"])
        ):
            raise ReleaseVerificationError(f"manifest {key} digest is invalid")


def _check_checksums(path: Path, expected: dict[str, Path]) -> None:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2 or not HEX64.fullmatch(parts[0]):
            raise ReleaseVerificationError(f"invalid checksum row: {line!r}")
        rows[parts[1]] = parts[0]
    for name, target in expected.items():
        if rows.get(name) != _sha256(target):
            raise ReleaseVerificationError(f"checksum mismatch: {name}")


def _check_archive(artifact: Path, manifest: dict[str, Any]) -> None:
    expected = {entry["path"]: entry for entry in manifest["files"]}
    with zipfile.ZipFile(artifact) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ReleaseVerificationError("archive contains duplicate paths")
        if set(names) != set(expected):
            raise ReleaseVerificationError("archive file set differs from the source manifest")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ReleaseVerificationError(f"unsafe archive member: {info.filename}")
            data = archive.read(info)
            entry = expected[info.filename]
            if len(data) != entry["size"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ReleaseVerificationError(f"archive content mismatch: {info.filename}")
    digest = hashlib.sha256()
    for entry in manifest["files"]:
        digest.update(entry["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(entry["size"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(entry["sha256"].encode("ascii"))
        digest.update(b"\0")
    if digest.hexdigest() != manifest["source_tree_sha256"]:
        raise ReleaseVerificationError("source tree digest does not match manifest entries")


def verify(manifest_path: Path, checksums_path: Path, artifact: Path, sbom: Path) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    _check_manifest(manifest)
    if manifest["artifact"]["name"] != artifact.name or manifest["sbom"]["name"] != sbom.name:
        raise ReleaseVerificationError("manifest filenames do not match supplied files")
    checked = [("artifact", artifact, manifest["artifact"]), ("sbom", sbom, manifest["sbom"])]
    # The wheel is the file `uvx` and `npx` end up running. It is verified from the bundle
    # directory rather than a separate argument so an existing caller gains the check for free —
    # a channel nobody remembered to verify is the same as an unverified channel.
    if "wheel" in manifest:
        wheel = manifest_path.parent / manifest["wheel"]["name"]
        if not wheel.is_file():
            raise ReleaseVerificationError(f"manifest declares a wheel that is not in the bundle: {wheel.name}")
        checked.append(("wheel", wheel, manifest["wheel"]))
    for label, target, metadata in checked:
        if target.stat().st_size != metadata["size"] or _sha256(target) != metadata["sha256"]:
            raise ReleaseVerificationError(f"{label} does not match manifest")
    expected_checksums = {target.name: target for _, target, _ in checked}
    expected_checksums[manifest_path.name] = manifest_path
    _check_checksums(checksums_path, expected_checksums)
    _check_archive(artifact, manifest)
    sbom_document = _load_json(sbom)
    if sbom_document.get("bomFormat") != "CycloneDX" or sbom_document.get("metadata", {}).get("component", {}).get("version") != manifest["version"]:
        raise ReleaseVerificationError("SBOM identity does not match release version")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--checksums", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--sbom", required=True)
    args = parser.parse_args()
    try:
        manifest = verify(*(Path(value).resolve() for value in (args.manifest, args.checksums, args.artifact, args.sbom)))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f"release verification: FAIL ({exc})")
        return 1
    print(f"release verification: PASS (v{manifest['version']}, source {manifest['source_commit']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
