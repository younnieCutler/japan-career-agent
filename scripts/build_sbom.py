#!/usr/bin/env python3
"""Build a deterministic CycloneDX SBOM from the pinned runtime and dev locks."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from check_dependency_lock import ROOT, LockedPackage, parse_lock


def _component(package: LockedPackage, scope: str) -> dict[str, Any]:
    purl = f"pkg:pypi/{package.name}@{package.version}"
    return {
        "type": "library",
        "bom-ref": purl,
        "name": package.name,
        "version": package.version,
        "purl": purl,
        "scope": scope,
        "hashes": [{"alg": "SHA-256", "content": value} for value in package.hashes],
        "licenses": [{"license": {"id": "MIT"}}],
    }


def _lock_digest(
    runtime: dict[str, LockedPackage], development: dict[str, LockedPackage]
) -> bytes:
    identity = {
        scope: [
            {"name": package.name, "version": package.version, "hashes": list(package.hashes)}
            for package in (packages[name] for name in sorted(packages))
        ]
        for scope, packages in (("runtime", runtime), ("development", development))
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).digest()


def build_document(runtime_lock: Path, development_lock: Path) -> dict[str, Any]:
    runtime = parse_lock(runtime_lock)
    development = parse_lock(development_lock)
    lock_digest = _lock_digest(runtime, development)
    serial = uuid.UUID(bytes=lock_digest[:16])
    components = []
    for name in sorted(development):
        components.append(_component(development[name], "required" if name in runtime else "optional"))
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "japan-career-agent",
                "version": json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"],
            },
            "properties": [
                {
                    "name": "lock.sha256",
                    "value": lock_digest.hex(),
                }
            ],
        },
        "components": components,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-lock", default="requirements.lock")
    parser.add_argument("--development-lock", default="requirements-dev.lock")
    parser.add_argument("--output", default="sbom.cdx.json")
    parser.add_argument("--check", action="store_true", help="fail when output differs from deterministic generation")
    args = parser.parse_args()
    runtime = Path(args.runtime_lock)
    development = Path(args.development_lock)
    output = Path(args.output)
    if not runtime.is_absolute():
        runtime = ROOT / runtime
    if not development.is_absolute():
        development = ROOT / development
    if not output.is_absolute():
        output = ROOT / output
    document = build_document(runtime.resolve(), development.resolve())
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        try:
            current = output.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"SBOM check: FAIL ({exc})")
            return 1
        if current != payload:
            print("SBOM check: FAIL (tracked SBOM is not reproducible from the locks)")
            return 1
        print("SBOM check: PASS")
        return 0
    output.write_text(payload, encoding="utf-8", newline="\n")
    print(f"SBOM written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
