#!/usr/bin/env python3
"""Keep Claude/Codex/plugin marketplace metadata on the same version and identity."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = [ROOT / ".claude-plugin" / "plugin.json", ROOT / ".codex-plugin" / "plugin.json"]


def main() -> int:
    docs = [json.loads(path.read_text(encoding="utf-8")) for path in FILES]
    if len({doc.get("name") for doc in docs}) != 1:
        raise SystemExit("manifest name mismatch")
    if len({doc.get("version") for doc in docs}) != 1:
        raise SystemExit("manifest version mismatch")
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    item = marketplace["plugins"][0]
    if item.get("name") != docs[0].get("name"):
        raise SystemExit("marketplace plugin name mismatch")
    print(f"manifest consistency: {docs[0]['name']} v{docs[0]['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
