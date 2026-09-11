#!/usr/bin/env python3
"""Project a Japan job-transition scenario into source-backed administrative tasks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "_shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from transition_admin import TransitionAdminError, project, render_text  # noqa: E402


def _load_scenario(path: str) -> dict:
    if path == "-":
        text = sys.stdin.read()
        suffix = ".json"
    else:
        source = Path(path)
        text = source.read_text(encoding="utf-8")
        suffix = source.suffix.lower()
    try:
        if suffix == ".json":
            payload = json.loads(text)
        else:
            payload = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise TransitionAdminError(f"cannot parse scenario: {exc}") from exc
    if not isinstance(payload, dict):
        raise TransitionAdminError("scenario must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", help="JSON/YAML scenario path, or - for JSON stdin")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    try:
        results = project(_load_scenario(args.scenario))
    except (OSError, TransitionAdminError) as exc:
        print(f"transition admin error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(render_text(results), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
