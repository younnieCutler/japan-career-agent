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
        "JAPAN_RECRUIT_NO_UPDATE_CHECK", "24-hour", "CONTRIBUTING.md", "CHANGELOG.md",
        "check_agent_context.py", "check_context_budget.py", "check_manifest_consistency.py",
        "check_readme_consistency.py", "check_release_consistency.py", "test_hook_contract.py",
        "test_self_analysis_profile.py",
        "test_state_durability.py", "test_routing.py", "test_career_agent.py",
        "test_checklist_contract.py", "test_checklist_runtime.js", "mock-interviewer", "1.6.2",
    ),
    "README_ko.md": (
        "JAPAN_RECRUIT_NO_UPDATE_CHECK", "24시간", "CONTRIBUTING.md", "CHANGELOG.md",
        "check_agent_context.py", "check_context_budget.py", "check_manifest_consistency.py",
        "check_readme_consistency.py", "check_release_consistency.py", "test_hook_contract.py",
        "test_self_analysis_profile.py",
        "test_state_durability.py", "test_routing.py", "test_career_agent.py",
        "test_checklist_contract.py", "test_checklist_runtime.js", "mock-interviewer", "1.6.2",
    ),
    "README_ja.md": (
        "JAPAN_RECRUIT_NO_UPDATE_CHECK", "24時間", "CONTRIBUTING.md", "CHANGELOG.md",
        "check_agent_context.py", "check_context_budget.py", "check_manifest_consistency.py",
        "check_readme_consistency.py", "check_release_consistency.py", "test_hook_contract.py",
        "test_self_analysis_profile.py",
        "test_state_durability.py", "test_routing.py", "test_career_agent.py",
        "test_checklist_contract.py", "test_checklist_runtime.js", "mock-interviewer", "1.6.2",
    ),
}
FORBIDDEN = (
    *CANDIDATE_OUTCOME_PERCENTAGE_PATTERNS,
    re.compile(r"(?:Recruit|Persol)\s+(?:algorithm|score|style)", re.I),
)


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
    if errors:
        print("README consistency errors:")
        print("\n".join(errors))
        return 1
    print("README consistency: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
