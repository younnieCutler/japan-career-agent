#!/usr/bin/env python3
"""Verify every `references/*.md` and `_shared/*` path mentioned in a SKILL.md actually exists.

Catches typos and stale links (a doc renamed or deleted, a reference never updated) before a
real session hits them. Does not attempt to resolve bare filenames or cross-skill paths like
`career-agent/references/...` — only the two common, unambiguous forms.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"`((?:\.\./\.\./)?(?:references|_shared)/[A-Za-z0-9_.\-/]+\.(?:md|yml|py))`")


def check_skill(skill_md: Path) -> list[str]:
    skill_dir = skill_md.parent
    text = skill_md.read_text(encoding="utf-8")
    missing = []
    for match in PATTERN.finditer(text):
        raw = match.group(1)
        target = ROOT / raw if raw.startswith("_shared/") else (skill_dir / raw).resolve()
        if not target.exists():
            missing.append(raw)
    return sorted(set(missing))


def main() -> int:
    skill_files = sorted(ROOT.glob("skills/*/SKILL.md"))
    problems = {}
    for skill_md in skill_files:
        missing = check_skill(skill_md)
        if missing:
            problems[str(skill_md.relative_to(ROOT))] = missing
    if problems:
        for path, missing in problems.items():
            print(f"{path}: missing referenced file(s):")
            for item in missing:
                print(f"  - {item}")
        return 1
    print(f"OK: all reference paths resolved across {len(skill_files)} SKILL.md files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
