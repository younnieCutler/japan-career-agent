#!/usr/bin/env python3
"""Check that the three README entry points advertise the canonical contract."""

from __future__ import annotations

import re
from pathlib import Path

from policy_patterns import CANDIDATE_OUTCOME_PERCENTAGE_PATTERNS

ROOT = Path(__file__).resolve().parent.parent
FILES = [ROOT / "README.md", ROOT / "README_ko.md", ROOT / "README_ja.md"]
REQUIRED = ("_shared/decision_philosophy.md", "_shared/schemas.yml", "_shared/career_claims.yml", "Unknown")
REQUIRED_BY_FILE = {
    "README.md": (
        "JAPAN_CAREER_NO_UPDATE_CHECK", "24-hour", "CONTRIBUTING.md", "CHANGELOG.md",
        "run_all_checks.py", "mock-interviewer", "1.6.2", "1.6.3", "check_version_bump.py",
    ),
    "README_ko.md": (
        "JAPAN_CAREER_NO_UPDATE_CHECK", "24시간", "CONTRIBUTING.md", "CHANGELOG.md",
        "run_all_checks.py", "mock-interviewer", "1.6.2", "1.6.3", "check_version_bump.py",
    ),
    "README_ja.md": (
        "JAPAN_CAREER_NO_UPDATE_CHECK", "24時間", "CONTRIBUTING.md", "CHANGELOG.md",
        "run_all_checks.py", "mock-interviewer", "1.6.2", "1.6.3", "check_version_bump.py",
    ),
}
FORBIDDEN = (
    *CANDIDATE_OUTCOME_PERCENTAGE_PATTERNS,
    re.compile(r"(?:Recruit|Persol)\s+(?:algorithm|score|style)", re.I),
)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
IN_PAGE_LINK = re.compile(r'href="#([^"]+)"')


def _anchor(heading: str) -> str:
    """GitHub's heading anchor: lowercased, punctuation dropped, spaces hyphenated.

    `\\w` under Unicode keeps Hangul and kana, which the navigation rows in README_ko and
    README_ja depend on.
    """
    text = re.sub(r"[^\w\s-]", "", heading.strip().lower(), flags=re.UNICODE)
    return re.sub(r"\s+", "-", text)


def main() -> int:
    errors: list[str] = []
    for path in FILES:
        text = path.read_text(encoding="utf-8")
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
    if errors:
        print("README consistency errors:")
        print("\n".join(errors))
        return 1
    print("README consistency: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
