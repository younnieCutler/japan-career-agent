"""Application adapter for the GUI's read-only home and timeline.

The adapter composes existing read models. It does not parse the ledger, create a second state
store, or turn independent readiness dimensions into a score.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from experiences import list_experiences, list_projects, show_project_timeline
from guided_flow import run_guided
from views import evidence_pool, readiness, status, weekly_review


_PRIVATE_KEYS = frozenset({"vault", "path", "pipeline", "workspace"})


def _debug_enabled() -> bool:
    return os.environ.get("JAPAN_CAREER_GUI_DEBUG") == "1"


def _internal_key(key: str) -> bool:
    return key == "id" or key.endswith("_id") or key.endswith("_ids") or key == "ids"


def _public(value: Any, *, debug: bool) -> Any:
    """Drop storage metadata and internal identifiers before data reaches the browser."""
    if isinstance(value, Mapping):
        return {
            str(key): _public(child, debug=debug)
            for key, child in value.items()
            if str(key) not in _PRIVATE_KEYS and (debug or not _internal_key(str(key)))
        }
    if isinstance(value, list):
        return [_public(child, debug=debug) for child in value]
    if isinstance(value, tuple):
        return [_public(child, debug=debug) for child in value]
    return value


def _dimension_rows(readiness_result: Mapping[str, Any]) -> list[dict[str, str]]:
    dimensions = readiness_result.get("dimensions")
    if not isinstance(dimensions, Mapping):
        return []
    return [
        {"name": str(name), "status": str(value)}
        for name, value in dimensions.items()
    ]


def home_payload(
    home: Any, *, workspace: str | None = None, as_of: str | None = None,
) -> dict[str, Any]:
    """Return the read-only Home model from canonical application projections."""
    status_result = status(home, workspace=workspace)
    readiness_result = readiness(home, as_of=as_of)
    effective_as_of = as_of or readiness_result.get("as_of")
    evidence_result = evidence_pool(home, as_of=effective_as_of)
    review_result = weekly_review(home, as_of=effective_as_of)
    experiences_result = list_experiences(home)
    projects_result = list_projects(home)
    guided_result = run_guided(home, workspace=workspace, as_of=effective_as_of)

    guided = guided_result.get("guided") if isinstance(guided_result, Mapping) else {}
    guided = guided if isinstance(guided, Mapping) else {}
    guided_summary = guided.get("summary")
    guided_summary = guided_summary if isinstance(guided_summary, Mapping) else {}
    actions = guided.get("available_actions")
    actions = actions if isinstance(actions, list) else []
    dimensions = _dimension_rows(readiness_result)
    profile = status_result.get("profile") if isinstance(status_result, Mapping) else {}
    profile = profile if isinstance(profile, Mapping) else {}
    state = status_result.get("state") if isinstance(status_result, Mapping) else {}
    state = state if isinstance(state, Mapping) else {}
    case_state = status_result.get("workspace") if isinstance(status_result, Mapping) else {}
    case_state = case_state if isinstance(case_state, Mapping) else {}

    raw = {
        "mode": "home",
        "case": {
            "initialized": guided_summary.get("initialized", False),
            "career_status": profile.get("career_status"),
            "track": profile.get("track"),
            "target_role": profile.get("target_role"),
            "employment_status": profile.get("employment_status"),
            "job_search": profile.get("job_search"),
            "career_mode": state.get("career_mode"),
            "stage": state.get("stage"),
            "company_count": case_state.get("company_count", 0),
            "case_exists": case_state.get("exists", False),
        },
        "status": status_result,
        "readiness": readiness_result,
        "evidence_pool": evidence_result,
        "weekly_review": review_result,
        "guided": guided,
        "confirmed": {
            "dimensions": [row for row in dimensions if row["status"] == "Confirmed"],
            "projects": projects_result.get("projects", []) if isinstance(projects_result, Mapping) else [],
            "experiences": experiences_result.get("experiences", [])
            if isinstance(experiences_result, Mapping) else [],
        },
        "unknown": {
            "dimensions": [row for row in dimensions if row["status"] != "Confirmed"],
            "review_questions": review_result.get("ask_first", [])
            if isinstance(review_result, Mapping) else [],
        },
        "conflicts": {"count": guided_summary.get("conflict_count", 0)},
        "pending_approval": {
            "count": status_result.get("pending_proposals", 0),
            "kind": status_result.get("pending_kind"),
        },
        "next_work": {"actions": actions},
        "no_total_by_design": True,
    }
    return _public(raw, debug=_debug_enabled())


def _period_from(row: Mapping[str, Any]) -> str:
    period = row.get("period")
    if isinstance(period, Mapping):
        return str(period.get("from") or "9999-99-99")
    return "9999-99-99"


def timeline_payload(home: Any, *, as_of: str | None = None) -> dict[str, Any]:
    """Return employment, non-work context, experience, and project time sections."""
    experiences_result = list_experiences(home)
    projects_result = list_projects(home)
    contexts = experiences_result.get("contexts", {}) if isinstance(experiences_result, Mapping) else {}
    experiences = experiences_result.get("experiences", []) if isinstance(experiences_result, Mapping) else []
    projects = projects_result.get("projects", []) if isinstance(projects_result, Mapping) else []
    sections: list[dict[str, Any]] = []

    if isinstance(contexts, Mapping):
        context_rows = contexts.values()
    else:
        context_rows = contexts if isinstance(contexts, list) else []
    for context in context_rows:
        if not isinstance(context, Mapping):
            continue
        sections.append({
            "kind": "context",
            "context_kind": context.get("kind"),
            "label": context.get("external_label") or context.get("label"),
            "period": context.get("period"),
        })

    for experience in experiences:
        if not isinstance(experience, Mapping):
            continue
        context = contexts.get(experience.get("context_id"), {}) if isinstance(contexts, Mapping) else {}
        sections.append({
            "kind": "experience",
            "label": experience.get("label"),
            "period": context.get("period") if isinstance(context, Mapping) else None,
            "evidence_count": len(experience.get("evidence_event_ids", [])),
        })

    for project in projects:
        if not isinstance(project, Mapping) or not project.get("id"):
            continue
        timeline = show_project_timeline(home, str(project["id"]))
        sections.append({
            "kind": "project",
            "label": project.get("external_label") or project.get("title"),
            "status": project.get("status"),
            "period": project.get("period"),
            "entries": timeline.get("timeline", []) if isinstance(timeline, Mapping) else [],
        })

    sections.sort(key=lambda row: (_period_from(row), str(row.get("label") or "")))
    return _public(
        {
            "mode": "timeline",
            "as_of": as_of,
            "sections": sections,
            "read_only": True,
        },
        debug=_debug_enabled(),
    )
