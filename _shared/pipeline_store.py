"""Shared read-lock-mutate-write helper for data/pipeline.yml.

Two writers touch pipeline.yml: career_agent.py's approve() and scripts/check_action.py.
Both used to do their own read-whole-file / rewrite-whole-file, with no lock and no atomic
write, so a crash mid-write could truncate the file and a second local process writing at
the same time could silently drop the first one's change. mutate() below is the one place
that does load -> lock -> mutate -> temp-write -> atomic rename -> unlock.
"""

from __future__ import annotations

import os
import datetime as dt
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


def _companies(data: dict[str, Any]) -> list[dict[str, Any]]:
    companies = data.setdefault("companies", [])
    if not isinstance(companies, list):
        raise ValueError("pipeline companies must be a list")
    return companies


DECISION_STATUSES = {"proceed", "review", "conflict"}
MATCH_MODEL_VERSIONS = {"evidence_based_v3", "legacy_v1"}


def _validate_fields(fields: dict[str, Any]) -> None:
    if not isinstance(fields, dict):
        raise ValueError("company fields must be a JSON object")
    if "slug" in fields:
        raise ValueError("slug is the command argument, not an editable field")
    if "stage" in fields and (not isinstance(fields["stage"], int) or not 0 <= fields["stage"] <= 7):
        raise ValueError("stage must be an integer from 0 to 7")

    level = fields.get("interest_level")
    if level is not None and (isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 5):
        raise ValueError("interest_level must be an integer from 1 to 5, or null")
    status = fields.get("decision_status")
    if status is not None and status not in DECISION_STATUSES:
        raise ValueError(f"decision_status must be one of {sorted(DECISION_STATUSES)}")
    version = fields.get("match_model_version")
    if version is not None and version not in MATCH_MODEL_VERSIONS:
        raise ValueError(f"match_model_version must be one of {sorted(MATCH_MODEL_VERSIONS)}")
    # match_score is legacy_v1 history. Writing a new one would put an uncalibrated 0-100 number
    # back beside a v3 decision_status, which is the exact confusion v3 removed.
    if "match_score" in fields:
        raise ValueError(
            "match_score is legacy_v1 and frozen; existing values are preserved but no new one is "
            "written. Use decision_status (+ match_model_version) from _shared/matching_v3.py."
        )


CLEARABLE_FIELDS = {
    "interest_level", "interest_reason", "interest_evidence", "interest_updated_at",
    "next_action", "deadline", "closed_reason", "match_conflicts", "match_unknowns"
}


def _snapshot_interest_history_if_needed(entry: dict[str, Any], fields: dict[str, Any]) -> None:
    if "interest_level" not in fields:
        return
    new_level = fields.get("interest_level")
    old_level = entry.get("interest_level")
    if old_level is not None and old_level != new_level:
        entry.setdefault("interest_history", []).append({
            "interest_level": old_level,
            "interest_reason": entry.get("interest_reason"),
            "interest_evidence": entry.get("interest_evidence"),
            "interest_updated_at": entry.get("interest_updated_at"),
            "changed_at": dt.date.today().isoformat(),
        })


def _append_history_idempotent(entry: dict[str, Any], history: dict[str, Any] | None) -> None:
    if history is None:
        return
    if not isinstance(history, dict):
        raise ValueError("history must be an object")
    hist_id = history.get("event_id") or history.get("id")
    if "id" in history:
        history = {key: value for key, value in history.items() if key != "id"}
        if "event_id" not in history and hist_id:
            history["event_id"] = hist_id
    history_list = entry.setdefault("history", [])
    if hist_id:
        for item in history_list:
            if isinstance(item, dict) and (item.get("id") == hist_id or item.get("event_id") == hist_id):
                return
    history_list.append(history)


def upsert_company(
    path: Path,
    slug: str,
    fields: dict[str, Any],
    *,
    history: dict[str, Any] | None = None,
    forward_only_stage: bool = True,
) -> dict[str, Any]:
    """Merge one company through the shared lock/atomic-write path."""
    _validate_fields(fields)
    if not slug.strip():
        raise ValueError("slug must not be empty")

    def apply(data: dict[str, Any]) -> dict[str, Any]:
        companies = _companies(data)
        entry = next((item for item in companies if item.get("slug") == slug), None)
        if entry is None:
            entry = {"slug": slug, "name": fields.get("name") or slug, "closed": False, "history": []}
            companies.append(entry)
        _snapshot_interest_history_if_needed(entry, fields)
        for key, value in fields.items():
            if value is None:
                if key in CLEARABLE_FIELDS:
                    entry[key] = None
                continue
            if key == "stage" and forward_only_stage and isinstance(entry.get("stage"), int):
                if value < entry["stage"]:
                    continue
            entry[key] = value
        _append_history_idempotent(entry, history)
        data["updated"] = str((history or {}).get("date") or dt.date.today().isoformat())
        return data

    return mutate(path, apply)


def update_company(path: Path, slug: str, fields: dict[str, Any], *, history: dict[str, Any] | None = None) -> dict[str, Any]:
    """Update an existing company; unlike upsert, a missing slug is an error."""
    _validate_fields(fields)

    def apply(data: dict[str, Any]) -> dict[str, Any]:
        if not any(item.get("slug") == slug for item in _companies(data)):
            raise ValueError(f"no company {slug!r}")
        return _update_company_data(data, slug, fields, history)

    return mutate(path, apply)


def _update_company_data(
    data: dict[str, Any], slug: str, fields: dict[str, Any], history: dict[str, Any] | None,
) -> dict[str, Any]:
    entry = next(item for item in _companies(data) if item.get("slug") == slug)
    _snapshot_interest_history_if_needed(entry, fields)
    for key, value in fields.items():
        if value is None:
            if key in CLEARABLE_FIELDS:
                entry[key] = None
            continue
        if key == "stage" and isinstance(entry.get("stage"), int) and value < entry["stage"]:
            continue
        entry[key] = value
    _append_history_idempotent(entry, history)
    data["updated"] = str((history or {}).get("date") or dt.date.today().isoformat())
    return data


def append_history(path: Path, slug: str, event: str, *, date: str | None = None) -> dict[str, Any]:
    if not event.strip():
        raise ValueError("history event must not be empty")
    return update_company(path, slug, {}, history={"date": date or dt.date.today().isoformat(), "event": event.strip()})
