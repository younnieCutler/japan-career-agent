#!/usr/bin/env python3
"""Check that the three README entry points advertise the canonical contract."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = [ROOT / "README.md", ROOT / "README_ko.md", ROOT / "README_ja.md"]
REQUIRED = ("_shared/decision_philosophy.md", "_shared/schemas.yml", "_shared/career_claims.yml", "Unknown")
FORBIDDEN = (
    re.compile(r"(?:screening|document|offer)\s+(?:passage|pass)\s*[:=]\s*<?\s*\d+\s*%", re.I),
    re.compile(r"(?:Recruit|Persol)\s+(?:algorithm|score|style)", re.I),
    re.compile(r"(?:probability|pass rate|offer rate)\s*[:=]\s*<?\s*\d+\s*%", re.I),
)


def main() -> int:
    errors: list[str] = []
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        for phrase in REQUIRED:
            if phrase not in text:
                errors.append(f"{path.name}: missing {phrase}")
        for pattern in FORBIDDEN:
            if pattern.search(text):
                errors.append(f"{path.name}: forbidden output claim {pattern.pattern}")
    if errors:
        print("README consistency errors:")
        print("\n".join(errors))
        return 1
    print("README consistency: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
