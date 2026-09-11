#!/usr/bin/env python3
"""Validate the transition-administration registry and fail on stale procedural sources."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "_shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from transition_admin import TransitionAdminError, load_registry  # noqa: E402


def check(as_of: dt.date | None = None) -> list[str]:
    today = as_of or dt.date.today()
    registry = load_registry()
    errors: list[str] = []
    for source_id, source in registry["sources"].items():
        review_by = dt.date.fromisoformat(str(source["review_by"]))
        if review_by < today:
            errors.append(f"stale transition source: {source_id} review_by {review_by}")
    return errors


def main() -> int:
    try:
        errors = check()
    except TransitionAdminError as exc:
        print(f"transition admin registry error: {exc}", file=sys.stderr)
        return 2
    if errors:
        print("transition admin errors:", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("transition admin registry: valid and current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
