"""Skill invocation lifecycle: open, close, and list what nobody closed.

Python cannot call the LLM host back, so this cannot execute a Skill's SOP and return a result the
way FR-3 of the Skill-First PRD originally asked for. What it can do is the honest substitute: open
an invocation record before the host runs the SOP, and require the host (or the deterministic path
itself) to report a terminal status afterward. An invocation nobody reports stays open forever and
is surfaced by `status` and `doctor` -- detected, not prevented. This module makes no claim that a
host actually executed anything; it only makes the absence of a claim visible.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from lifecycle import vault_lock
from models import SKILL_INVOCATION_TERMINAL_STATUSES, CareerError
from persistence import append_jsonl, read_jsonl
from skill_registry import find as find_skill
from validation import validate_skill_result
from vault import CareerVault, utc_now


def _invocation_id() -> str:
    return f"skillinv-{uuid.uuid4().hex[:12]}"


def open_invocation(
    home: CareerVault,
    skills_root: Path,
    skill: str,
    *,
    entrypoint: str,
    reason: str | None = None,
    goal: str | None = None,
    plan_id: str | None = None,
    step_id: str | None = None,
) -> dict[str, Any]:
    """Open an invocation, or refuse it outright when the Skill cannot run here.

    A `host_required` Skill opened from `cli` or `gui` writes one terminal `unsupported` record
    and nothing more (AC-7): there is no host coming to close it, so leaving it `started` would be
    a permanently-open record standing in for a run that will never happen.
    """
    entry = find_skill(skills_root, skill)
    if (plan_id is None) != (step_id is None):
        raise CareerError("--plan-id and --step-id must be supplied together", code="INVALID_INPUT")
    invocation_id = _invocation_id()
    base = {
        "invocation_id": invocation_id,
        "skill": skill,
        "execution": entry["execution"],
        "entrypoint": entrypoint,
        "reason": reason,
        "goal": goal,
        "created_at": utc_now(),
    }
    if plan_id is not None:
        base["plan_id"] = plan_id
        base["step_id"] = step_id
    if entry["execution"] == "host_required" and entrypoint in ("cli", "gui"):
        record = {
            **base,
            "status": "unsupported",
            "error": "host_required",
            "available_hosts": ["claude", "codex"],
            "artifacts": [],
            "evidence_used": [],
            "tools_used": [],
            "signals": [],
        }
        validate_skill_result(record, terminal=True)
        with vault_lock(home):
            if plan_id is not None:
                from execution_plans import validate_plan_step_open

                validate_plan_step_open(home, plan_id, step_id, skill)
            append_jsonl(home.invocations, record)
        return record
    record = {**base, "status": "started"}
    validate_skill_result(record, terminal=False)
    with vault_lock(home):
        if plan_id is not None:
            from execution_plans import validate_plan_step_open

            validate_plan_step_open(home, plan_id, step_id, skill)
        append_jsonl(home.invocations, record)
    return record


def _by_invocation(home: CareerVault) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in read_jsonl(home.invocations):
        grouped.setdefault(row.get("invocation_id"), []).append(row)
    return grouped


def report_invocation(
    home: CareerVault,
    invocation_id: str,
    *,
    status: str,
    summary: str | None = None,
    artifacts: list[str] | None = None,
    evidence_used: list[str] | None = None,
    tools_used: list[str] | None = None,
    error: str | None = None,
    signals: list[str] | None = None,
) -> dict[str, Any]:
    """Close an invocation the host (or a deterministic path) actually ran.

    Refuses an unknown id, and refuses a second terminal report on an id already closed -- a
    closed invocation cannot un-close itself. `open_invocation` only ever writes a `started` row
    or a terminal one (never anything else), so a known id with no terminal row always has a
    `started` row to report against; there is no third case to guard against here.

    The read and both guards run *inside* the lock, matching every other read-modify-write in this
    runtime (`lifecycle.review_work_event`, `lifecycle.approve`): reading outside the lock would
    let two concurrent `skill-report` calls for the same id -- a host retry racing the user's CLI,
    or the GUI and CLI against one Vault -- both observe no terminal record, both pass the
    "already closed" guard, and both append, leaving two conflicting terminal records for one
    invocation.

    `validate_skill_result` requires `summary` for `completed`/`needs_input`/`needs_approval` and
    `error` for `failed`/`blocked`/`unsupported`, so a `completed` report with nothing behind it
    (no artifact, no evidence, no summary) is refused here rather than accepted as indistinguishable
    from one that did something.
    """
    with vault_lock(home):
        rows = _by_invocation(home).get(invocation_id)
        if not rows:
            raise CareerError(f"unknown skill invocation: {invocation_id}")
        already_closed = next(
            (row for row in rows if row.get("status") in SKILL_INVOCATION_TERMINAL_STATUSES), None,
        )
        if already_closed is not None:
            raise CareerError(
                f"skill invocation {invocation_id} is already closed with status "
                f"{already_closed['status']!r}"
            )
        started = next(row for row in rows if row.get("status") == "started")
        record = {
            "invocation_id": invocation_id,
            "skill": started["skill"],
            "execution": started["execution"],
            "entrypoint": started["entrypoint"],
            "status": status,
            "summary": summary,
            "artifacts": list(artifacts or []),
            "evidence_used": list(evidence_used or []),
            "tools_used": list(tools_used or []),
            "error": error,
            "signals": list(signals or []),
            "created_at": utc_now(),
        }
        if started.get("plan_id") is not None:
            record["plan_id"] = started["plan_id"]
            record["step_id"] = started["step_id"]
            from execution_plans import validate_plan_step_report

            validate_plan_step_report(
                home,
                started["plan_id"],
                started["step_id"],
                started["skill"],
                status=status,
                artifacts=record["artifacts"],
            )
        validate_skill_result(record, terminal=True)
        append_jsonl(home.invocations, record)
        return record


def open_invocations(home: CareerVault) -> list[dict[str, Any]]:
    """Every invocation with a `started` record and no terminal record, oldest-`created_at` first."""
    open_rows: list[dict[str, Any]] = []
    for invocation_id, rows in _by_invocation(home).items():
        if any(row.get("status") in SKILL_INVOCATION_TERMINAL_STATUSES for row in rows):
            continue
        started = next((row for row in rows if row.get("status") == "started"), None)
        if started is not None:
            open_rows.append(started)
    return sorted(open_rows, key=lambda row: row.get("created_at", ""))
