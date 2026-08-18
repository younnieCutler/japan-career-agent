"""Discover the domain Skills this runtime knows about, and what each one requires to run.

This is a read-only view over `skills/*/SKILL.md` plus the execution class table in `models.py`. It
duplicates no metadata SKILL.md already carries -- name and description come from the same
frontmatter parse `routing.skill_context()` uses -- and adds the one fact SKILL.md cannot state
about itself: whether running it needs a host.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from models import SKILL_EXECUTION, CareerError

_DESCRIPTION = re.compile(r"^description:\s*>\s*\n(.*?)(?=^---\s*$)", re.M | re.S)
_NAME = re.compile(r"^name:\s*(\S+)\s*$", re.M)


def _parse_skill_md(path: Path) -> tuple[str | None, str]:
    text = path.read_text(encoding="utf-8")
    name_match = _NAME.search(text)
    description = ""
    description_match = _DESCRIPTION.search(text)
    if description_match:
        description = " ".join(line.strip() for line in description_match.group(1).splitlines()).strip()
    return (name_match.group(1) if name_match else None), description


def discover(skills_root: Path) -> list[dict[str, Any]]:
    """Every `skills/*/SKILL.md` this runtime can see, exhaustively cross-checked against
    `SKILL_EXECUTION`.

    A directory present on disk but missing from `SKILL_EXECUTION` is a build-time contract gap,
    not a runtime one -- it means a Skill shipped without anyone deciding whether it needs a host.
    Raising here, rather than defaulting its execution class, is what keeps that decision from being
    made by omission.
    """
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        skill_path = skill_dir / "SKILL.md"
        if not skill_path.is_file():
            continue
        name, description = _parse_skill_md(skill_path)
        skill_name = name or skill_dir.name
        if skill_name not in SKILL_EXECUTION:
            raise CareerError(
                f"skill '{skill_name}' at {skill_path} has no entry in models.SKILL_EXECUTION"
            )
        seen.add(skill_name)
        entries.append({
            "skill": skill_name,
            "path": str(skill_path),
            "description": description,
            "execution": SKILL_EXECUTION[skill_name],
        })
    missing = sorted(set(SKILL_EXECUTION) - seen)
    if missing:
        raise CareerError(f"SKILL_EXECUTION names skills with no directory: {', '.join(missing)}")
    return entries


def find(skills_root: Path, skill: str) -> dict[str, Any]:
    """One registry entry by name, or a `CareerError` naming what was asked for."""
    for entry in discover(skills_root):
        if entry["skill"] == skill:
            return entry
    raise CareerError(f"unknown skill: {skill}")
