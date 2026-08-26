#!/usr/bin/env python3
"""Hold the documentation to the facts the code already decides.

Only mechanically derivable things are checked here: a version, a supported interpreter, a count, a
list of names, a path that must resolve. Whether the prose is *good* is not this script's business
and is not checkable this way.

Each rule exists because the corresponding claim had already gone stale, or was one edit away from
it: the runbook advertised a check count from twenty checks ago, the skill table was missing a
shipped Skill, and README.md declared in its own header comment that its outbound links were
absolute while eight of them were not.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
READMES = (ROOT / "README.md", ROOT / "README_ko.md", ROOT / "README_ja.md")
DOCS = ROOT / "docs"
# The three language hubs. Every other file under docs/ has to be reachable from one of them.
HUBS = (DOCS / "README.md", DOCS / "README_ko.md", DOCS / "README_ja.md")
RUNBOOK = DOCS / "MAINTAINER_RUNBOOK.md"
ORCHESTRATION = ROOT / "_shared" / "agent_context" / "orchestration.md"
NPM_README = ROOT / "packaging" / "npm" / "README.md"

PYPROJECT_REQUIRES = re.compile(r"^requires-python = \">=([\d.]+)\"", re.MULTILINE)
PYPROJECT_CLASSIFIER = re.compile(r"^\s*\"Programming Language :: Python :: ([\d.]+)\",", re.MULTILINE)
PYTHON_BADGE = re.compile(r"img\.shields\.io/badge/python-([^\"?]+)")
MINOR_VERSION = re.compile(r"3\.\d+")
CHECK_COUNT = re.compile(r"All (\d+) repository checks passed")
GATE_D_ROOTS = re.compile(
    r"Gate D currently accepts only these Domain roots:\s*(.+?);", re.DOTALL
)
BACKTICKED = re.compile(r"`([^`]+)`")
FENCED_BLOCK = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HTML_HREF = re.compile(r'href="([^"]+)"')


def _body(path: Path) -> str:
    """File text with fenced code blocks removed, so shell samples are not read as links."""
    return FENCED_BLOCK.sub("", path.read_text(encoding="utf-8"))


def _links(text: str) -> list[str]:
    return [*MD_LINK.findall(text), *HTML_HREF.findall(text)]


def _is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "#"))


def _plan_policy_roots() -> set[str]:
    """The Gate D root Skills, from the module that decides them."""
    sys.path.insert(0, str(ROOT / "skills" / "career-agent"))
    from execution_plans import _PLAN_POLICIES  # noqa: PLC0415 -- needs the sys.path insert above

    return set(_PLAN_POLICIES)


def _registered_check_count() -> int:
    """len(CHECKS) without running the matrix; the module guards its own entry point."""
    spec = importlib.util.spec_from_file_location(
        "_run_all_checks", ROOT / "scripts" / "run_all_checks.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return len(module.CHECKS)


def check_python_versions() -> list[str]:
    """The interpreters the READMEs advertise are the ones pyproject actually declares."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requires = PYPROJECT_REQUIRES.search(pyproject)
    if requires is None:
        return ["pyproject.toml: missing requires-python"]
    minimum = requires.group(1)
    classifiers = set(PYPROJECT_CLASSIFIER.findall(pyproject))
    if not classifiers:
        return ["pyproject.toml: no Python classifiers"]

    errors: list[str] = []
    for path in READMES:
        text = path.read_text(encoding="utf-8")
        badge = PYTHON_BADGE.search(text)
        if badge is None:
            errors.append(f"{path.name}: no Python version badge")
        else:
            advertised = set(MINOR_VERSION.findall(badge.group(1)))
            if advertised != classifiers:
                errors.append(
                    f"{path.name}: badge advertises {sorted(advertised)}, "
                    f"pyproject classifies {sorted(classifiers)}"
                )
        if f"Python {minimum}" not in text:
            errors.append(f"{path.name}: prose does not state the minimum Python {minimum}")
    if f"Python {minimum}" not in NPM_README.read_text(encoding="utf-8"):
        errors.append(f"{NPM_README.relative_to(ROOT)}: does not state the minimum Python {minimum}")
    return errors


def _skill_table(text: str) -> str | None:
    """The rows of the one Markdown table whose last column is headed `Skill`.

    Scoped deliberately: searching the whole file would pass as long as a Skill is named anywhere,
    so a row deleted from the table would still look present because the prose mentions it.
    Matching the header rather than a translated section title keeps this working in all three
    languages.
    """
    rows: list[str] = []
    collecting = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.rstrip("| ").endswith("Skill"):
            collecting = True
            continue
        if collecting:
            if not stripped.startswith("|"):
                break
            rows.append(stripped)
    return "\n".join(rows) if rows else None


def check_skill_coverage() -> list[str]:
    """Every shipped Skill appears in every README's skill table.

    Counting them in prose would only move the staleness; naming all of them is checkable.
    """
    skills = {path.parent.name for path in ROOT.glob("skills/*/SKILL.md")}
    errors: list[str] = []
    for path in READMES:
        table = _skill_table(path.read_text(encoding="utf-8"))
        if table is None:
            errors.append(f"{path.name}: no table with a `Skill` column")
            continue
        missing = sorted(skill for skill in skills if f"`{skill}`" not in table)
        if missing:
            errors.append(f"{path.name}: skill table does not name {', '.join(missing)}")
    return errors


def check_gate_d_roots() -> list[str]:
    """The Gate D root Skills named in the orchestration context match the policy table."""
    supported = _plan_policy_roots()
    match = GATE_D_ROOTS.search(ORCHESTRATION.read_text(encoding="utf-8"))
    if match is None:
        return [f"{ORCHESTRATION.relative_to(ROOT)}: no Gate D root Skill sentence"]
    documented = set(BACKTICKED.findall(match.group(1)))
    if documented != supported:
        return [
            f"{ORCHESTRATION.relative_to(ROOT)}: documents {sorted(documented)}, "
            f"execution_plans supports {sorted(supported)}"
        ]
    return []


def check_check_count() -> list[str]:
    """The runbook's expected output matches the matrix it tells you to run."""
    registered = _registered_check_count()
    match = CHECK_COUNT.search(RUNBOOK.read_text(encoding="utf-8"))
    if match is None:
        return [f"{RUNBOOK.relative_to(ROOT)}: does not state the expected check count"]
    if int(match.group(1)) != registered:
        return [
            f"{RUNBOOK.relative_to(ROOT)}: expects {match.group(1)} checks, "
            f"run_all_checks.py registers {registered}"
        ]
    return []


def check_relative_links() -> list[str]:
    """Relative links resolve, and README.md has none.

    README.md is the PyPI long description. PyPI resolves a relative link against nothing, so a
    working GitHub link there is a dead link for everyone who arrives from `pip show`.
    """
    errors: list[str] = []
    for path in (*READMES, *sorted(DOCS.glob("*.md"))):
        for target in _links(_body(path)):
            if _is_external(target):
                continue
            if path == ROOT / "README.md":
                errors.append(f"README.md: relative link {target!r} breaks on PyPI; use a full URL")
                continue
            if not (path.parent / target.split("#", 1)[0]).exists():
                errors.append(f"{path.relative_to(ROOT)}: link {target!r} resolves to nothing")
    return errors


def check_hub_coverage() -> list[str]:
    """Every docs page is reachable from a language hub.

    Eleven of them were reachable from nothing before the hub existed.
    """
    linked: set[str] = set()
    for hub in HUBS:
        for target in _links(_body(hub)):
            if not _is_external(target):
                linked.add(target.split("#", 1)[0])
    orphans = sorted(
        path.name
        for path in DOCS.iterdir()
        if path.is_file() and path not in HUBS and path.name not in linked
    )
    if orphans:
        return [f"docs/: not linked from any hub: {', '.join(orphans)}"]
    return []


CHECKS = (
    check_python_versions,
    check_skill_coverage,
    check_gate_d_roots,
    check_check_count,
    check_relative_links,
    check_hub_coverage,
)


def main() -> int:
    errors: list[str] = []
    for check in CHECKS:
        errors.extend(check())
    if errors:
        print("documentation drift:")
        print("\n".join(errors))
        return 1
    print(f"docs drift: clean ({len(CHECKS)} rules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
