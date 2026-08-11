#!/usr/bin/env python3
"""Hold the capability matrix to the parser.

A capability table is only worth reading if a `core` claim means a command exists. This walks the
`core` rows in docs/CAPABILITY_MATRIX.md, pulls the command names out of the Command column, and
checks each one against the subcommands `build_parser()` actually defines. A row that promises a
deterministic path the CLI does not have fails the build, and so does a command that quietly
disappears from the parser while the table still advertises it.

It does not check `host-enhanced` or `host-only` rows: those describe host behaviour this repository
cannot execute, and asserting them here would be the same overclaiming the table exists to prevent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATRIX = ROOT / "docs" / "CAPABILITY_MATRIX.md"
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

CLASSES = {"core", "host-enhanced", "host-only", "not-supported"}
ROW = re.compile(r"^\|(?P<capability>[^|]+)\|(?P<klass>[^|]+)\|(?P<commands>[^|]+)\|")


def parser_commands() -> set[str]:
    from command_line import build_parser  # noqa: PLC0415 -- needs the sys.path insert above

    actions = [
        action for action in build_parser()._subparsers._group_actions  # noqa: SLF001
        if hasattr(action, "choices")
    ]
    return {name for action in actions for name in action.choices}


def rows(text: str) -> list[tuple[str, str, str]]:
    found = []
    for line in text.splitlines():
        match = ROW.match(line.strip())
        if not match:
            continue
        klass = match.group("klass").strip().strip("`")
        if klass in CLASSES:
            found.append((
                match.group("capability").strip(),
                klass,
                match.group("commands").strip(),
            ))
    return found


def main() -> int:
    text = MATRIX.read_text(encoding="utf-8")
    entries = rows(text)
    if not entries:
        print(f"capability matrix: no classified rows found in {MATRIX.name}", file=sys.stderr)
        return 1

    available = parser_commands()
    errors: list[str] = []
    core = 0
    for capability, klass, commands in entries:
        if klass != "core":
            continue
        core += 1
        named = re.findall(r"`([a-z][a-z-]*)`", commands)
        if not named:
            errors.append(f"core row {capability!r} names no command")
            continue
        missing = sorted(set(named) - available)
        if missing:
            errors.append(f"core row {capability!r} names commands the parser does not define: {', '.join(missing)}")

    if errors:
        print("capability matrix errors:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"capability matrix: {core} core rows backed by the parser, {len(entries)} classified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
