#!/usr/bin/env python3
"""Verify that the compact AGENTS index points to existing lazy references."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
PATTERN = re.compile(r"`(_shared/agent_context/[A-Za-z0-9_.\-/]+\.md)`")


def main() -> int:
    text = AGENTS.read_text(encoding="utf-8")
    paths = sorted(set(PATTERN.findall(text)))
    missing = [path for path in paths if not (ROOT / path).is_file()]
    if missing:
        print("missing AGENTS lazy references:")
        print("\n".join(f"- {path}" for path in missing))
        return 1
    if len(paths) < 6:
        print(f"expected at least 6 lazy references, found {len(paths)}")
        return 1
    print(f"AGENTS context references: {len(paths)} resolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
