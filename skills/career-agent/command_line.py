#!/usr/bin/env python3
"""CLI execution boundary: parser compatibility, output projection, and process exit behavior.

The argument contract lives in ``cli_parser.py``. This module intentionally re-exports
``build_parser`` and ``_default_output_format`` so existing callers keep the same public surface,
while execution and output remain owned here.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Iterable, Mapping

from cli_parser import _default_output_format, build_parser
from dispatch import run_command
from guided import render_human as render_guided_human
from localization import normalize_language
from models import CareerError
from routing import language_for
from ux import attach as project_ux, error_payload, render_human
from vault import CareerVault


def _output_language(
    args: argparse.Namespace,
    result: Mapping[str, Any] | None = None,
    home: CareerVault | None = None,
) -> str:
    """Choose human-output language without changing the machine contract."""
    if args.command == "run" and args.mode == "chat":
        message = args.message or ""
        return normalize_language((result or {}).get("language") or language_for(message))
    if args.command == "guided" and args.message:
        return language_for(args.message)
    # The GUI can fail before a Vault/profile is available. Its explicit launch locale must still
    # determine the recovery message instead of silently falling back to Korean.
    if args.command == "ui" and args.language:
        return normalize_language(args.language)
    if args.command == "setup" and args.language:
        return normalize_language(args.language)
    if result and isinstance(result.get("profile"), dict) and result["profile"].get("language"):
        return normalize_language(result["profile"].get("language"))
    if home is not None:
        try:
            return normalize_language(home.load_profile().get("language"))
        except (CareerError, OSError, ValueError):
            pass
    return normalize_language(None)


def _emit(args: argparse.Namespace, context: dict[str, Any]) -> int:
    """Project one result and write it out. Every successful command leaves through here."""
    result = project_ux(
        args.command,
        context["result"],
        args=vars(args),
        language=_output_language(args, context["result"], context.get("output_home")),
    )
    context["result"] = result
    if args.output_format == "human":
        # `guided` is the one command whose human form is a menu rather than a report, so it has
        # its own renderer. The machine JSON is identical in shape to every other command's.
        print(render_guided_human(result) if args.command == "guided" else render_human(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    # Only the commands that answer a yes/no question report it as an exit status. A `doctor` that
    # finds problems, or a `status` with pending proposals, succeeded at reporting: exiting non-zero
    # there would tell a script the command failed when it did exactly what it was asked to do.
    if context.get("ok_is_exit_status") and not result.get("ok", True):
        return 2
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    quickstart = not raw_argv
    args = parser.parse_args(raw_argv or ["ui"])
    if quickstart:
        args._quickstart = True
    context: dict[str, Any] = {}
    try:
        context["result"] = run_command(args, context)
        return _emit(args, context)
    except CareerError as exc:
        result = error_payload(
            exc,
            language=_output_language(args, context.get("result"), context.get("home")),
        )
        if getattr(args, "output_format", "json") == "human":
            print(render_human(result), file=sys.stderr)
        else:
            print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        return 2
