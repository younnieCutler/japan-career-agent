"""Application-owned durable case metadata for the local GUI."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from lifecycle import vault_lock
from models import EXTERNAL_USE_STATES, CareerError
from persistence import read_json, write_json
from vault import CareerVault, utc_now


DURABLE_GUI_ROOT = ("03-active", "gui")
# A project is a case the user is living through, not one they are applying to. It gets the same
# container as a company so notes, retrospectives and drafts hang off it and stay out of the
# canonical ledger until approval — the point of the project screen is that nothing written while
# the work is happening becomes a career fact by itself.
CASE_KINDS = frozenset({"company", "application", "project"})
CASE_STATUSES = frozenset({"active", "archived", "deleted"})
# Derived from CASE_KINDS rather than spelled out again: the two lists disagreeing is exactly how
# adding `project` first failed, with a kind that could be created and then never read back.
CASE_ID = re.compile(rf"^case-(?:{'|'.join(sorted(CASE_KINDS))})-[a-f0-9]{{16}}$")
MAX_LABEL_LENGTH = 240


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
    return dict(record)


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
    if kind in {"company", "project"} and parent_ref is not None:
        raise CareerError(f"{kind} cases cannot have a parent", code="INVALID_INPUT")
    if kind == "application":
        if parent_ref is None:
            raise CareerError("application cases require a company parent", code="INVALID_INPUT")
        parent = _read_case(home, parent_ref)
        if parent["kind"] != "company" or parent["status"] == "deleted":
            raise CareerError("application parent must be an existing company case", code="INVALID_INPUT")
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


def create_project(
    home: CareerVault,
    label: str,
    *,
    project_id: str | None = None,
    external_use: str | None = None,
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
    }
    return _create(
        home,
        kind="project",
        label=label,
        parent_ref=None,
        metadata={key: value for key, value in metadata.items() if value is not None},
        source_refs=source_refs,
        case_id=case_id,
    )


def list_cases(
    home: CareerVault,
    *,
    kind: str | None = None,
    include_archived: bool = True,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    if kind is not None and kind not in CASE_KINDS:
        raise CareerError("unsupported case kind", code="INVALID_INPUT")
    rows: list[dict[str, Any]] = []
    for path in sorted(cases_root(home).glob("case-*.json")):
        record = _validate_case(read_json(path, None))
        if kind is not None and record["kind"] != kind:
            continue
        if record["status"] == "deleted" and not include_deleted:
            continue
        if record["status"] == "archived" and not include_archived:
            continue
        rows.append(record)
    return sorted(rows, key=lambda item: (item["kind"], item["label"].casefold(), item["case_id"]))


def _set_status(home: CareerVault, case_id: str, status: str) -> dict[str, Any]:
    if status not in {"archived", "deleted"}:
        raise CareerError("unsupported case status", code="INVALID_INPUT")
    with vault_lock(home):
        record = _read_case(home, case_id)
        record["status"] = status
        record["updated_at"] = utc_now()
        _validate_case(record)
        write_json(case_path(home, case_id), record)
    return record


def archive_case(home: CareerVault, case_id: str) -> dict[str, Any]:
    return _set_status(home, case_id, "archived")


def delete_case(home: CareerVault, case_id: str) -> dict[str, Any]:
    """Tombstone metadata; canonical evidence and artifact bodies remain untouched."""
    return _set_status(home, case_id, "deleted")
