#!/usr/bin/env python3
"""Every tracked `test_*.py` is either in the verification matrix or exempt on the record.

`scripts/run_all_checks.py` is an explicit list, which is what makes it deterministic and
orderable. The cost of an explicit list is that a new test file passes review, passes locally,
and then never runs again because nobody added the line. This check closes that gap: a test that
is not in the matrix has to be named here, with the reason it runs somewhere else.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Tests the matrix deliberately does not run, and where they run instead. A path listed here must
# still exist and must still be absent from the matrix, so a stale exemption is itself a failure.
EXEMPT: dict[str, str] = {
    "scripts/test_release_install.py": (
        "needs an unpacked release bundle (`--bundle`); the release and test workflows build one "
        "and invoke it directly after `run_all_checks.py`"
    ),
}


def _tracked_tests() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", "*test_*.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return sorted(
        line for line in result.stdout.splitlines()
        if line and Path(line).name.startswith("test_")
    )


def _registered_paths() -> set[str]:
    """Read the matrix as data rather than as text, so a reordered list still reads correctly."""
    spec = importlib.util.spec_from_file_location(
        "_run_all_checks", ROOT / "scripts" / "run_all_checks.py"
    )
    if spec is None or spec.loader is None:  # pragma: no cover - packaging accident
        raise RuntimeError("could not load scripts/run_all_checks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {
        argument
        for _label, command in module.CHECKS
        for argument in command
        if isinstance(argument, str) and argument.endswith((".py", ".js"))
    }


def main() -> int:
    registered = _registered_paths()
    problems: list[str] = []

    for path in _tracked_tests():
        if path in registered:
            continue
        if path in EXEMPT:
            continue
        problems.append(
            f"{path} is tracked but not run by scripts/run_all_checks.py; "
            "add it to CHECKS, or add it to EXEMPT in this file with the reason"
        )

    for path, reason in EXEMPT.items():
        if not (ROOT / path).exists():
            problems.append(f"EXEMPT lists {path}, which no longer exists")
        elif path in registered:
            problems.append(f"EXEMPT lists {path}, but the matrix now runs it: {reason}")

    for path in sorted(registered):
        if not (ROOT / path).exists():
            problems.append(f"scripts/run_all_checks.py runs {path}, which does not exist")

    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    print("Every tracked test file is registered in the verification matrix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
