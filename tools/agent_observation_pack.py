#!/usr/bin/env python3
"""Pack large or failed agent-facing command output without losing the original evidence.

The archive is local-only under ``.agent-observations/``. Each observation is content-addressed by
its label, command, exit code, stdout, and stderr. The compact receipt shown to an agent is
deliberately not a semantic summary: failure excerpts are exact lines from the archived stream,
and the full raw bytes remain recallable by handle.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STORE = ROOT / ".agent-observations"
SCHEMA_VERSION = 1
HANDLE_HEX_LENGTH = 24
HANDLE_RE = re.compile(rf"^obs-[0-9a-f]{{{HANDLE_HEX_LENGTH}}}$")
DEFAULT_EXCERPT_LINES = 16
DEFAULT_PACK_THRESHOLD_BYTES = 8 * 1024


class ObservationPackError(RuntimeError):
    """Raised when an observation cannot be stored or verified safely."""


@dataclass(frozen=True)
class ObservationReceipt:
    handle: str | None
    label: str
    command: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes
    path: Path | None

    @property
    def total_bytes(self) -> int:
        return len(self.stdout) + len(self.stderr)

    @property
    def preferred_stream(self) -> str:
        return "stderr" if self.stderr else "stdout"


def _framed_digest(parts: Sequence[bytes]) -> str:
    """Hash length-framed bytes so concatenation cannot create ambiguous identities."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


def _handle(label: str, command: Sequence[str], returncode: int, stdout: bytes, stderr: bytes) -> str:
    command_bytes = [argument.encode("utf-8") for argument in command]
    identity = _framed_digest(
        [
            b"agent-observation-pack-v1",
            label.encode("utf-8"),
            *command_bytes,
            str(returncode).encode("ascii"),
            stdout,
            stderr,
        ]
    )
    return f"obs-{identity[:HANDLE_HEX_LENGTH]}"


def _line_count(data: bytes) -> int:
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(
    *, label: str, command: Sequence[str], returncode: int, stdout: bytes, stderr: bytes
) -> dict[str, object]:
    handle = _handle(label, command, returncode, stdout, stderr)
    return {
        "version": SCHEMA_VERSION,
        "handle": handle,
        "label": label,
        "command": list(command),
        "returncode": returncode,
        "stdout_b64": base64.b64encode(stdout).decode("ascii"),
        "stderr_b64": base64.b64encode(stderr).decode("ascii"),
        "stdout_sha256": _sha256(stdout),
        "stderr_sha256": _sha256(stderr),
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
        "stdout_lines": _line_count(stdout),
        "stderr_lines": _line_count(stderr),
    }


def _safe_chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass


def archive_observation(
    *,
    label: str,
    command: Sequence[str],
    returncode: int,
    stdout: bytes,
    stderr: bytes,
    store: Path = DEFAULT_STORE,
) -> ObservationReceipt:
    """Persist one exact observation atomically and return its content-addressed receipt."""
    normalized_command = tuple(str(argument) for argument in command)
    record = _record(
        label=label,
        command=normalized_command,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
    handle = str(record["handle"])
    store.mkdir(parents=True, exist_ok=True)
    _safe_chmod(store, 0o700)
    path = store / f"{handle}.json"

    serialized = (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if path.exists():
        existing = path.read_bytes()
        if existing != serialized:
            raise ObservationPackError(f"content-address collision or corrupted observation: {handle}")
    else:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{handle}.", suffix=".tmp", dir=store)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle_file:
                handle_file.write(serialized)
                handle_file.flush()
                os.fsync(handle_file.fileno())
            _safe_chmod(temporary, 0o600)
            os.replace(temporary, path)
            _safe_chmod(path, 0o600)
        finally:
            if temporary.exists():
                temporary.unlink()

    return ObservationReceipt(
        handle=handle,
        label=label,
        command=normalized_command,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        path=path,
    )


def _decode_record(path: Path) -> tuple[dict[str, object], bytes, bytes]:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ObservationPackError(f"cannot read observation {path.name}: {exc}") from exc
    if not isinstance(record, dict):
        raise ObservationPackError(f"invalid observation record {path.name}: expected an object")
    if record.get("version") != SCHEMA_VERSION:
        raise ObservationPackError(
            f"unsupported observation schema {record.get('version')!r}; expected {SCHEMA_VERSION}"
        )
    if not isinstance(record.get("label"), str) or not isinstance(record.get("command"), list):
        raise ObservationPackError(f"invalid observation record {path.name}: label/command shape")
    try:
        stdout = base64.b64decode(str(record["stdout_b64"]), validate=True)
        stderr = base64.b64decode(str(record["stderr_b64"]), validate=True)
        label = str(record["label"])
        command = tuple(str(value) for value in record["command"])
        returncode = int(record["returncode"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ObservationPackError(f"invalid observation record {path.name}: {exc}") from exc

    expected_handle = _handle(label, command, returncode, stdout, stderr)
    if record.get("handle") != expected_handle or path.name != f"{expected_handle}.json":
        raise ObservationPackError(f"observation identity mismatch: {path.name}")
    if record.get("stdout_sha256") != _sha256(stdout) or record.get("stderr_sha256") != _sha256(stderr):
        raise ObservationPackError(f"observation digest mismatch: {path.name}")
    if record.get("stdout_bytes") != len(stdout) or record.get("stderr_bytes") != len(stderr):
        raise ObservationPackError(f"observation byte-count mismatch: {path.name}")
    if record.get("stdout_lines") != _line_count(stdout) or record.get("stderr_lines") != _line_count(stderr):
        raise ObservationPackError(f"observation line-count mismatch: {path.name}")
    return record, stdout, stderr


def load_observation(handle: str, *, store: Path = DEFAULT_STORE) -> tuple[dict[str, object], bytes, bytes]:
    """Load and verify one observation without allowing a handle to escape the archive directory."""
    if not HANDLE_RE.fullmatch(handle):
        raise ObservationPackError(f"invalid observation handle: {handle!r}")
    path = store / f"{handle}.json"
    if not path.is_file():
        raise ObservationPackError(f"observation not found: {handle}")
    return _decode_record(path)


def select_stream(stdout: bytes, stderr: bytes, stream: str) -> tuple[str, bytes]:
    if stream == "auto":
        return ("stderr", stderr) if stderr else ("stdout", stdout)
    if stream == "stdout":
        return "stdout", stdout
    if stream == "stderr":
        return "stderr", stderr
    raise ObservationPackError(f"unknown stream: {stream}")


def text_lines(data: bytes) -> list[str]:
    """Decode text for display while the archive retains the exact original bytes."""
    return data.decode("utf-8", errors="replace").splitlines()


def line_window(data: bytes, *, start_line: int, lines: int) -> tuple[int, int, list[str]]:
    if start_line < 1:
        raise ObservationPackError("start_line must be >= 1")
    if lines < 1:
        raise ObservationPackError("lines must be >= 1")
    all_lines = text_lines(data)
    if not all_lines:
        return 0, 0, []
    start_index = min(start_line - 1, len(all_lines))
    selected = all_lines[start_index : start_index + lines]
    if not selected:
        return 0, 0, []
    return start_index + 1, start_index + len(selected), selected


def tail_window(data: bytes, *, lines: int = DEFAULT_EXCERPT_LINES) -> tuple[int, int, list[str]]:
    if lines < 1:
        raise ObservationPackError("lines must be >= 1")
    all_lines = text_lines(data)
    if not all_lines:
        return 0, 0, []
    selected = all_lines[-lines:]
    start = len(all_lines) - len(selected) + 1
    return start, len(all_lines), selected


def should_pack(*, returncode: int, stdout: bytes, stderr: bytes, threshold_bytes: int) -> bool:
    if threshold_bytes < 0:
        raise ObservationPackError("threshold_bytes must be >= 0")
    return returncode != 0 or len(stdout) + len(stderr) >= threshold_bytes


def run_command(
    *,
    label: str,
    command: Sequence[str],
    cwd: Path = ROOT,
    store: Path = DEFAULT_STORE,
    threshold_bytes: int = DEFAULT_PACK_THRESHOLD_BYTES,
    always_pack: bool = False,
) -> ObservationReceipt:
    """Run a command with captured raw streams and pack it when the policy says evidence matters."""
    if not command:
        raise ObservationPackError("command must not be empty")
    normalized_command = tuple(str(argument) for argument in command)
    try:
        result = subprocess.run(
            list(normalized_command),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        program = normalized_command[0]
        raise ObservationPackError(f"could not start command {program!r}: {exc}") from exc
    stdout = bytes(result.stdout or b"")
    stderr = bytes(result.stderr or b"")
    if always_pack or should_pack(
        returncode=result.returncode,
        stdout=stdout,
        stderr=stderr,
        threshold_bytes=threshold_bytes,
    ):
        return archive_observation(
            label=label,
            command=normalized_command,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
            store=store,
        )
    return ObservationReceipt(
        handle=None,
        label=label,
        command=normalized_command,
        returncode=result.returncode,
        stdout=stdout,
        stderr=stderr,
        path=None,
    )


def format_compact_receipt(
    receipt: ObservationReceipt, *, excerpt_lines: int = DEFAULT_EXCERPT_LINES
) -> str:
    """Return a bounded receipt; any quoted output is copied directly from the archived stream."""
    if receipt.returncode == 0:
        if receipt.handle:
            return (
                f"ok {receipt.label} — packed {receipt.total_bytes} bytes as {receipt.handle}; "
                f"recall: python tools/agent_observation_pack.py show {receipt.handle}"
            )
        return f"ok {receipt.label}"

    lines = [f"FAILED {receipt.label} (exit {receipt.returncode})"]
    if receipt.handle:
        lines.append(
            f"full evidence: {receipt.handle} ({receipt.total_bytes} bytes); "
            f"recall: python tools/agent_observation_pack.py show {receipt.handle}"
        )
    stream_name, stream = select_stream(receipt.stdout, receipt.stderr, "auto")
    start, end, excerpt = tail_window(stream, lines=excerpt_lines)
    if excerpt:
        lines.append(f"exact {stream_name} lines {start}-{end}:")
        lines.extend(f"  {line}" for line in excerpt)
    elif receipt.stdout or receipt.stderr:
        lines.append("command produced non-text output; use the observation handle for the raw archive")
    else:
        lines.append("command produced no stdout/stderr")
    return "\n".join(lines)


def _show(arguments: argparse.Namespace) -> int:
    record, stdout, stderr = load_observation(arguments.handle, store=arguments.store)
    stream_name, data = select_stream(stdout, stderr, arguments.stream)
    start, end, selected = line_window(data, start_line=arguments.start_line, lines=arguments.lines)
    print(
        f"{record['handle']} {record['label']} exit={record['returncode']} "
        f"{stream_name} lines={record[f'{stream_name}_lines']} bytes={record[f'{stream_name}_bytes']} "
        f"sha256={record[f'{stream_name}_sha256']}"
    )
    if selected:
        print(f"--- exact {stream_name} lines {start}-{end} ---")
        for line in selected:
            print(line)
    return 0


def _run(arguments: argparse.Namespace) -> int:
    command = list(arguments.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ObservationPackError("run requires a command after --")
    receipt = run_command(
        label=arguments.label,
        command=command,
        cwd=arguments.cwd,
        store=arguments.store,
        threshold_bytes=arguments.threshold_bytes,
        always_pack=arguments.always_pack,
    )
    print(format_compact_receipt(receipt, excerpt_lines=arguments.excerpt_lines))
    return receipt.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    run_parser = subparsers.add_parser("run", help="run a command and emit a bounded evidence receipt")
    run_parser.add_argument("--label", required=True)
    run_parser.add_argument("--cwd", type=Path, default=ROOT)
    run_parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    run_parser.add_argument("--threshold-bytes", type=int, default=DEFAULT_PACK_THRESHOLD_BYTES)
    run_parser.add_argument("--excerpt-lines", type=int, default=DEFAULT_EXCERPT_LINES)
    run_parser.add_argument("--always-pack", action="store_true")
    run_parser.add_argument("command", nargs=argparse.REMAINDER)
    run_parser.set_defaults(func=_run)

    show_parser = subparsers.add_parser("show", help="recall an exact line window from one observation")
    show_parser.add_argument("handle")
    show_parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    show_parser.add_argument("--stream", choices=("auto", "stdout", "stderr"), default="auto")
    show_parser.add_argument("--start-line", type=int, default=1)
    show_parser.add_argument("--lines", type=int, default=80)
    show_parser.set_defaults(func=_show)

    arguments = parser.parse_args()
    try:
        return int(arguments.func(arguments))
    except ObservationPackError as exc:
        print(f"observation-pack: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
