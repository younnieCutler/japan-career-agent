#!/usr/bin/env python3
"""Run the canonical repository matrix with compact, recallable output for coding agents."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_observation_pack import (  # noqa: E402
    DEFAULT_EXCERPT_LINES,
    DEFAULT_STORE,
    ObservationPackError,
    format_compact_receipt,
    run_command,
)

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--excerpt-lines", type=int, default=DEFAULT_EXCERPT_LINES)
    parser.add_argument(
        "--no-pack-success",
        action="store_true",
        help="do not retain the successful full-matrix output; failures are always retained",
    )
    arguments = parser.parse_args()

    try:
        receipt = run_command(
            label="repository verification matrix",
            command=(sys.executable, "scripts/run_all_checks.py"),
            cwd=ROOT,
            store=arguments.store,
            threshold_bytes=0,
            always_pack=not arguments.no_pack_success,
        )
    except ObservationPackError as exc:
        print(f"agent-checks: {exc}", file=sys.stderr)
        return 2

    print(format_compact_receipt(receipt, excerpt_lines=arguments.excerpt_lines))
    return receipt.returncode


if __name__ == "__main__":
    raise SystemExit(main())
