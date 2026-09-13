#!/usr/bin/env python3
"""Run the canonical repository matrix with compact, recallable output for coding agents."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_observation_pack import (  # noqa: E402
    DEFAULT_EXCERPT_LINES,
    DEFAULT_STORE,
    ObservationPackError,
    ObservationReceipt,
    archive_observation,
    format_compact_receipt,
)

ROOT = Path(__file__).resolve().parent.parent
LABEL = "repository verification matrix"
COMMAND = (sys.executable, "scripts/run_all_checks.py")


def _run_canonical(*, store: Path, pack_success: bool) -> ObservationReceipt:
    """Run the canonical matrix first, then persist its observation on a best-effort basis."""
    try:
        result = subprocess.run(
            list(COMMAND),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise ObservationPackError(f"could not start canonical matrix: {exc}") from exc

    stdout = bytes(result.stdout or b"")
    stderr = bytes(result.stderr or b"")
    receipt = ObservationReceipt(
        handle=None,
        label=LABEL,
        command=COMMAND,
        returncode=result.returncode,
        stdout=stdout,
        stderr=stderr,
        path=None,
    )

    if result.returncode == 0 and not pack_success:
        return receipt

    try:
        return archive_observation(
            label=LABEL,
            command=COMMAND,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
            store=store,
        )
    except ObservationPackError as exc:
        # The canonical command has already completed. Persistence is presentation/debugging only
        # and must never replace the command's pass/fail truth with an observation-layer exit code.
        print(f"agent-checks: observation archive failed: {exc}", file=sys.stderr)
        return receipt


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
        receipt = _run_canonical(
            store=arguments.store,
            pack_success=not arguments.no_pack_success,
        )
    except ObservationPackError as exc:
        # No canonical result exists when the command itself could not be started.
        print(f"agent-checks: {exc}", file=sys.stderr)
        return 2

    print(format_compact_receipt(receipt, excerpt_lines=arguments.excerpt_lines))
    return receipt.returncode


if __name__ == "__main__":
    raise SystemExit(main())
