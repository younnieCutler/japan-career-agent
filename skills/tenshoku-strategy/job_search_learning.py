#!/usr/bin/env python3
"""Application-level job-search learning loop.

This command writes only local workspace state. It never submits an application, contacts a company,
or turns a pattern into a standing rule without the user's separate decision.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SHARED_ROOT = Path(__file__).resolve().parent.parent.parent / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))

import application_learning  # noqa: E402


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", help="workspace containing data/ (default: CAREER_WORKSPACE or cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    begin = sub.add_parser("begin", help="begin one application and reset the company projection")
    begin.add_argument("company_slug")
    begin.add_argument("--company-name", required=True)
    begin.add_argument("--position", required=True)
    begin.add_argument("--role-family")
    begin.add_argument("--channel", required=True, choices=sorted(application_learning.CHANNELS))
    begin.add_argument("--opened-at", required=True, help="YYYY-MM-DD")
    begin.add_argument("--stage", required=True, type=int)
    begin.add_argument("--id", dest="application_id")

    observe = sub.add_parser("observe", help="append raw feedback or a candidate self-observation")
    observe.add_argument("application_id")
    observe.add_argument("--kind", required=True, choices=sorted(application_learning.OBSERVATION_KINDS))
    observe.add_argument("--text", required=True)
    observe.add_argument("--observed-at", required=True)
    observe.add_argument("--source-ref", required=True)
    observe.add_argument("--stage", type=int)
    observe.add_argument("--id", dest="observation_id")

    classify = sub.add_parser("classify", help="append a theme proposal or user decision")
    classify.add_argument("application_id")
    classify.add_argument("observation_id")
    classify.add_argument("--theme", required=True)
    classify.add_argument("--state", required=True, choices=sorted(application_learning.CLASSIFICATION_STATES))
    classify.add_argument("--source", required=True, choices=sorted(application_learning.CLASSIFICATION_SOURCES))
    classify.add_argument("--classified-at", required=True)
    classify.add_argument("--id", dest="classification_id")

    close = sub.add_parser("close", help="freeze the application outcome and current matching snapshot")
    close.add_argument("application_id")
    close.add_argument("--reason", required=True)
    close.add_argument("--closed-at", required=True, help="YYYY-MM-DD")
    close.add_argument("--reached-stage", type=int)

    report = sub.add_parser("report", help="show repeated evidence patterns without inferring causes")
    report.add_argument("--json", action="store_true", dest="as_json")

    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    workspace = args.workspace
    try:
        if args.command == "begin":
            value = application_learning.begin_application(
                workspace=workspace,
                company_slug=args.company_slug,
                company_name=args.company_name,
                position_title=args.position,
                role_family=args.role_family,
                channel=args.channel,
                opened_at=args.opened_at,
                stage=args.stage,
                application_id=args.application_id,
            )
            _print(value)
            return 0
        if args.command == "observe":
            value = application_learning.add_observation(
                workspace=workspace,
                application_id=args.application_id,
                kind=args.kind,
                text=args.text,
                observed_at=args.observed_at,
                source_ref=args.source_ref,
                stage=args.stage,
                observation_id=args.observation_id,
            )
            _print(value)
            return 0
        if args.command == "classify":
            value = application_learning.classify_observation(
                workspace=workspace,
                application_id=args.application_id,
                observation_id=args.observation_id,
                theme=args.theme,
                state=args.state,
                source=args.source,
                classified_at=args.classified_at,
                classification_id=args.classification_id,
            )
            _print(value)
            return 0
        if args.command == "close":
            value = application_learning.close_application(
                workspace=workspace,
                application_id=args.application_id,
                closed_reason=args.reason,
                closed_at=args.closed_at,
                reached_stage=args.reached_stage,
            )
            _print(value)
            return 0

        data = application_learning.load_store(application_learning.applications_path(workspace))
        result = application_learning.analyze(data)
        if args.as_json:
            _print(result)
        else:
            print(application_learning.render_report(result))
        return 0
    except (ValueError, ImportError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
