"""Application-owned durable case metadata for the local GUI."""

from __future__ import annotations

import re
import uuid
import hashlib
import datetime as dt
from pathlib import Path
from typing import Any

from approvals import approve as approve_canonical
from experiences import add_context, add_project, list_experiences, list_projects
from lifecycle import vault_lock
from models import (
    EXPERIENCE_CONTEXT_KINDS,
    EXTERNAL_USE_STATES,
    WORK_EXPERIENCE_CONTEXT_KINDS,
    CareerError,
)
from persistence import read_json, read_jsonl, write_json
from proposals import review_proposal
from vault import CareerVault, utc_now


DURABLE_GUI_ROOT = ("03-active", "gui")
# A project is a case the user is living through, not one they are applying to. It gets the same
# container as a company so notes, retrospectives and drafts hang off it and stay out of the
# canonical ledger until approval — the point of the project screen is that nothing written while
# the work is happening becomes a career fact by itself.
CASE_KINDS = frozenset({"company", "application", "career_context", "project"})
CASE_STATUSES = frozenset({"active", "archived", "deleted"})
# Derived from CASE_KINDS rather than spelled out again: the two lists disagreeing is exactly how
# adding `project` first failed, with a kind that could be created and then never read back.
CASE_ID = re.compile(rf"^case-(?:{'|'.join(sorted(CASE_KINDS))})-[a-f0-9]{{16}}$")
MAX_LABEL_LENGTH = 240


def context_relationship(context_kind: object) -> str:
    """Return the case hierarchy used for a canonical experience context."""
    return "employer" if context_kind in WORK_EXPERIENCE_CONTEXT_KINDS else "non_work"


def durable_root(home: CareerVault) -> Path:
    """Return the durable GUI root without creating it."""
    return home.path.joinpath(*DURABLE_GUI_ROOT)


def cases_root(home: CareerVault) -> Path:
    return durable_root(home) / "cases"


def case_path(home: CareerVault, case_id: str) -> Path:
    if not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id):
        raise CareerError("invalid case id", code="INVALID_INPUT")
    return cases_root(home) / f"{case_id}.json"


def _text(value: Any, field: str, *, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > MAX_LABEL_LENGTH:
        raise CareerError(f"{field} must be a non-empty short string", code="INVALID_INPUT")
    return value.strip()


def _strings(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise CareerError(f"{field} must be a list of strings", code="INVALID_INPUT")
    result = []
    for item in value:
        text = _text(item, field)
        assert text is not None
        result.append(text)
    return result


def _object(value: Any, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise CareerError(f"{field} must be an object", code="INVALID_INPUT")
    return dict(value)


def _new_id(kind: str) -> str:
    return f"case-{kind}-{uuid.uuid4().hex[:16]}"


def _validate_case(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise CareerError("case record must be an object", code="CASE_INVALID")
    case_id = record.get("case_id")
    if not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id):
        raise CareerError("case record has an invalid id", code="CASE_INVALID")
    if record.get("kind") not in CASE_KINDS:
        raise CareerError("case record has an invalid kind", code="CASE_INVALID")
    if record.get("status") not in CASE_STATUSES:
        raise CareerError("case record has an invalid status", code="CASE_INVALID")
    if record.get("parent_ref") is not None and (
        not isinstance(record["parent_ref"], str) or not CASE_ID.fullmatch(record["parent_ref"])
    ):
        raise CareerError("case.parent_ref is invalid", code="CASE_INVALID")
    if not isinstance(record.get("label"), str) or not record["label"].strip():
        raise CareerError("case.label is required", code="CASE_INVALID")
    if not isinstance(record.get("source_refs"), list) or any(
        not isinstance(item, str) or not item.strip() for item in record["source_refs"]
    ):
        raise CareerError("case.source_refs is invalid", code="CASE_INVALID")
    if not isinstance(record.get("metadata"), dict):
        raise CareerError("case.metadata is invalid", code="CASE_INVALID")
    result = dict(record)
    result["relationship_state"] = (
        "needs_context"
        if record["kind"] == "project" and record.get("parent_ref") is None
        else "linked"
    )
    return result


def _read_case(home: CareerVault, case_id: str) -> dict[str, Any]:
    path = case_path(home, case_id)
    record = read_json(path, None)
    if record is None:
        raise CareerError(f"case not found: {case_id}", code="CASE_NOT_FOUND")
    return _validate_case(record)


def get_case(home: CareerVault, case_id: str) -> dict[str, Any]:
    return _read_case(home, case_id)


def _create(
    home: CareerVault,
    *,
    kind: str,
    label: str,
    parent_ref: str | None,
    metadata: dict[str, Any],
    source_refs: Any,
    case_id: str | None,
) -> dict[str, Any]:
    if kind not in CASE_KINDS:
        raise CareerError("unsupported case kind", code="INVALID_INPUT")
    if kind in {"company", "career_context"} and parent_ref is not None:
        raise CareerError(f"{kind} cases cannot have a parent", code="INVALID_INPUT")
    if kind == "application" and parent_ref is None:
        raise CareerError("application cases require a company parent", code="INVALID_INPUT")
    if kind == "project" and parent_ref is None:
        raise CareerError(
            "project cases require a career context parent",
            code="INVALID_RELATIONSHIP",
        )
    if case_id is None:
        case_id = _new_id(kind)
    else:
        case_path(home, case_id)
        if case_path(home, case_id).exists():
            raise CareerError("case id already exists", code="CASE_EXISTS")
    now = utc_now()
    record = {
        "case_id": case_id,
        "kind": kind,
        "parent_ref": parent_ref,
        "label": _text(label, "label"),
        "status": "active",
        "metadata": _object(metadata, "metadata"),
        "source_refs": _strings(source_refs, "source_refs"),
        "created_at": now,
        "updated_at": now,
    }
    _validate_case(record)
    with vault_lock(home):
        if kind in {"application", "project"}:
            parent = _read_case(home, str(parent_ref))
            expected_kind = "company" if kind == "application" else "career_context"
            if parent["kind"] != expected_kind or parent["status"] != "active":
                raise CareerError(
                    f"{kind} parent must be an active {expected_kind} case",
                    code="INVALID_RELATIONSHIP",
                )
        path = case_path(home, case_id)
        if path.exists():
            raise CareerError("case id already exists", code="CASE_EXISTS")
        write_json(path, record)
    return record


def create_company(
    home: CareerVault,
    label: str,
    *,
    pipeline_slug: str | None = None,
    business: Any = None,
    products: Any = None,
    source_refs: Any = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    metadata = {"pipeline_slug": pipeline_slug, "business": business, "products": products}
    return _create(
        home,
        kind="company",
        label=label,
        parent_ref=None,
        metadata={key: value for key, value in metadata.items() if value is not None},
        source_refs=source_refs,
        case_id=case_id,
    )


def create_application(
    home: CareerVault,
    parent_ref: str,
    label: str,
    *,
    jd: Any = None,
    evidence_refs: Any = None,
    document_kinds: Any = None,
    source_refs: Any = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    metadata = {
        "jd": _object(jd, "jd"),
        "evidence_refs": _strings(evidence_refs, "evidence_refs"),
        "document_kinds": _strings(document_kinds, "document_kinds"),
    }
    return _create(
        home,
        kind="application",
        label=label,
        parent_ref=parent_ref,
        metadata=metadata,
        source_refs=source_refs,
        case_id=case_id,
    )


def create_career_context(
    home: CareerVault,
    label: str,
    *,
    context_kind: str,
    relationship: str,
    context_id: str | None = None,
    role: str | None = None,
    summary: str | None = None,
    period: dict[str, Any] | None = None,
    source_refs: Any = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    """Organize employer and non-work drafts without creating canonical context evidence."""
    if context_kind not in EXPERIENCE_CONTEXT_KINDS:
        raise CareerError("unsupported career context kind", code="INVALID_INPUT")
    if relationship not in {"employer", "non_work"}:
        raise CareerError("relationship must be employer or non_work", code="INVALID_INPUT")
    if relationship != context_relationship(context_kind):
        raise CareerError(
            "career context kind and relationship do not match",
            code="INVALID_RELATIONSHIP",
        )
    metadata = {
        "context_kind": context_kind,
        "relationship": relationship,
        "role": _text(role, "role", required=False),
        "summary": _text(summary, "summary", required=False),
        "period": _object(period, "period") if period is not None else None,
    }
    if context_id is not None:
        metadata["context_id"] = _text(context_id, "context_id")
    return _create(
        home,
        kind="career_context",
        label=label,
        parent_ref=None,
        metadata={key: value for key, value in metadata.items() if value is not None},
        source_refs=source_refs,
        case_id=case_id,
    )


def create_project(
    home: CareerVault,
    parent_ref: str,
    label: str,
    *,
    project_id: str | None = None,
    external_use: str | None = None,
    role: str | None = None,
    scope: str | None = None,
    summary: str | None = None,
    period: dict[str, Any] | None = None,
    evidence_refs: Any = None,
    source_refs: Any = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    """A case for work in progress. `project_id` links it to the confirmed project projection."""
    if external_use is not None and external_use not in EXTERNAL_USE_STATES:
        raise CareerError(
            f"external_use must be one of: {', '.join(sorted(EXTERNAL_USE_STATES))}",
            code="INVALID_INPUT",
        )
    metadata = {
        "project_id": project_id,
        # Whether this may leave the vault is the user's answer, not an inference. Unknown until
        # they say, and unknown is what keeps it out of the documents a company sees.
        "external_use": external_use or "unknown",
        "evidence_refs": _strings(evidence_refs, "evidence_refs"),
        "role": _text(role, "role", required=False),
        "scope": _text(scope, "scope", required=False),
        "summary": _text(summary, "summary", required=False),
        "period": _object(period, "period") if period is not None else None,
    }
    return _create(
        home,
        kind="project",
        label=label,
        parent_ref=parent_ref,
        metadata={key: value for key, value in metadata.items() if value is not None},
        source_refs=source_refs,
        case_id=case_id,
    )


def _canonical_case_id(kind: str, canonical_id: str) -> str:
    digest = hashlib.sha256(f"{kind}:{canonical_id}".encode("utf-8")).hexdigest()[:16]
    return f"case-{kind}-{digest}"


def ensure_canonical_context_case(home: CareerVault, context_id: str) -> dict[str, Any]:
    """Create organizing metadata for readable pre-GUI canonical history, idempotently."""
    contexts = list_experiences(home).get("contexts", {})
    context = contexts.get(context_id) if isinstance(contexts, dict) else None
    if not isinstance(context, dict):
        raise CareerError("confirmed career context was not found", code="CONTEXT_NOT_FOUND")
    existing = next(
        (
            row for row in list_cases(home, kind="career_context")
            if row["metadata"].get("context_id") == context_id
        ),
        None,
    )
    if existing is not None:
        return existing
    try:
        return create_career_context(
            home,
            str(context.get("external_label") or context.get("label")),
            context_kind=str(context.get("kind") or "other"),
            relationship=context_relationship(context.get("kind")),
            context_id=context_id,
            role=context.get("role"),
            summary=context.get("summary"),
            period=context.get("period"),
            case_id=_canonical_case_id("career_context", context_id),
        )
    except CareerError as exc:
        if exc.code != "CASE_EXISTS":
            raise
        record = get_case(home, _canonical_case_id("career_context", context_id))
        if record["metadata"].get("context_id") != context_id:
            raise CareerError("canonical context organizer collision", code="REVISION_STALE")
        return record


def ensure_canonical_project_case(
    home: CareerVault, context_id: str, project_id: str, *, explicit_selection: bool = False
) -> dict[str, Any]:
    """Attach a confirmed legacy project to its proven context without rewriting the ledger."""
    experience_view = list_experiences(home)
    linked_contexts = {
        str(row["context_id"])
        for row in experience_view.get("claims", [])
        if isinstance(row, dict)
        and row.get("project_id") == project_id
        and row.get("context_id")
    }
    if linked_contexts and linked_contexts != {context_id}:
        raise CareerError(
            "confirmed project evidence belongs to another career context",
            code="INVALID_RELATIONSHIP",
        )
    if not linked_contexts and not explicit_selection:
        raise CareerError(
            "confirmed project is not supported by this career context",
            code="INVALID_RELATIONSHIP",
        )
    if linked_contexts and context_id not in linked_contexts:
        raise CareerError(
            "confirmed project is not supported by this career context",
            code="INVALID_RELATIONSHIP",
        )
    projects = list_projects(home).get("projects", [])
    project = next(
        (row for row in projects if isinstance(row, dict) and row.get("id") == project_id),
        None,
    )
    if project is None:
        raise CareerError("confirmed project was not found", code="PROJECT_NOT_FOUND")
    context_case = ensure_canonical_context_case(home, context_id)
    existing = next(
        (
            row for row in list_cases(home, kind="project")
            if row["metadata"].get("project_id") == project_id
        ),
        None,
    )
    if existing is not None:
        if existing.get("parent_ref") is None and explicit_selection:
            return assign_project_context(
                home,
                existing["case_id"],
                context_case["case_id"],
                expected_updated_at=existing["updated_at"],
            )
        if existing.get("parent_ref") != context_case["case_id"]:
            raise CareerError(
                "confirmed project is organized under another career context",
                code="INVALID_RELATIONSHIP",
            )
        return existing
    try:
        return create_project(
            home,
            context_case["case_id"],
            str(project.get("external_label") or project.get("title")),
            project_id=project_id,
            role=project.get("role"),
            scope=project.get("scope"),
            summary=project.get("summary"),
            period=project.get("period"),
            case_id=_canonical_case_id("project", project_id),
        )
    except CareerError as exc:
        if exc.code != "CASE_EXISTS":
            raise
        record = get_case(home, _canonical_case_id("project", project_id))
        if record["metadata"].get("project_id") != project_id:
            raise CareerError("canonical project organizer collision", code="REVISION_STALE")
        return record


def assign_project_context(
    home: CareerVault,
    project_case_id: str,
    context_case_id: str,
    *,
    expected_updated_at: str,
) -> dict[str, Any]:
    """Repair a legacy parentless project with optimistic and canonical-context checks."""
    if not isinstance(expected_updated_at, str) or not expected_updated_at:
        raise CareerError("expected_updated_at is required", code="INVALID_INPUT")
    with vault_lock(home):
        project = _read_case(home, project_case_id)
        context = _read_case(home, context_case_id)
        if project["kind"] != "project" or context["kind"] != "career_context":
            raise CareerError(
                "a project can only be connected to a career context",
                code="INVALID_RELATIONSHIP",
            )
        if project["updated_at"] != expected_updated_at:
            raise CareerError(
                "this project changed in another entrypoint",
                code="REVISION_STALE",
                retryable=True,
            )
        if project.get("parent_ref") is not None:
            if project["parent_ref"] == context_case_id:
                return project
            raise CareerError(
                "this project is already connected to another career context",
                code="REVISION_STALE",
                retryable=True,
            )
        if project["status"] != "active" or context["status"] != "active":
            raise CareerError(
                "restore the project and career context before connecting them",
                code="INVALID_RELATIONSHIP",
            )
        project_id = project["metadata"].get("project_id")
        if project_id:
            context_id = context["metadata"].get("context_id")
            if not context_id:
                raise CareerError(
                    "confirm the career context before connecting this confirmed project",
                    code="PARENT_NOT_CONFIRMED",
                )
            linked_contexts = {
                str(row["context_id"])
                for row in list_experiences(home).get("claims", [])
                if isinstance(row, dict)
                and row.get("project_id") == project_id
                and row.get("context_id")
            }
            if linked_contexts and linked_contexts != {context_id}:
                raise CareerError(
                    "confirmed project evidence belongs to another career context",
                    code="INVALID_RELATIONSHIP",
                )
        project["parent_ref"] = context_case_id
        project["updated_at"] = _next_updated_at(project["updated_at"])
        _validate_case(project)
        write_json(case_path(home, project_case_id), project)
        return project


def list_cases(
    home: CareerVault,
    *,
    kind: str | None = None,
    include_archived: bool = True,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    if kind is not None and kind not in CASE_KINDS:
        raise CareerError("unsupported case kind", code="INVALID_INPUT")
    proposals = {
        row.get("id"): row.get("status")
        for row in read_jsonl(home.proposals)
        if isinstance(row.get("id"), str)
    }
    rows: list[dict[str, Any]] = []
    for path in sorted(cases_root(home).glob("case-*.json")):
        record = _validate_case(read_json(path, None))
        if kind is not None and record["kind"] != kind:
            continue
        if record["status"] == "deleted" and not include_deleted:
            continue
        if record["status"] == "archived" and not include_archived:
            continue
        if record["kind"] in {"career_context", "project"}:
            canonical_field = "context_id" if record["kind"] == "career_context" else "project_id"
            if record["status"] == "archived":
                lifecycle = "archived"
            elif record["metadata"].get(canonical_field):
                lifecycle = "approved"
            elif proposals.get(record["metadata"].get("proposal_id")) == "pending":
                lifecycle = "review_pending"
            else:
                lifecycle = "draft"
            record = {**record, "lifecycle": lifecycle}
        rows.append(record)
    return sorted(rows, key=lambda item: (item["kind"], item["label"].casefold(), item["case_id"]))


def link_canonical_record(
    home: CareerVault,
    case_id: str,
    *,
    canonical_id: str,
    proposal_id: str,
) -> dict[str, Any]:
    """Attach an approved context/project id to its organizing case.

    The case remains metadata. The id points at the append-only ledger record; it never copies or
    replaces canonical evidence.
    """
    canonical_id = _text(canonical_id, "canonical_id")
    proposal_id = _text(proposal_id, "proposal_id")
    assert canonical_id is not None and proposal_id is not None
    with vault_lock(home):
        record = _read_case(home, case_id)
        field = {"career_context": "context_id", "project": "project_id"}.get(record["kind"])
        if field is None:
            raise CareerError(
                "only career context and project cases can link canonical records",
                code="INVALID_RELATIONSHIP",
            )
        existing = record["metadata"].get(field)
        if existing not in (None, canonical_id):
            raise CareerError(
                "case already links a different canonical record",
                code="REVISION_STALE",
                retryable=True,
            )
        bound_proposal = record["metadata"].get("proposal_id")
        if bound_proposal not in {None, proposal_id}:
            raise CareerError(
                "case is reviewing a different proposal",
                code="REVISION_STALE",
                retryable=True,
            )
        record["metadata"] = {
            **record["metadata"],
            field: canonical_id,
            "proposal_id": proposal_id,
        }
        record["updated_at"] = _next_updated_at(record["updated_at"])
        _validate_case(record)
        write_json(case_path(home, case_id), record)
    return record


def link_pending_proposal(
    home: CareerVault,
    case_id: str,
    proposal_id: str,
    *,
    expected_proposal_id: str | None = None,
) -> dict[str, Any]:
    proposal_id = _text(proposal_id, "proposal_id")
    assert proposal_id is not None
    with vault_lock(home):
        record = _read_case(home, case_id)
        if record["kind"] not in {"career_context", "project"}:
            raise CareerError(
                "only career context and project cases have canonical proposals",
                code="INVALID_RELATIONSHIP",
            )
        if record["metadata"].get("proposal_id") != expected_proposal_id:
            raise CareerError(
                "this career record changed in another entrypoint",
                code="REVISION_STALE",
                retryable=True,
            )
        record["metadata"] = {**record["metadata"], "proposal_id": proposal_id}
        record["updated_at"] = _next_updated_at(record["updated_at"])
        _validate_case(record)
        write_json(case_path(home, case_id), record)
    return record


def _set_status(
    home: CareerVault,
    case_id: str,
    status: str,
    *,
    expected_updated_at: str | None = None,
) -> dict[str, Any]:
    if status not in {"archived", "deleted"}:
        raise CareerError("unsupported case status", code="INVALID_INPUT")
    with vault_lock(home):
        record = _read_case(home, case_id)
        if expected_updated_at is not None and record["updated_at"] != expected_updated_at:
            raise CareerError(
                "this record changed in another entrypoint",
                code="REVISION_STALE",
                retryable=True,
            )
        canonical_field = {
            "career_context": "context_id",
            "project": "project_id",
        }.get(record["kind"])
        if canonical_field and record["metadata"].get(canonical_field):
            raise CareerError(
                "confirmed career history cannot be archived or deleted",
                code="CASE_ALREADY_CONFIRMED",
            )
        if status in {"archived", "deleted"} and any(
            child.get("parent_ref") == case_id and child.get("status") == "active"
            for child in list_cases(home)
        ):
            raise CareerError(
                "archive active child records first",
                code="CASE_HAS_ACTIVE_CHILDREN",
            )
        record["status"] = status
        record["updated_at"] = _next_updated_at(record["updated_at"])
        _validate_case(record)
        write_json(case_path(home, case_id), record)
    return record


def archive_case(
    home: CareerVault, case_id: str, *, expected_updated_at: str | None = None
) -> dict[str, Any]:
    return _set_status(home, case_id, "archived", expected_updated_at=expected_updated_at)


def restore_case(
    home: CareerVault, case_id: str, *, expected_updated_at: str | None = None
) -> dict[str, Any]:
    with vault_lock(home):
        record = _read_case(home, case_id)
        if expected_updated_at is not None and record["updated_at"] != expected_updated_at:
            raise CareerError(
                "this record changed in another entrypoint",
                code="REVISION_STALE",
                retryable=True,
            )
        if record["status"] == "deleted":
            raise CareerError(
                "a deleted case cannot be restored through the archive action",
                code="INVALID_INPUT",
            )
        record["status"] = "active"
        record["updated_at"] = _next_updated_at(record["updated_at"])
        _validate_case(record)
        write_json(case_path(home, case_id), record)
    return record


def delete_case(home: CareerVault, case_id: str) -> dict[str, Any]:
    """Tombstone metadata; canonical evidence and artifact bodies remain untouched."""
    return _set_status(home, case_id, "deleted")


def propose_canonical_case(home: CareerVault, case_id: str) -> dict[str, Any]:
    """Prepare the exact context/project snapshot the user can approve."""
    record = get_case(home, case_id)
    if record["status"] != "active":
        raise CareerError("restore this record before review", code="INVALID_RELATIONSHIP")
    if record["kind"] not in {"career_context", "project"}:
        raise CareerError("this record is not part of career history", code="INVALID_RELATIONSHIP")
    canonical_field = "context_id" if record["kind"] == "career_context" else "project_id"
    if record["metadata"].get(canonical_field):
        raise CareerError("this record is already confirmed", code="CASE_ALREADY_CONFIRMED")
    pending_id = record["metadata"].get("proposal_id")
    if not pending_id:
        orphaned = [
            row
            for row in read_jsonl(home.proposals)
            if row.get("case_ref") == case_id and row.get("status") in {"pending", "approved"}
        ]
        if orphaned:
            pending_id = orphaned[-1]["id"]
            record = link_pending_proposal(
                home,
                case_id,
                str(pending_id),
                expected_proposal_id=None,
            )
    if pending_id:
        reviewed = review_proposal(home, str(pending_id))
        if reviewed["proposal"].get("status") == "pending":
            return {**reviewed, "case": record}
        if reviewed["proposal"].get("status") == "approved":
            recovered = approve_canonical_case(home, case_id, str(pending_id))
            return {**reviewed, "case": recovered["case"], "recovered": True}

    metadata = record["metadata"]
    fields = {
        key: metadata.get(key)
        for key in ("role", "scope", "summary", "period")
        if metadata.get(key) not in (None, {})
    }
    evidence = ["User confirmation in the local Career Agent GUI"]
    if record["kind"] == "career_context":
        created = add_context(
            home,
            str(metadata["context_kind"]),
            record["label"],
            evidence=evidence,
            case_ref=case_id,
            **{key: value for key, value in fields.items() if key != "scope"},
        )
    else:
        parent = get_case(home, str(record["parent_ref"]))
        if not parent["metadata"].get("context_id"):
            raise CareerError(
                "confirm the career context before confirming its project",
                code="PARENT_NOT_CONFIRMED",
            )
        created = add_project(
            home,
            record["label"],
            evidence=evidence,
            case_ref=case_id,
            **fields,
        )
    proposal_id = created["proposal"]["id"]
    linked = link_pending_proposal(
        home,
        case_id,
        proposal_id,
        expected_proposal_id=str(pending_id) if pending_id else None,
    )
    return {**review_proposal(home, proposal_id), "case": linked}


def approve_canonical_case(home: CareerVault, case_id: str, proposal_id: str) -> dict[str, Any]:
    """Approve only the proposal bound to this organizing case, then link its ledger id."""
    record = get_case(home, case_id)
    if record["status"] != "active":
        raise CareerError("restore this record before approval", code="INVALID_RELATIONSHIP")
    if record["metadata"].get("proposal_id") != proposal_id:
        raise CareerError("proposal does not belong to this career record", code="INVALID_INPUT")
    reviewed = review_proposal(home, proposal_id)["proposal"]
    if reviewed.get("case_ref") != case_id:
        raise CareerError("proposal does not belong to this career record", code="INVALID_INPUT")
    if reviewed.get("status") == "approved":
        event_id = reviewed.get("approved_event_id")
        event = next((row for row in read_jsonl(home.events) if row.get("id") == event_id), None)
        if event is None:
            raise CareerError(
                "approved proposal has no canonical event",
                code="APPROVAL_RECOVERY_FAILED",
            )
        result = {"approved": True, "idempotent": True, "event": event, "proposal": reviewed}
    else:
        def approval_precondition() -> None:
            current = get_case(home, case_id)
            if current["metadata"].get("proposal_id") != proposal_id:
                raise CareerError(
                    "this career record changed in another entrypoint",
                    code="REVISION_STALE",
                    retryable=True,
                )
            current_proposal = review_proposal(home, proposal_id)["proposal"]
            if current_proposal.get("case_ref") != case_id:
                raise CareerError(
                    "proposal does not belong to this career record",
                    code="INVALID_INPUT",
                )

        result = approve_canonical(home, proposal_id, precondition=approval_precondition)
        event = result["event"]
    key = "experience_context" if record["kind"] == "career_context" else "project"
    payload = event.get(key)
    if not isinstance(payload, dict) or not payload.get("id"):
        raise CareerError("approved event does not match its career record", code="PROPOSAL_INVALID")
    linked = link_canonical_record(
        home,
        case_id,
        canonical_id=str(payload["id"]),
        proposal_id=proposal_id,
    )
    return {**result, "case": linked}

def _next_updated_at(previous: str) -> str:
    """Return a timestamp that can safely serve as an optimistic-concurrency token."""
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    try:
        prior = dt.datetime.fromisoformat(previous.replace("Z", "+00:00"))
        if prior.tzinfo is None:
            prior = prior.replace(tzinfo=dt.timezone.utc)
        if now <= prior:
            now = prior + dt.timedelta(seconds=1)
    except ValueError:
        pass
    return now.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
