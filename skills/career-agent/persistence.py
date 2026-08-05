"""Canonical JSON/TOML/JSONL persistence boundary for the Career Agent.

This module owns file-format serialization and the atomic replacement writer.
It deliberately knows nothing about routing, proposals, or the CLI so the
runtime can depend on it without creating a domain import cycle.
"""

from __future__ import annotations

import json
import os
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Iterable

from models import CareerError


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        raise CareerError(f"invalid JSON: {path}: {exc}") from exc


def atomic_write_text(path: Path, payload: str) -> None:
    """Write a complete sibling temp file, then replace the destination atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Byte-mode sibling of ``atomic_write_text`` for imported document blobs.

    Personal documents are opaque bytes: decoding them to text would corrupt every binary format
    and change the SHA-256 the import contract verifies against.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    # ponytail: linear JSONL scan; move to SQLite FTS5 when event volume makes it slow.
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CareerError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
        if isinstance(row, dict):
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    atomic_write_text(path, payload)


def read_toml(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            value = tomllib.load(stream)
    except FileNotFoundError:
        return {} if default is None else default
    except tomllib.TOMLDecodeError as exc:
        raise CareerError(f"invalid TOML: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CareerError(f"TOML root must be a table: {path}")
    return value


def toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list) and all(not isinstance(item, dict) for item in value):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    raise CareerError(f"unsupported TOML value: {type(value).__name__}")


def write_toml(path: Path, values: dict[str, Any]) -> None:
    """Write the small, flat TOML subset used by the vault contract."""
    lines: list[str] = []
    tables: list[tuple[str, dict[str, Any]]] = []
    table_arrays: list[tuple[str, list[dict[str, Any]]]] = []
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, dict):
            tables.append((key, value))
        elif isinstance(value, list) and all(isinstance(item, dict) for item in value):
            if value:
                table_arrays.append((key, value))
            else:
                lines.append(f"{key} = []")
        else:
            lines.append(f"{key} = {toml_value(value)}")
    for key, table in tables:
        lines.extend(("", f"[{key}]"))
        lines.extend(f"{name} = {toml_value(item)}" for name, item in table.items() if item is not None)
    for key, rows in table_arrays:
        for row in rows:
            lines.extend(("", f"[[{key}]]"))
            lines.extend(f"{name} = {toml_value(item)}" for name, item in row.items() if item is not None)
    atomic_write_text(path, "\n".join(lines) + "\n")
