#!/usr/bin/env python3
"""Check that the three README entry points advertise the canonical contract."""

from __future__ import annotations

import re
from pathlib import Path

from policy_patterns import CANDIDATE_OUTCOME_PERCENTAGE_PATTERNS

ROOT = Path(__file__).resolve().parent.parent
FILES = [ROOT / "README.md", ROOT / "README_ko.md", ROOT / "README_ja.md"]
# The README is the landing page; the contract documents it used to name inline now live one click
# away, so the markers that guarantee they are still reachable follow them to the hub.
HUBS = [ROOT / "docs" / "README.md", ROOT / "docs" / "README_ko.md", ROOT / "docs" / "README_ja.md"]
HUB_REQUIRED = (
    "_shared/decision_philosophy.md", "_shared/schemas.yml", "_shared/career_claims.yml",
    "run_all_checks.py", "check_version_bump.py",
)
REQUIRED = ("Unknown",)
REQUIRED_BY_FILE = {
    "README.md": (
        "JAPAN_CAREER_NO_UPDATE_CHECK", "24-hour", "CONTRIBUTING.md", "CHANGELOG.md",
        "mock-interviewer", "docs/README.md",
    ),
    "README_ko.md": (
        "JAPAN_CAREER_NO_UPDATE_CHECK", "24시간", "CONTRIBUTING.md", "CHANGELOG.md",
        "mock-interviewer", "docs/README_ko.md",
    ),
    "README_ja.md": (
        "JAPAN_CAREER_NO_UPDATE_CHECK", "24時間", "CONTRIBUTING.md", "CHANGELOG.md",
        "mock-interviewer", "docs/README_ja.md",
    ),
}
FORBIDDEN = (
    *CANDIDATE_OUTCOME_PERCENTAGE_PATTERNS,
    re.compile(r"(?:Recruit|Persol)\s+(?:algorithm|score|style)", re.I),
)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
HEADING_LEVEL = re.compile(r"^(#{2,6})\s+\S", re.MULTILINE)
IN_PAGE_LINK = re.compile(r'href="#([^"]+)"')

# The landing-page path is deliberately thin: run the product first, then keep it installed or add
# a host only if that is useful. Advanced setup/guided/ui commands remain documented below, but the
# README may not force a setup subcommand back into the first-run path.
GLOBAL_NPM_PAIR = re.compile(
    r"npm install -g japan-career-agent\s*\njapan-career-agent"
)
INSTALL_ORDER = (
    "npm install -g japan-career-agent",
    "npx japan-career-agent",
    "uvx japan-career-agent",
    "uv tool install japan-career-agent",
    "pipx install japan-career-agent",
    "claude plugin install japan-career-agent@japan-career-agent",
    "codex plugin add japan-career-agent@japan-career-agent",
)
# `init` was the documented first command through 2.1.x. It still exists, but is not the product's
# first-run path.
FIRST_RUN_IS_INIT = re.compile(r"(?:npx|uvx|pipx run) japan-career-agent init")


def _anchor(heading: str) -> str:
    """GitHub's heading anchor: lowercased, punctuation dropped, spaces hyphenated.

    `\\w` under Unicode keeps Hangul and kana, which the navigation rows in README_ko and
    README_ja depend on.
    """
    text = re.sub(r"[^\w\s-]", "", heading.strip().lower(), flags=re.UNICODE)
    return re.sub(r"\s+", "-", text)


def main() -> int:
    errors: list[str] = []
    structures: dict[str, list[str]] = {}
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        structures[path.name] = HEADING_LEVEL.findall(text)

        if FIRST_RUN_IS_INIT.search(text):
            errors.append(f"{path.name}: the first command shown is `init`; the first run is zero-argument")
        if not GLOBAL_NPM_PAIR.search(text):
            errors.append(
                f"{path.name}: quick start must show `npm install -g japan-career-agent` "
                "followed by `japan-career-agent`"
            )
        position = -1
        for command in INSTALL_ORDER:
            found = text.find(command)
            if found < 0:
                errors.append(f"{path.name}: install section does not show `{command}`")
            elif found < position:
                errors.append(f"{path.name}: `{command}` appears before the step it should follow")
            else:
                position = found

        for phrase in REQUIRED:
            if phrase not in text:
                errors.append(f"{path.name}: missing {phrase}")
        for phrase in REQUIRED_BY_FILE[path.name]:
            if phrase not in text:
                errors.append(f"{path.name}: missing contract marker {phrase}")
        for pattern in FORBIDDEN:
            if pattern.search(text):
                errors.append(f"{path.name}: forbidden output claim {pattern.pattern}")
        # The navigation row is the first thing a reader clicks, and a heading rename silently
        # turns it into a link to the top of the page.
        anchors = {_anchor(heading) for heading in HEADING.findall(text)}
        for target in IN_PAGE_LINK.findall(text):
            if target not in anchors:
                errors.append(f"{path.name}: navigation link #{target} matches no heading")

    for hub in HUBS:
        hub_text = hub.read_text(encoding="utf-8")
        for phrase in HUB_REQUIRED:
            if phrase not in hub_text:
                errors.append(f"docs/{hub.name}: missing contract marker {phrase}")

    # A section added to one language and not the others is the failure mode this catches: the
    # headings differ by translation, but the shape must not. Comparing the level sequence is what
    # can be compared across three languages without hard-coding any of their words.
    reference, *rest = FILES
    for path in rest:
        if structures[path.name] != structures[reference.name]:
            errors.append(
                f"{path.name}: heading structure differs from {reference.name} "
                f"({len(structures[path.name])} headings vs {len(structures[reference.name])}); "
                f"{''.join(structures[path.name])} vs {''.join(structures[reference.name])}"
            )

    if errors:
        print("README consistency errors:")
        print("\n".join(errors))
        return 1
    print("README consistency: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())