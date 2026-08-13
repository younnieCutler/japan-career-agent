"""Application adapter for the GUI's read-only home and timeline.

The adapter composes existing read models. It does not parse the ledger, create a second state
store, or turn independent readiness dimensions into a score.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from artifact_store import list_artifacts
from case_store import context_relationship, list_cases
from experiences import list_experiences, list_projects, show_project_timeline
from guided_flow import run_guided
from sessions import list_sessions
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


def projects_payload(home: Any) -> dict[str, Any]:
    """Return project references together with the user's declared employment state."""
    status_result = status(home)
    profile = status_result.get("profile") if isinstance(status_result, Mapping) else {}
    profile = profile if isinstance(profile, Mapping) else {}
    projects_result = list_projects(home)
    project_rows = projects_result.get("projects", []) if isinstance(projects_result, Mapping) else []
    projects: list[dict[str, Any]] = []
    for project in project_rows:
        if not isinstance(project, Mapping) or not project.get("id"):
            continue
        timeline_result = show_project_timeline(home, str(project["id"]))
        timeline = timeline_result.get("timeline", []) if isinstance(timeline_result, Mapping) else []
        projects.append({**project, "timeline": timeline})

    raw = {
        "mode": "projects",
        "employment": {
            "career_status": profile.get("career_status"),
            "employment_status": profile.get("employment_status", "unknown"),
            "job_search": profile.get("job_search"),
            "target_role": profile.get("target_role"),
        },
        "projects": projects,
        "read_only": True,
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
    experiences = experiences_result.get("claims", []) if isinstance(experiences_result, Mapping) else []
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
        confidential = bool(experience.get("contains_confidential"))
        sections.append({
            "kind": "experience",
            "label": None if confidential else experience.get("label"),
            "contains_confidential": confidential,
            "period": (
                {"from": experience.get("work_date"), "to": experience.get("work_date")}
                if experience.get("work_date")
                else context.get("period") if isinstance(context, Mapping) else None
            ),
            "evidence_count": experience.get(
                "material_evidence_count", experience.get("evidence_count", 0)
            ),
        })

    for project in projects:
        if not isinstance(project, Mapping) or not project.get("id"):
            continue
        sections.append({
            "kind": "project",
            "label": project.get("external_label") or project.get("title"),
            "status": project.get("status"),
            "period": project.get("period"),
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


def _case_public(row: Mapping[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    return {
        "ref": row.get("case_id"),
        "label": row.get("label"),
        "lifecycle": row.get("lifecycle", row.get("status")),
        "period": metadata.get("period"),
        "role": metadata.get("role"),
        "summary": metadata.get("summary"),
        "relationship_state": row.get("relationship_state"),
        "updated_at": row.get("updated_at"),
    }


def _session_public(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "session_ref": row.get("session_id"),
        "workflow": row.get("workflow"),
        "stage": row.get("stage"),
        "lifecycle": row.get("status"),
        "context": row.get("display_context", []),
        "remaining": row.get("remaining_work", []),
        "updated_at": row.get("updated_at"),
        "revision": row.get("revision"),
        "last_entrypoint": row.get("last_entrypoint"),
    }


def _experience_public(row: Mapping[str, Any]) -> dict[str, Any]:
    detail = row.get("detail") if isinstance(row.get("detail"), Mapping) else {}
    evidence_count = row.get("material_evidence_count", row.get("evidence_count", 0))
    return {
        "ref": row.get("claim_id"),
        "label": row.get("label"),
        "kind": row.get("kind"),
        "lifecycle": "approved",
        "work_date": row.get("work_date"),
        "evidence_count": evidence_count,
        "evidence_state": "present" if evidence_count else "missing",
        "contribution_state": "present" if row.get("individual_contribution") else "missing",
        "detail": dict(detail) if not row.get("contains_confidential") else {},
        "contains_confidential": bool(row.get("contains_confidential")),
        "external_use": row.get("external_use"),
    }


def career_overview_payload(home: Any) -> dict[str, Any]:
    """One navigable context → project → experience model over drafts and canonical history."""
    cases = list_cases(home)
    context_cases = [row for row in cases if row["kind"] == "career_context"]
    project_cases = [row for row in cases if row["kind"] == "project"]
    session_rows = list_sessions(home)["sessions"]
    sessions_by_case: dict[str, list[dict[str, Any]]] = {}
    for row in session_rows:
        case_ref = row.get("case_ref")
        if isinstance(case_ref, str):
            sessions_by_case.setdefault(case_ref, []).append(_session_public(row))

    experience_result = list_experiences(home)
    canonical_contexts = experience_result.get("contexts", {})
    canonical_contexts = canonical_contexts if isinstance(canonical_contexts, Mapping) else {}
    canonical_experiences = experience_result.get("claims", [])
    canonical_experiences = canonical_experiences if isinstance(canonical_experiences, list) else []
    canonical_projects_result = list_projects(home)
    canonical_projects = canonical_projects_result.get("projects", [])
    canonical_projects = canonical_projects if isinstance(canonical_projects, list) else []
    projects_by_id = {
        str(row.get("id")): row
        for row in canonical_projects
        if isinstance(row, Mapping) and row.get("id")
    }
    project_case_by_id = {
        str(row["metadata"].get("project_id")): row
        for row in project_cases
        if row["metadata"].get("project_id")
    }
    contexts: list[dict[str, Any]] = []
    relationship_conflicts: list[dict[str, Any]] = []
    seen_context_ids: set[str] = set()
    seen_project_ids: set[str] = set()
    displayed_canonical_projects: set[str] = set()
    for context_case in context_cases:
        context = _case_public(context_case)
        metadata = context_case["metadata"]
        context_id = metadata.get("context_id")
        canonical = canonical_contexts.get(context_id, {}) if context_id else {}
        if context_id:
            seen_context_ids.add(str(context_id))
        context.update({
            "kind": metadata.get("context_kind"),
            "relationship": metadata.get("relationship"),
            "label": canonical.get("external_label") or canonical.get("label") or context["label"],
            "period": canonical.get("period") or context["period"],
            "projects": [],
            "other_experiences": [],
        })
        for project_case in project_cases:
            if project_case.get("parent_ref") != context_case["case_id"]:
                continue
            project = _case_public(project_case)
            project_id = project_case["metadata"].get("project_id")
            canonical_project = projects_by_id.get(str(project_id), {}) if project_id else {}
            if project_id:
                seen_project_ids.add(str(project_id))
                displayed_canonical_projects.add(str(project_id))
            project_experiences = [
                row
                for row in canonical_experiences
                if isinstance(row, Mapping)
                and project_id
                and row.get("project_id") == project_id
            ]
            relationship_conflict = any(
                row.get("context_id") not in {None, context_id}
                for row in project_experiences
            )
            for row in project_experiences:
                actual_context_id = row.get("context_id")
                if actual_context_id in {None, context_id}:
                    continue
                actual = canonical_contexts.get(actual_context_id, {})
                relationship_conflicts.append({
                    "project_ref": project_case["case_id"],
                    "project_label": project_case["label"],
                    "recorded_context": context["label"],
                    "actual_context": actual.get("external_label") or actual.get("label"),
                    "experience": _experience_public(row),
                })
            project.update({
                "label": canonical_project.get("external_label") or canonical_project.get("title") or project["label"],
                "period": canonical_project.get("period") or project["period"],
                "status": canonical_project.get("status"),
                "experiences": [
                    _experience_public(row)
                    for row in project_experiences
                    if row.get("context_id") in {None, context_id}
                ],
                "work": sessions_by_case.get(str(project_case["case_id"]), []),
                "relationship_conflict": relationship_conflict,
            })
            context["projects"].append(project)
        context_project_ids = sorted({
            str(row["project_id"])
            for row in canonical_experiences
            if isinstance(row, Mapping)
            and row.get("context_id") == context_id
            and row.get("project_id")
        })
        for project_id in context_project_ids:
            if project_id in project_case_by_id:
                continue
            canonical_project = projects_by_id.get(project_id, {})
            project_claims = [
                row for row in canonical_experiences
                if isinstance(row, Mapping)
                and row.get("context_id") == context_id
                and str(row.get("project_id") or "") == project_id
            ]
            context["projects"].append({
                "ref": f"canonical:{project_id}",
                "label": canonical_project.get("external_label") or canonical_project.get("title"),
                "lifecycle": "approved",
                "period": canonical_project.get("period"),
                "role": canonical_project.get("role"),
                "summary": canonical_project.get("summary"),
                "relationship_state": "canonical_only",
                "updated_at": None,
                "status": canonical_project.get("status"),
                "experiences": [_experience_public(row) for row in project_claims],
                "work": [],
                "relationship_conflict": False,
            })
            displayed_canonical_projects.add(project_id)
        context["other_experiences"] = [
            _experience_public(row)
            for row in canonical_experiences
            if isinstance(row, Mapping)
            and context_id
            and row.get("context_id") == context_id
            and not row.get("project_id")
        ]
        contexts.append(context)

    for context_id, canonical in canonical_contexts.items():
        if str(context_id) in seen_context_ids or not isinstance(canonical, Mapping):
            continue
        context = {
            "ref": f"canonical:{context_id}",
            "label": canonical.get("external_label") or canonical.get("label"),
            "kind": canonical.get("kind"),
            "relationship": context_relationship(canonical.get("kind")),
            "lifecycle": "approved",
            "period": canonical.get("period"),
            "role": canonical.get("role"),
            "summary": canonical.get("summary"),
            "relationship_state": "canonical_only",
            "updated_at": None,
            "projects": [],
            "other_experiences": [
                _experience_public(row)
                for row in canonical_experiences
                if isinstance(row, Mapping)
                and row.get("context_id") == context_id
                and not row.get("project_id")
            ],
        }
        context_project_ids = sorted({
            str(row["project_id"])
            for row in canonical_experiences
            if isinstance(row, Mapping)
            and row.get("context_id") == context_id
            and row.get("project_id")
        })
        for project_id in context_project_ids:
            if project_id in seen_project_ids:
                continue
            canonical_project = projects_by_id.get(project_id, {})
            project_claims = [
                row for row in canonical_experiences
                if isinstance(row, Mapping)
                and row.get("context_id") == context_id
                and str(row.get("project_id") or "") == project_id
            ]
            context["projects"].append({
                "ref": f"canonical:{project_id}",
                "label": canonical_project.get("external_label") or canonical_project.get("title"),
                "lifecycle": "approved",
                "period": canonical_project.get("period"),
                "role": canonical_project.get("role"),
                "summary": canonical_project.get("summary"),
                "relationship_state": "canonical_only",
                "updated_at": None,
                "status": canonical_project.get("status"),
                "experiences": [_experience_public(row) for row in project_claims],
                "work": [],
            })
            seen_project_ids.add(project_id)
            displayed_canonical_projects.add(project_id)
        contexts.append(context)

    unassigned_projects = [
        {
            **_case_public(row),
            "work": sessions_by_case.get(str(row["case_id"]), []),
        }
        for row in project_cases
        if row.get("parent_ref") is None
    ] + [
        {
            "ref": f"canonical:{project_id}",
            "label": row.get("external_label") or row.get("title"),
            "lifecycle": "approved",
            "period": row.get("period"),
            "role": row.get("role"),
            "summary": row.get("summary"),
            "relationship_state": "needs_context",
            "updated_at": None,
            "work": [],
        }
        for project_id, row in projects_by_id.items()
        if project_id not in displayed_canonical_projects
    ]
    unassigned_work = [
        _session_public(row) for row in session_rows if not row.get("case_ref")
    ]
    all_projects = [project for context in contexts for project in context["projects"]]
    all_experiences = [
        experience
        for context in contexts
        for project in context["projects"]
        for experience in project["experiences"]
    ] + [experience for context in contexts for experience in context["other_experiences"]]
    lifecycle_rows = [context["lifecycle"] for context in contexts] + [
        project["lifecycle"] for project in all_projects
    ] + [work["lifecycle"] for row in sessions_by_case.values() for work in row]
    return {
        "mode": "career-overview",
        "summary": {
            "contexts": len(contexts),
            "projects": len(all_projects),
            "experiences": len(all_experiences),
            "draft": lifecycle_rows.count("draft"),
            "review_pending": lifecycle_rows.count("review_pending"),
            "approved": lifecycle_rows.count("approved") + len(all_experiences),
        },
        "contexts": contexts,
        "unassigned_projects": unassigned_projects,
        "unassigned_work": unassigned_work,
        "relationship_conflicts": relationship_conflicts,
        "read_only_projection": True,
    }


def applications_payload(home: Any) -> dict[str, Any]:
    """Present target companies and positions without exposing case/artifact vocabulary."""
    cases = list_cases(home)
    companies = [row for row in cases if row["kind"] == "company"]
    applications = [row for row in cases if row["kind"] == "application"]
    artifacts = list_artifacts(home)
    result = []
    for company in companies:
        positions = []
        for application in applications:
            if application.get("parent_ref") != company["case_id"]:
                continue
            attached = [row for row in artifacts if row.get("case_ref") == application["case_id"]]
            metadata = application.get("metadata", {})
            positions.append({
                "ref": application["case_id"],
                "label": application["label"],
                "status": application["status"],
                "updated_at": application.get("updated_at"),
                "jd": metadata.get("jd", {}),
                "selected_evidence_count": len(metadata.get("evidence_refs", [])),
                "documents": [
                    {
                        "ref": row.get("artifact_id"),
                        "type": row.get("kind"),
                        "status": row.get("status"),
                        "version": row.get("version"),
                        "evidence_count": len(row.get("evidence_refs", [])),
                        "updated_at": row.get("updated_at") or row.get("created_at"),
                    }
                    for row in attached
                ],
            })
        result.append({
            "ref": company["case_id"],
            "label": company["label"],
            "status": company["status"],
            "updated_at": company.get("updated_at"),
            "positions": positions,
        })
    experience_result = list_experiences(home)
    context_rows = experience_result.get("contexts", {})
    context_rows = context_rows if isinstance(context_rows, Mapping) else {}
    evidence_options = []
    for claim in experience_result.get("claims", []):
        if not isinstance(claim, Mapping):
            continue
        context = context_rows.get(claim.get("context_id"), {})
        context = context if isinstance(context, Mapping) else {}
        confidential = bool(claim.get("contains_confidential"))
        external_use = claim.get("external_use")
        sharing = "available"
        if confidential and external_use != "allowed":
            sharing = "blocked" if external_use == "blocked" else "review_required"
        evidence_options.append({
            # A confidential claim can be explicitly approved for external reuse without making
            # its private narrative appropriate for every application-list summary.
            "label": None if confidential else claim.get("label"),
            "context": context.get("external_label") or context.get("label"),
            "work_date": claim.get("work_date"),
            "refs": [claim.get("claim_id")],
            "sharing": sharing,
            "contains_confidential": confidential,
        })
    evidence_options.sort(
        key=lambda row: (str(row.get("context") or ""), str(row.get("label") or ""))
    )
    return {
        "mode": "applications",
        "companies": result,
        "evidence_options": evidence_options,
        "read_only": False,
    }


def documents_payload(home: Any) -> dict[str, Any]:
    applications = applications_payload(home)["companies"]
    rows = []
    for company in applications:
        for position in company["positions"]:
            for document in position["documents"]:
                rows.append({
                    **document,
                    "company": company["label"],
                    "position": position["label"],
                })
    return {"mode": "documents", "documents": rows, "read_only": True}
