#!/usr/bin/env python3
"""Static guard against reintroducing retired outcome claims into active content."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from policy_patterns import CANDIDATE_OUTCOME_PERCENTAGE_PATTERNS

ROOT = Path(__file__).resolve().parent.parent
ACTIVE_ROOTS = (ROOT / "skills", ROOT / "_shared", ROOT / "scripts", ROOT)
ALLOW_FILES = {
    ROOT / "_shared" / "legacy_experimental.py",
    ROOT / "skills" / "matching-simulator" / "references" / "legacy-v1.md",
    ROOT / "scripts" / "check_policy.py",
}
SKIP_PARTS = {"__pycache__", ".git", ".pytest_cache", "data", "career-docs"}

# These are output-shaped claims, not ordinary discussion of the policy. Historical examples
# remain isolated in the two explicit legacy files above.
FORBIDDEN = (
    *CANDIDATE_OUTCOME_PERCENTAGE_PATTERNS,
    re.compile(r"Recruit-style|Persol-style", re.I),
    re.compile(r"reverse-engineer(?:s|ed|ing)?\s+(?:the\s+)?internal\s+matching", re.I),
    re.compile(r"(?:×|x|\*)\s*0\.2\s*(?:weight|multiplier)?", re.I),
)


def files() -> list[Path]:
    extensions = {".md", ".py", ".yml", ".yaml", ".json", ".toml", ".html"}
    result = []
    for root in ACTIVE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in extensions:
                continue
            if any(part in SKIP_PARTS for part in path.parts) or path in ALLOW_FILES:
                continue
            # Tests deliberately contain forbidden user prompts; they are tested separately.
            if "tests" in path.parts or path.name.startswith("test_"):
                continue
            result.append(path)
    return sorted(set(result))


def scan() -> list[str]:
    hits = []
    for path in files():
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for pattern in FORBIDDEN:
                if pattern.search(line):
                    hits.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    return hits


def main() -> int:
    hits = scan()
    if hits:
        print("forbidden active policy output:")
        print("\n".join(hits))
        return 1
    print("policy scan: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
