"""Bounded host-coordinated execution plans for Gate D.

The runtime selects the next Skill and persists workflow state, but never calls a Host. Invocation
rows remain the source of truth for what actually happened; this module only keeps the current plan
snapshot and folds those rows into its next-step view.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from lifecycle import vault_lock
from models import (
    PLAN_MAX_ATTEMPTS,
    PLAN_SIGNALS,
    PLAN_STATUSES,
    PLAN_STEP_STATUSES,
    PLAN_SCHEMA_VERSION,
    SKILL_INVOCATION_TERMINAL_STATUSES,
    CareerError,
)
from persistence import atomic_write_text, read_json, read_jsonl
from skill_registry import find as find_skill
from validation import validate_execution_plan
from vault import CareerVault, utc_now


_QUALITY_SKILLS = {"sip"}
_TERMINAL_STEP_STATUSES = PLAN_STEP_STATUSES - {"pending", "started"}


def _plan_id() -> str:
    return f"plan-{uuid.uuid4().hex[:16]}"


def _plan_path(home: CareerVault, plan_id: str) -> Path:
    if not isinstance(plan_id, str) or not plan_id.startswith("plan-"):
        raise CareerError("invalid execution plan id")
    return home.execution_plans / f"{plan_id}.json"


def _load_plan(home: CareerVault, plan_id: str) -> dict[str, Any]:
    path = _plan_path(home, plan_id)
    value = read_json(path, None)
    if not isinstance(value, dict):
        raise CareerError(f"execution plan not found: {plan_id}")
    validate_execution_plan(value)
    return value


def _write_plan(home: CareerVault, plan: dict[str, Any]) -> None:
    validate_execution_plan(plan)
    home.execution_plans.mkdir(parents=True, exist_ok=True)
    atomic_write_text(_plan_path(home, plan["plan_id"]), json.dumps(
        plan, ensure_ascii=False, indent=2,
    ) + "\n")


def _policy_steps(skill: str) -> list[dict[str, Any]]:
    if skill == "career-document":
        names = (
            ("draft", "career-document", None, True, False),
            ("humanize", "humanize-japanese-career", "draft", True, False),
            ("verify", "sip", "humanize", False, True),
        )
    else:
        names = (("domain", skill, None, False, False),)
    return [
        {
            "id": step_id,
            "skill": step_skill,
            "status": "pending",
            "depends_on": [] if dependency is None else [dependency],
            "condition": None,
            "invocation_id": None,
            "requires_artifact": requires_artifact,
            "requires_artifact_reference": requires_artifact_reference,
        }
        for step_id, step_skill, dependency, requires_artifact, requires_artifact_reference in names
    ]


def create_plan(
    home: CareerVault,
    skills_root: Path,
    *,
    goal: str,
    skill: str,
) -> dict[str, Any]:
    if not isinstance(goal, str) or not goal.strip():
        raise CareerError("plan goal must be a non-empty string", code="INVALID_INPUT")
    entry = find_skill(skills_root, skill)
    if skill in _QUALITY_SKILLS:
        raise CareerError("plan must start with a routed Domain Skill", code="INVALID_INPUT")
    if entry["execution"] not in {"deterministic", "hybrid", "host_required"}:
        raise CareerError(f"unsupported execution class for plan Skill: {skill}")
    now = utc_now()
    plan = {
        "plan_schema_version": PLAN_SCHEMA_VERSION,
        "plan_id": _plan_id(),
        "goal": goal.strip(),
        "status": "running",
        "steps": _policy_steps(skill),
        "created_at": now,
        "updated_at": now,
    }
    validate_execution_plan(plan)
    with vault_lock(home):
        _write_plan(home, plan)
    return {"mode": "plan", **plan}


def _rows_for_plan(home: CareerVault, plan_id: str) -> list[dict[str, Any]]:
    return [row for row in read_jsonl(home.invocations) if row.get("plan_id") == plan_id]


def _rows_for_step(rows: list[dict[str, Any]], step_id: str) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("step_id") == step_id]


def _signals(rows: list[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    for row in rows:
        if row.get("status") not in SKILL_INVOCATION_TERMINAL_STATUSES:
            continue
        values.update(signal for signal in row.get("signals", []) if signal in PLAN_SIGNALS)
    return values


def _latest_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    # JSONL append order is the authoritative tie-breaker because `utc_now()` intentionally has
    # second precision and a started row plus its terminal row commonly share a timestamp.
    return rows[-1] if rows else None


def _contract_error(step: dict[str, Any], row: dict[str, Any]) -> str | None:
    if row.get("status") != "completed":
        return None
    artifacts = row.get("artifacts") or []
    if step.get("requires_artifact") and not artifacts:
        return "step output contract requires at least one artifact"
    if step.get("requires_artifact_reference") and not artifacts:
        return "step output contract requires an artifact reference"
    return None


def _result_projection(step: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    row = _latest_row(rows)
    if row is None or row.get("status") not in SKILL_INVOCATION_TERMINAL_STATUSES:
        return None
    error = row.get("error") or _contract_error(step, row)
    return {
        "invocation_id": row.get("invocation_id"),
        "status": "blocked" if error and row.get("status") == "completed" else row.get("status"),
        "invocation_status": row.get("status"),
        "summary": row.get("summary"),
        "error": error,
        "artifacts": list(row.get("artifacts") or []),
        "evidence_used": list(row.get("evidence_used") or []),
        "tools_used": list(row.get("tools_used") or []),
        "signals": list(row.get("signals") or []),
    }


def _materialize(plan: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    materialized = {**plan, "steps": [dict(step) for step in plan["steps"]]}
    for step in materialized["steps"]:
        linked = _latest_row(_rows_for_step(rows, step["id"]))
        if linked is None:
            continue
        # A retry/resume keeps the previous terminal invocation id until a new started row is
        # opened. That marker prevents the old terminal result from immediately re-closing the
        # reopened step.
        if (
            step["status"] == "pending"
            and step.get("invocation_id") == linked.get("invocation_id")
            and linked.get("status") in SKILL_INVOCATION_TERMINAL_STATUSES
        ):
            continue
        step["invocation_id"] = linked.get("invocation_id")
        if linked.get("status") in PLAN_STEP_STATUSES:
            step["status"] = "blocked" if _contract_error(step, linked) else linked["status"]

    current = next(
        (step for step in materialized["steps"] if step["status"] == "started"),
        None,
    )
    terminal = [step for step in materialized["steps"] if step["status"] in _TERMINAL_STEP_STATUSES]
    if current is not None:
        status = "running"
    elif any(step["status"] == "needs_input" for step in materialized["steps"]):
        status = "paused"
    elif any(step["status"] == "needs_approval" for step in materialized["steps"]):
        status = "paused"
    elif any(step["status"] == "unsupported" for step in materialized["steps"]):
        status = "unsupported"
    elif any(step["status"] == "blocked" for step in materialized["steps"]):
        status = "blocked"
    elif any(step["status"] == "failed" for step in materialized["steps"]):
        status = "failed"
    elif len(terminal) == len(materialized["steps"]):
        status = "completed"
    else:
        status = "running"
    materialized["status"] = status
    return materialized


def _public_step(
    plan: dict[str, Any], step: dict[str, Any], rows: list[dict[str, Any]],
) -> dict[str, Any]:
    clean = {key: value for key, value in step.items() if key != "_plan_id"}
    result = _result_projection(step, _rows_for_step(rows, step["id"]))
    if result is not None and step["status"] not in {"skipped", "pending", "started"}:
        clean["result"] = result
    if step["status"] == "pending" and step.get("depends_on"):
        dependency = step["depends_on"][0]
        dependency_step = next(
            (candidate for candidate in plan["steps"] if candidate["id"] == dependency),
            None,
        )
        if dependency_step is not None:
            dependency_result = _result_projection(
                dependency_step, _rows_for_step(rows, dependency),
            )
            if dependency_result is not None:
                clean["input"] = {"from_step": dependency, **dependency_result}
    if step["status"] == "pending":
        clean["invoke_with"] = (
            f"skill-open --skill {clean['skill']} --entrypoint HOST "
            f"--plan-id {plan['plan_id']} --step-id {clean['id']}"
        )
    return clean
    return clean


def validate_plan_step_open(home: CareerVault, plan_id: str, step_id: str, skill: str) -> None:
    """Validate a linked open while the caller holds ``vault_lock``."""
    plan = _load_plan(home, plan_id)
    rows = _rows_for_plan(home, plan_id)
    materialized = _materialize(plan, rows)
    step = next((item for item in materialized["steps"] if item["id"] == step_id), None)
    if step is None:
        raise CareerError(f"unknown execution plan step: {step_id}", code="INVALID_INPUT")
    if step["skill"] != skill:
        raise CareerError("linked invocation Skill does not match the plan step", code="INVALID_INPUT")
    if materialized["status"] != "running" or step["status"] != "pending":
        raise CareerError("execution plan step is not ready to open", code="INVALID_INPUT")
    step_by_id = {item["id"]: item for item in materialized["steps"]}
    if any(step_by_id[dependency]["status"] not in {"completed", "skipped"} for dependency in step["depends_on"]):
        raise CareerError("execution plan dependencies are not complete", code="INVALID_INPUT")
    if step["condition"] and step["condition"] not in _signals(rows):
        raise CareerError("execution plan step condition is not satisfied", code="INVALID_INPUT")
    if (_latest_row(_rows_for_step(rows, step_id)) or {}).get("status") == "started":
        raise CareerError("execution plan step already has an open invocation", code="INVALID_INPUT")


def _reset_for_resume(plan: dict[str, Any], step: dict[str, Any]) -> None:
    step["status"] = "pending"
    plan["status"] = "running"
    plan["updated_at"] = utc_now()


def next_step(
    home: CareerVault,
    plan_id: str,
    *,
    resume: bool = False,
    retry: bool = False,
) -> dict[str, Any]:
    if resume and retry:
        raise CareerError("choose either --resume or --retry", code="INVALID_INPUT")
    with vault_lock(home):
        plan = _load_plan(home, plan_id)
        rows = _rows_for_plan(home, plan_id)
        materialized = _materialize(plan, rows)
        current = next(
            (
                step for step in materialized["steps"]
                if step["status"] in {"started", "needs_input", "needs_approval", "blocked", "failed", "unsupported"}
            ),
            None,
        )
        if resume or retry:
            if current is None:
                raise CareerError("execution plan has no resumable step", code="INVALID_INPUT")
            if resume and current["status"] not in {"needs_input", "needs_approval"}:
                raise CareerError("--resume requires an input- or approval-paused step", code="INVALID_INPUT")
            if retry and current["status"] != "failed":
                raise CareerError("--retry requires a failed step", code="INVALID_INPUT")
            attempts = sum(row.get("status") == "started" for row in _rows_for_step(rows, current["id"]))
            if attempts >= PLAN_MAX_ATTEMPTS:
                raise CareerError("execution plan step retry limit reached", code="INVALID_INPUT")
            _reset_for_resume(materialized, current)
            _write_plan(home, materialized)
            plan = materialized
            rows = _rows_for_plan(home, plan_id)
            materialized = _materialize(plan, rows)
            current = None

        if current is not None:
            if current["status"] == "started":
                return {
                    "mode": "plan-next",
                    "plan_id": plan_id,
                    "status": "running",
                    "current_step": _public_step(materialized, current, rows),
                    "next_step": None,
                }
            if materialized != plan:
                materialized["updated_at"] = utc_now()
                _write_plan(home, materialized)
            return {
                "mode": "plan-next",
                "plan_id": plan_id,
                "status": materialized["status"],
                "current_step": _public_step(materialized, current, rows),
                "next_step": None,
                "resume": current["status"] in {"needs_input", "needs_approval"},
                "retry": current["status"] == "failed",
            }

        available_signals = _signals(rows)
        changed = materialized != plan
        for step in materialized["steps"]:
            if step["status"] != "pending":
                continue
            if step["condition"] and step["condition"] not in available_signals:
                step["status"] = "skipped"
                step["updated_at"] = utc_now()
                changed = True
                continue
            if changed:
                materialized["updated_at"] = utc_now()
                _write_plan(home, materialized)
            return {
                "mode": "plan-next",
                "plan_id": plan_id,
                "status": "running",
                "current_step": None,
                "next_step": _public_step(materialized, step, rows),
            }

        materialized["status"] = "completed"
        materialized["updated_at"] = utc_now()
        _write_plan(home, materialized)
        return {
            "mode": "plan-next",
            "plan_id": plan_id,
            "status": "completed",
            "current_step": None,
            "next_step": None,
        }


def plan_status(home: CareerVault, plan_id: str) -> dict[str, Any]:
    with vault_lock(home):
        plan = _load_plan(home, plan_id)
        rows = _rows_for_plan(home, plan_id)
        materialized = _materialize(plan, rows)
    current = next(
        (
            step for step in materialized["steps"]
            if step["status"] in {"started", "needs_input", "needs_approval", "blocked", "failed", "unsupported"}
        ),
        None,
    )
    return {
        "mode": "plan-status",
        "plan_id": plan_id,
        "status": materialized["status"],
        "goal": materialized["goal"],
        "steps": [_public_step(materialized, step, rows) for step in materialized["steps"]],
        "current_step": _public_step(materialized, current, rows) if current else None,
        "created_at": materialized["created_at"],
        "updated_at": materialized["updated_at"],
    }


def active_plans(home: CareerVault) -> list[dict[str, Any]]:
    if not home.execution_plans.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    with vault_lock(home):
        for path in sorted(home.execution_plans.glob("plan-*.json")):
            plan_id = path.stem
            try:
                plan = _load_plan(home, plan_id)
            except CareerError:
                continue
            materialized = _materialize(plan, _rows_for_plan(home, plan_id))
            if materialized["status"] in PLAN_STATUSES - {"completed"}:
                current = next((step for step in materialized["steps"] if step["status"] == "started"), None)
                rows.append({
                    "plan_id": plan_id,
                    "goal": materialized["goal"],
                    "status": materialized["status"],
                    "current_step": current["id"] if current else None,
                    "updated_at": materialized["updated_at"],
                })
    return rows
