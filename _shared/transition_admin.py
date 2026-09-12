#!/usr/bin/env python3
"""Deterministic Japan job-transition administration projection.

The registry stores official procedural sources and narrow applicability rules.  This module does
not calculate tax, insurance premiums, benefits, or immigration eligibility.  It answers the much
smaller question: for the supplied transition facts, which document/action is required,
conditional, recommended, not applicable, or still unknown, and who owns the next step.
"""

from __future__ import annotations

import calendar
import datetime as dt
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = ROOT / "_shared" / "transition_admin.yml"

ALLOWED_REQUIREDNESS = {"required", "conditional", "recommended"}
ALLOWED_RESULT_STATES = ALLOWED_REQUIREDNESS | {"not_applicable", "unknown"}
ALLOWED_OWNERS = {
    "user",
    "former_employer",
    "new_employer",
    "former_and_new_employer",
    "authority",
}
ALLOWED_OPS = {"eq", "in", "in_group", "not_in_groups", "is_known"}
ALLOWED_DEADLINE_KINDS = {"days_after", "months_after"}
ALLOWED_SOURCE_TYPES = {"official_guidance", "official_local_guidance", "statute"}


class TransitionAdminError(ValueError):
    """Raised when registry or scenario data violates the deterministic contract."""


def _date(value: Any, label: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise TransitionAdminError(f"{label} must be YYYY-MM-DD") from exc


def _known(value: Any) -> bool:
    return value is not None and value != ""


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    if not path.is_file():
        raise TransitionAdminError(f"transition admin registry not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    validate_registry(payload)
    return payload


def validate_registry(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise TransitionAdminError("registry must be an object")
    if payload.get("schema_version") != "1.0":
        raise TransitionAdminError("registry schema_version must be 1.0")

    sources = payload.get("sources")
    tasks = payload.get("tasks")
    groups = payload.get("residence_status_groups")
    if not isinstance(sources, dict) or not sources:
        raise TransitionAdminError("registry sources must be a non-empty object")
    if not isinstance(tasks, list) or not tasks:
        raise TransitionAdminError("registry tasks must be a non-empty list")
    if not isinstance(groups, dict):
        raise TransitionAdminError("residence_status_groups must be an object")

    for group_name, values in groups.items():
        if not isinstance(group_name, str) or not group_name:
            raise TransitionAdminError("residence status group names must be non-empty strings")
        if not isinstance(values, list) or not values or not all(isinstance(v, str) and v for v in values):
            raise TransitionAdminError(f"residence_status_groups.{group_name} must be strings")

    for source_id, source in sources.items():
        if not isinstance(source, dict):
            raise TransitionAdminError(f"source {source_id} must be an object")
        required = {"authority", "source_type", "url", "observed_at", "review_by"}
        missing = sorted(required - set(source))
        if missing:
            raise TransitionAdminError(f"source {source_id} missing: {', '.join(missing)}")
        if source["source_type"] not in ALLOWED_SOURCE_TYPES:
            raise TransitionAdminError(f"source {source_id} has unsupported source_type")
        if not str(source["url"]).startswith("https://"):
            raise TransitionAdminError(f"source {source_id} must use https")
        _date(source["observed_at"], f"source {source_id}.observed_at")
        _date(source["review_by"], f"source {source_id}.review_by")

    seen: set[str] = set()
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise TransitionAdminError(f"tasks[{index}] must be an object")
        required = {
            "id",
            "label_ja",
            "category",
            "phase",
            "owner",
            "user_action",
            "requiredness",
            "source_ids",
            "guidance",
        }
        missing = sorted(required - set(task))
        if missing:
            raise TransitionAdminError(f"tasks[{index}] missing: {', '.join(missing)}")
        task_id = str(task["id"])
        if not task_id or task_id in seen:
            raise TransitionAdminError(f"duplicate or empty task id: {task_id!r}")
        seen.add(task_id)
        if task["requiredness"] not in ALLOWED_REQUIREDNESS:
            raise TransitionAdminError(f"task {task_id} has invalid requiredness")
        if task["owner"] not in ALLOWED_OWNERS:
            raise TransitionAdminError(f"task {task_id} has invalid owner")
        source_ids = task["source_ids"]
        if not isinstance(source_ids, list) or not source_ids:
            raise TransitionAdminError(f"task {task_id} must cite at least one source")
        missing_sources = sorted(set(source_ids) - set(sources))
        if missing_sources:
            raise TransitionAdminError(
                f"task {task_id} references unknown sources: {', '.join(missing_sources)}"
            )
        if "residence_status_group" in task and task["residence_status_group"] not in groups:
            raise TransitionAdminError(f"task {task_id} references unknown residence status group")
        if "applies_if" in task:
            _validate_condition(task["applies_if"], task_id, groups)
        if "deadline" in task:
            deadline = task["deadline"]
            if not isinstance(deadline, dict) or deadline.get("kind") not in ALLOWED_DEADLINE_KINDS:
                raise TransitionAdminError(f"task {task_id} has invalid deadline")
            if not isinstance(deadline.get("value"), int) or deadline["value"] < 0:
                raise TransitionAdminError(f"task {task_id} deadline value must be a non-negative int")
            if not isinstance(task.get("trigger_field"), str) or not task["trigger_field"]:
                raise TransitionAdminError(f"task {task_id} deadline requires trigger_field")


def _validate_condition(condition: Any, task_id: str, groups: dict[str, Any]) -> None:
    if not isinstance(condition, dict):
        raise TransitionAdminError(f"task {task_id} condition must be an object")
    branches = [name for name in ("all", "any") if name in condition]
    if branches:
        if len(branches) != 1 or len(condition) != 1:
            raise TransitionAdminError(f"task {task_id} condition must have exactly one all/any")
        children = condition[branches[0]]
        if not isinstance(children, list) or not children:
            raise TransitionAdminError(f"task {task_id} {branches[0]} must be a non-empty list")
        for child in children:
            _validate_condition(child, task_id, groups)
        return

    required = {"field", "op", "value"}
    if set(condition) != required:
        raise TransitionAdminError(f"task {task_id} predicate must contain field/op/value only")
    if condition["op"] not in ALLOWED_OPS:
        raise TransitionAdminError(f"task {task_id} uses unsupported op {condition['op']!r}")
    if condition["op"] == "in_group" and condition["value"] not in groups:
        raise TransitionAdminError(f"task {task_id} uses unknown group {condition['value']!r}")
    if condition["op"] == "not_in_groups":
        values = condition["value"]
        if not isinstance(values, list) or not values or not all(value in groups for value in values):
            raise TransitionAdminError(f"task {task_id} not_in_groups must name known groups")
    if condition["op"] == "in" and not isinstance(condition["value"], list):
        raise TransitionAdminError(f"task {task_id} in predicate value must be a list")
    if condition["op"] == "is_known" and not isinstance(condition["value"], bool):
        raise TransitionAdminError(f"task {task_id} is_known value must be boolean")


def _predicate(
    condition: dict[str, Any], scenario: dict[str, Any], groups: dict[str, list[str]]
) -> bool | None:
    if "all" in condition:
        values = [_predicate(child, scenario, groups) for child in condition["all"]]
        if False in values:
            return False
        if None in values:
            return None
        return True
    if "any" in condition:
        values = [_predicate(child, scenario, groups) for child in condition["any"]]
        if True in values:
            return True
        if None in values:
            return None
        return False

    field = condition["field"]
    op = condition["op"]
    expected = condition["value"]
    actual = scenario.get(field)
    if op == "is_known":
        return _known(actual) is expected
    if not _known(actual):
        return None
    if op == "eq":
        return actual == expected
    if op == "in":
        return actual in expected
    if op == "in_group":
        return actual in groups[expected]
    if op == "not_in_groups":
        return all(actual not in groups[group_name] for group_name in expected)
    raise AssertionError(op)


def _add_months(value: dt.date, months: int) -> dt.date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def _deadline(task: dict[str, Any], scenario: dict[str, Any]) -> str | None:
    if "deadline" not in task:
        return None
    trigger = scenario.get(task["trigger_field"])
    if not _known(trigger):
        return None
    base = _date(trigger, task["trigger_field"])
    rule = task["deadline"]
    if rule["kind"] == "days_after":
        return (base + dt.timedelta(days=rule["value"])).isoformat()
    if rule["kind"] == "months_after":
        return _add_months(base, rule["value"]).isoformat()
    raise AssertionError(rule["kind"])


def project(
    scenario: dict[str, Any], *, registry: dict[str, Any] | None = None, as_of: dt.date | None = None
) -> list[dict[str, Any]]:
    if not isinstance(scenario, dict):
        raise TransitionAdminError("scenario must be an object")
    data = registry or load_registry()
    validate_registry(data)
    today = as_of or dt.date.today()
    groups = data["residence_status_groups"]
    sources = data["sources"]
    results: list[dict[str, Any]] = []

    for task in data["tasks"]:
        condition = task.get("applies_if")
        applies = True if condition is None else _predicate(condition, scenario, groups)
        missing_inputs = [
            field for field in task.get("required_inputs", []) if not _known(scenario.get(field))
        ]
        cited_sources = [sources[source_id] | {"id": source_id} for source_id in task["source_ids"]]
        stale_sources = [
            source["id"] for source in cited_sources if _date(source["review_by"], source["id"]) < today
        ]

        if applies is False:
            state = "not_applicable"
            reason = "conditions_not_met"
        elif applies is None or missing_inputs:
            state = "unknown"
            reason = "missing_input"
        elif stale_sources:
            state = "unknown"
            reason = "stale_source"
        else:
            state = task["requiredness"]
            reason = "rule_applied"

        result = {
            "id": task["id"],
            "label_ja": task["label_ja"],
            "category": task["category"],
            "phase": task["phase"],
            "owner": task["owner"],
            "user_action": task["user_action"],
            "state": state,
            "reason": reason,
            "missing_inputs": missing_inputs,
            "deadline": _deadline(task, scenario) if state in ALLOWED_REQUIREDNESS else None,
            "municipality_specific": bool(task.get("municipality_specific", False)),
            "guidance": task["guidance"],
            "sources": cited_sources,
            "stale_sources": stale_sources,
        }
        if result["state"] not in ALLOWED_RESULT_STATES:
            raise AssertionError(result["state"])
        results.append(result)
    return results


def render_text(results: list[dict[str, Any]]) -> str:
    headings = (
        ("required", "必ず対応"),
        ("conditional", "条件付き"),
        ("recommended", "推奨・必要に応じて"),
        ("unknown", "確認が必要"),
        ("not_applicable", "現状は対象外"),
    )
    lines: list[str] = []
    for state, heading in headings:
        rows = [row for row in results if row["state"] == state]
        if not rows:
            continue
        lines.append(heading)
        lines.append("─" * len(heading) * 2)
        for row in rows:
            lines.append(f"- {row['label_ja']} [{row['id']}]")
            lines.append(f"  owner: {row['owner']} / action: {row['user_action']}")
            if row.get("deadline"):
                lines.append(f"  deadline: {row['deadline']}")
            if row.get("missing_inputs"):
                lines.append(f"  missing: {', '.join(row['missing_inputs'])}")
            if row.get("municipality_specific"):
                lines.append("  note: municipality-specific details must be rechecked locally")
            lines.append(f"  guidance: {row['guidance']}")
            lines.append(
                "  source: " + ", ".join(f"{s['authority']} {s['url']}" for s in row["sources"])
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
