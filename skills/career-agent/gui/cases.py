"""GUI adapter for durable case metadata."""

from __future__ import annotations

from typing import Any

from artifact_store import list_artifacts
from case_store import (
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
    propose_canonical_case,
    restore_case,
)

__all__ = [
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
    "restore_case",
    "propose_canonical_case",
    "approve_canonical_case",
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


def present_review(result: dict[str, Any]) -> dict[str, Any]:
    proposal = result.get("proposal") if isinstance(result.get("proposal"), dict) else {}
    event = proposal.get("event") if isinstance(proposal.get("event"), dict) else {}
    visible_event = {
        key: value
        for key, value in event.items()
        if key in {"experience_context", "project", "evidence"}
    }
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
        "recovered": bool(result.get("recovered")),
    }
