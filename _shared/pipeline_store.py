"""Shared read-lock-mutate-write helper for data/pipeline.yml.

Two writers touch pipeline.yml: career_agent.py's approve() and scripts/check_action.py.
Both used to do their own read-whole-file / rewrite-whole-file, with no lock and no atomic
write, so a crash mid-write could truncate the file and a second local process writing at
the same time could silently drop the first one's change. mutate() below is the one place
that does load -> lock -> mutate -> temp-write -> atomic rename -> unlock.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None


@contextmanager
def locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with open(lock_path, "a+") as handle:
        if fcntl is not None:
            fcntl.flock(handle, fcntl.LOCK_EX)
        elif msvcrt is not None:
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)
            elif msvcrt is not None:
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def load(path: Path) -> dict[str, Any]:
    import yaml

    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    tmp.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    os.replace(tmp, path)  # atomic on both POSIX and Windows


def mutate(path: Path, fn: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    """Load, apply fn(data) -> data, write back — all under one exclusive lock."""
    with locked(path):
        data = fn(load(path))
        atomic_write(path, data)
        return data
