#!/usr/bin/env python3
"""Keep Claude/Codex/plugin marketplace metadata on the same version and identity."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = {
    "claude": ROOT / ".claude-plugin" / "plugin.json",
    "codex": ROOT / ".codex-plugin" / "plugin.json",
}
COMMON_FIELDS = ("description", "homepage", "repository", "license", "keywords")


def main() -> int:
    docs = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in MANIFESTS.items()
    }
    claude = docs["claude"]
    codex = docs["codex"]
    if "hooks" in claude:
        raise SystemExit("Claude manifest must not redeclare standard hooks/hooks.json")
    if claude.get("name") != codex.get("name"):
        raise SystemExit("manifest name mismatch")
    if claude.get("version") != codex.get("version"):
        raise SystemExit("manifest version mismatch")
    for field in COMMON_FIELDS:
        claude_value = claude.get(field)
        codex_value = codex.get(field)
        if claude_value is None or codex_value is None:
            raise SystemExit(f"manifest missing common field: {field}")
        if claude_value != codex_value:
            raise SystemExit(f"manifest {field} mismatch")
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    item = next((entry for entry in marketplace.get("plugins", [])
                 if entry.get("name") == claude.get("name")), None)
    if item is None:
        raise SystemExit("marketplace plugin name mismatch")
    print(f"manifest consistency: {claude['name']} v{claude['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
