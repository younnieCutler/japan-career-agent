#!/usr/bin/env python3
"""Capture real CLI subprocess evidence for a local E2E run.

This helper records the command boundary only; it does not implement or bypass any career flow.
The log is an artifact for a caller-provided E2E directory, not a Vault ledger.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Sequence


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _redaction_pairs(roots: Iterable[Path]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    temp_root = Path(tempfile.gettempdir()).resolve()
    resolved_roots = {path.expanduser().resolve() for path in roots if str(path)}
    for path in sorted(resolved_roots, key=lambda item: len(str(item)), reverse=True):
        root = str(path)
        token = "<TEMP>" if path == temp_root or temp_root in path.parents else "<HOME>"
        variants = {root, root.replace("\\", "/"), root.replace("/", "\\")}
        pairs.extend((variant, token) for variant in sorted(variants, key=len, reverse=True))
    return pairs


def redact(value: str, roots: Iterable[Path]) -> str:
    result = value
    for source, token in _redaction_pairs(roots):
        result = re.sub(re.escape(source), token, result, flags=re.IGNORECASE if os.name == "nt" else 0)
    return result


def capture(
    argv: Sequence[str | Path],
    *,
    cwd: Path,
    log_path: Path,
    input_bytes: bytes | None = None,
    env: dict[str, str] | None = None,
    redact_roots: Iterable[Path] = (),
) -> subprocess.CompletedProcess[bytes]:
    command = [str(item) for item in argv]
    roots = [Path.home(), Path(tempfile.gettempdir()), *redact_roots]
    started_at = utc_now()
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    if Path(command[0]).name.lower().startswith("python"):
        process_env.setdefault("PYTHONIOENCODING", "utf-8")
    result = subprocess.run(
        command,
        cwd=cwd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=process_env,
        check=False,
    )
    finished_at = utc_now()
    row = {
        "started_at": started_at,
        "finished_at": finished_at,
        "argv": [redact(item, roots) for item in command],
        "cwd": redact(str(cwd), roots),
        "exit_code": result.returncode,
        "stdout": redact(result.stdout.decode("utf-8", errors="strict"), roots),
        "stderr": redact(result.stderr.decode("utf-8", errors="strict"), roots),
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="capture one real CLI subprocess into commands.jsonl")
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("a command is required after --")
    input_bytes = args.input_file.read_bytes() if args.input_file else None
    result = capture(command, cwd=args.cwd, log_path=args.log, input_bytes=input_bytes)
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
