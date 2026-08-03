#!/usr/bin/env python3
"""Deterministic writer for the suite-wide data/pipeline.yml company store.

Examples:
  python3 scripts/pipeline.py upsert gao --json '{"name":"GAO","stage":2}'
    python3 scripts/pipeline.py update gao --json '{"decision_status":"review","match_model_version":"evidence_based_v3"}'
  python3 scripts/pipeline.py history gao --event '企業研究を完了'
  python3 scripts/pipeline.py close gao --reason '内定辞退'
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

_SHARED_ROOT = Path(__file__).resolve().parent.parent / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))
import pipeline_store  # noqa: E402


def json_object(raw: str) -> dict:
    try:
        value = json.loads(sys.stdin.read() if raw == "-" else raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("--json must contain an object")
    return value


def path_arg(raw: str) -> Path:
    return Path(raw).expanduser()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="data/pipeline.yml", help="pipeline file (default: data/pipeline.yml)")
    sub = parser.add_subparsers(dest="command", required=True)

    for command in ("upsert", "update"):
        item = sub.add_parser(command)
        item.add_argument("slug")
        item.add_argument("--json", required=True, dest="payload")
        item.add_argument("--history", help="append one history event after the update")

    history = sub.add_parser("history")
    history.add_argument("slug")
    history.add_argument("--event", required=True)
    history.add_argument("--date", default=dt.date.today().isoformat())

    close = sub.add_parser("close")
    close.add_argument("slug")
    close.add_argument("--reason", required=True)
    close.add_argument("--reached-stage", type=int)
    close.add_argument("--event", help="history event; defaults to closed_reason")

    args = parser.parse_args(argv)
    path = path_arg(args.path)
    history_item = None
    if args.command in {"upsert", "update"} and args.history:
        history_item = {"date": dt.date.today().isoformat(), "event": args.history}

    try:
        if args.command == "upsert":
            result = pipeline_store.upsert_company(path, args.slug, json_object(args.payload), history=history_item)
        elif args.command == "update":
            result = pipeline_store.update_company(path, args.slug, json_object(args.payload), history=history_item)
        elif args.command == "history":
            result = pipeline_store.append_history(path, args.slug, args.event, date=args.date)
        else:
            if args.reached_stage is not None and not 0 <= args.reached_stage <= 7:
                raise ValueError("reached-stage must be an integer from 0 to 7")
            fields = {"closed": True, "closed_reason": args.reason}
            if args.reached_stage is not None:
                fields["reached_stage"] = args.reached_stage
            result = pipeline_store.update_company(
                path,
                args.slug,
                fields,
                history={"date": dt.date.today().isoformat(), "event": args.event or args.reason},
            )
    except (ValueError, ImportError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    company = next(item for item in result.get("companies", []) if item.get("slug") == args.slug)
    print(f"{args.command}: {args.slug} (stage={company.get('stage')}, closed={company.get('closed', False)})")
    print(path.resolve())
    if not path.is_file():
        print(f"write failed: {path.resolve()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
