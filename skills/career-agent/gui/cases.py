"""GUI adapter for durable case metadata."""

from __future__ import annotations

from typing import Any

from artifact_store import list_artifacts
from case_store import (
    application_evidence_refs,
    approve_canonical_case,
    archive_case,
    assign_project_context,
    case_path,
    create_application,
    create_career_context,
    create_company,
    create_project,
    delete_case,
    get_case,
    ensure_canonical_context_case,
    ensure_canonical_project_case,
    link_canonical_record,
    link_pending_proposal,
    list_cases,
    propose_career_context_update,
    propose_canonical_case,
    propose_project_update,
    restore_case,
    update_application,
    update_company,
)

__all__ = [
    "application_evidence_refs",
    "archive_case",
    "assign_project_context",
    "case_path",
    "create_application",
    "create_career_context",
    "create_company",
    "create_project",
    "delete_case",
    "get_case",
    "ensure_canonical_context_case",
    "ensure_canonical_project_case",
    "link_canonical_record",
    "link_pending_proposal",
    "list_cases",
    "payload",
    "propose_career_context_update",
    "restore_case",
    "propose_canonical_case",
    "propose_project_update",
    "approve_canonical_case",
    "update_application",
    "update_company",
]


def payload(home: Any) -> dict[str, Any]:
    case_rows = list_cases(home)
    return {
        "mode": "cases",
        "cases": case_rows,
        "artifacts": list_artifacts(home),
        "read_only": False,
        "pipeline_schema_unchanged": True,
        "canonical_write_performed": False,
    }


def present_case(record: dict[str, Any]) -> dict[str, Any]:
    """Return only the visible organizing record and the opaque ref needed to continue."""
    return {
        "ref": record.get("case_id"),
        "label": record.get("label"),
        "status": record.get("lifecycle", record.get("status")),
    }


def _visible_snapshot(kind: str, value: Any) -> dict[str, Any]:
    fields = {
        "experience_context": {"kind", "label", "external_label", "role", "summary", "period"},
        "project": {"title", "external_label", "role", "scope", "summary", "status", "period"},
    }.get(kind, set())
    return {
        key: item
        for key, item in value.items()
        if key in fields
    } if isinstance(value, dict) else {}


def present_review(result: dict[str, Any]) -> dict[str, Any]:
    proposal = result.get("proposal") if isinstance(result.get("proposal"), dict) else {}
    event = proposal.get("event") if isinstance(proposal.get("event"), dict) else {}
    visible_event = {
        key: (dict(value) if isinstance(value, dict) else value)
        for key, value in event.items()
        if key in {"experience_context", "project", "evidence"}
    }
    before = result.get("proposal", {}).get("before") if isinstance(result.get("proposal"), dict) else None
    after = result.get("proposal", {}).get("after") if isinstance(result.get("proposal"), dict) else None
    kind = "experience_context" if "experience_context" in visible_event else "project"
    # The dialog compares before against this, so it has to be the record as it will stand after
    # approval, not the submitted diff. A diff omits every field the form does not carry, and the
    # comparison would then report those untouched fields as being cleared.
    if after is not None:
        visible_event[kind] = _visible_snapshot(kind, after)
    if visible_event.get("evidence") == ["User confirmation in the local Career Agent GUI"]:
        visible_event["evidence"] = ["user_confirmation"]
    for payload in visible_event.values():
        if isinstance(payload, dict):
            payload.pop("id", None)
    return {
        "proposal": {
            "ref": proposal.get("id"),
            "status": proposal.get("status"),
            "event": visible_event,
        },
        "record": present_case(result.get("case", {})),
        "before": _visible_snapshot(kind, before) if before is not None else None,
        "revision": proposal.get("base_revision") or result.get("case", {}).get("updated_at"),
        "recovered": bool(result.get("recovered")),
    }
