"""Application-owned, resumable workflow sessions for the local GUI.

Sessions and drafts are transient user work. They never replace the Career Vault ledger: only the
existing proposal and approval path can promote a submitted draft into canonical evidence.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from approvals import approve as approve_canonical
from case_store import get_case
from lifecycle import vault_lock
from models import (
    EVIDENCE_EVENT_TYPES,
    EXPERIENCE_EVENT_TYPE,
    OUTCOME_STATES,
    USER_CONFIRMATION_EVIDENCE,
    WORK_EXPERIENCE_CONTEXT_KINDS,
    CareerError,
)
from persistence import atomic_write_text, read_json, read_jsonl
_SHARED_ROOT = Path(__file__).resolve().parents[2] / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))

import self_analysis_profile  # noqa: E402

from proposals import make_work_event, propose_career_context_payload  # noqa: E402
from projection import (  # noqa: E402
    confirmed_evidence_events,
    contexts_from_events,
    evidence_payload,
    projects_from_events,
)
from validation import validate_event, validate_work_event  # noqa: E402
from vault import CareerVault, utc_now  # noqa: E402


CURRENT_SESSION_SCHEMA_VERSION = 2
SESSION_SCHEMA_VERSION = CURRENT_SESSION_SCHEMA_VERSION
SESSION_WORKFLOW = "career_inventory"
SESSION_WORKFLOW_STAGES = {
    "career_inventory": frozenset({"context", "project", "experience", "review", "completed"}),
    "self_analysis": frozenset({"reflection", "hypotheses", "review", "completed"}),
    "application": frozenset({"target", "position", "research", "documents", "review", "completed"}),
}
SESSION_STAGES = frozenset(stage for stages in SESSION_WORKFLOW_STAGES.values() for stage in stages)
SESSION_STATUSES = frozenset({"draft", "review_pending", "completed", "archived"})
SESSION_ENTRYPOINTS = frozenset({"unknown", "gui", "cli", "claude", "codex"})
SESSION_ID = re.compile(r"^session-[a-f0-9]{12,64}$")
SESSION_MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def _timestamp() -> str:
    # Session/draft ordering needs finer precision than the canonical ledger's display timestamp.
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def transient_root(home: CareerVault) -> Path:
    """Return the capture-owned root for workflow material, never the derived runtime cache."""
    return home.path / "01-capture" / "gui"


def storage_paths(home: CareerVault) -> dict[str, Path]:
    root = transient_root(home)
    return {"sessions": root / "sessions", "drafts": root / "drafts"}


def storage_lifetime(kind: str) -> str:
    lifetimes = {
        "session": "transient user work; may be discarded or expire",
        "draft": "transient user work; may be discarded or expire",
        "case": "durable organizational metadata",
        "artifact": "durable generated-work metadata",
        "evidence": "canonical 02-state evidence; approval-gated",
    }
    try:
        return lifetimes[kind]
    except KeyError as exc:
        raise CareerError(f"unknown GUI storage lifetime: {kind}", code="INVALID_INPUT") from exc


def _validate_session_id(session_id: str) -> str:
    if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
        raise CareerError("invalid session id", code="INVALID_INPUT")
    return session_id


def career_project_subject(home: CareerVault, case_ref: str) -> dict[str, str]:
    """Resolve one confirmed project case into a stable, human-readable workflow subject."""
    project = get_case(home, case_ref)
    if project["kind"] != "project" or project["status"] != "active":
        raise CareerError("choose an active project", code="INVALID_RELATIONSHIP")
    context_ref = project.get("parent_ref")
    if not context_ref:
        raise CareerError(
            "this historical project needs a career context before new work can be added",
            code="INVALID_RELATIONSHIP",
        )
    context = get_case(home, context_ref)
    if context["kind"] != "career_context" or context["status"] != "active":
        raise CareerError("project context is unavailable", code="INVALID_RELATIONSHIP")
    context_id = context["metadata"].get("context_id")
    project_id = project["metadata"].get("project_id")
    if not context_id or not project_id:
        raise CareerError(
            "confirm the career context and project before recording canonical experience",
            code="PARENT_NOT_CONFIRMED",
        )
    events = read_jsonl(home.events)
    canonical_context = contexts_from_events(events).get(str(context_id))
    canonical_project = projects_from_events(events).get(str(project_id))
    if not isinstance(canonical_context, dict) or not isinstance(canonical_project, dict):
        raise CareerError(
            "the confirmed career context or project is unavailable; reload before recording work",
            code="REVISION_STALE",
            retryable=True,
        )
    return {
        "context_ref": context["case_id"],
        "context_label": str(canonical_context.get("external_label") or canonical_context["label"]),
        "context_kind": str(canonical_context["kind"]),
        "context_id": str(context_id),
        "project_ref": project["case_id"],
        "project_label": str(canonical_project.get("external_label") or canonical_project["title"]),
        "project_id": str(project_id),
    }


def _revision_source(home: CareerVault, event_id: str, expected_revision: str | None) -> dict[str, Any]:
    if not isinstance(event_id, str) or not event_id.strip():
        raise CareerError("experience id is required", code="INVALID_INPUT")
    if expected_revision != event_id:
        raise CareerError(
            "the experience changed in another entrypoint; reload before revising",
            code="REVISION_STALE", retryable=True,
        )
    events = read_jsonl(home.events)
    source = next((row for row in events if row.get("id") == event_id), None)
    if source is None or source.get("type") not in EVIDENCE_EVENT_TYPES:
        raise CareerError("experience not found", code="EXPERIENCE_NOT_FOUND")
    if not any(row.get("id") == event_id for row in confirmed_evidence_events(events)):
        raise CareerError(
            "the experience changed in another entrypoint; reload before revising",
            code="REVISION_STALE", retryable=True,
        )
    return source


def _revision_draft(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": source.get("summary") or "",
        "evidence": list(source.get("evidence") or []),
        **evidence_payload(source),
        "non_work": source.get("type") == EXPERIENCE_EVENT_TYPE,
    }


def create_revision_session(
    home: CareerVault, event_id: str, *, expected_revision: str | None, entrypoint: str = "unknown",
) -> dict[str, Any]:
    """Seed the existing capture editor from one still-current evidence event."""
    if entrypoint not in SESSION_ENTRYPOINTS:
        raise CareerError("unsupported workflow entrypoint", code="INVALID_INPUT")
    with vault_lock(home):
        source = _revision_source(home, event_id, expected_revision)
        session = _new_session(
            home,
            None,
            workflow=SESSION_WORKFLOW,
            entrypoint=entrypoint,
            subject={"experience_label": str(source.get("summary") or source["id"]), "revision_of": event_id},
        )
        _validate_session(session, home, session["session_id"])
        paths = storage_paths(home)
        paths["sessions"].mkdir(parents=True, exist_ok=True)
        paths["drafts"].mkdir(parents=True, exist_ok=True)
        _write_json(session_path(home, session["session_id"]), session)
        _write_json(
            draft_path(home, session["session_id"]),
            {
                "session_id": session["session_id"],
                "session_schema_version": CURRENT_SESSION_SCHEMA_VERSION,
                "workflow": SESSION_WORKFLOW,
                "revision": 0,
                "draft": _revision_draft(source),
                "updated_at": _timestamp(),
            },
        )
    return session


def _anchored_career_draft(
    home: CareerVault, session: dict[str, Any], draft: dict[str, Any]
) -> dict[str, Any]:
    case_ref = session.get("case_ref")
    revision_of = (session.get("subject") or {}).get("revision_of")
    if isinstance(revision_of, str):
        source = _revision_source(home, revision_of, revision_of)
        payload = evidence_payload(source)
        anchors = {
            key: payload[key]
            for key in (
                "context_id", "primary_project_id", "related_project_ids", "experience_ref",
                "experience_kind",
            )
            if key in payload
        }
        return {
            **draft,
            **anchors,
            "non_work": source.get("type") == EXPERIENCE_EVENT_TYPE,
        }
    if not case_ref:
        return draft
    subject = career_project_subject(home, str(case_ref))
    for field in ("context_id", "project_id"):
        if session["subject"].get(field) not in {None, subject[field]}:
            raise CareerError(
                "the project context changed; reload before saving",
                code="REVISION_STALE",
                retryable=True,
            )
    return {
        **draft,
        "context_id": subject["context_id"],
        "primary_project_id": subject["project_id"],
        "experience_kind": "project",
        "non_work": subject["context_kind"] not in WORK_EXPERIENCE_CONTEXT_KINDS,
    }


def session_path(home: CareerVault, session_id: str) -> Path:
    return storage_paths(home)["sessions"] / f"{_validate_session_id(session_id)}.json"


def draft_path(home: CareerVault, session_id: str) -> Path:
    return storage_paths(home)["drafts"] / f"{_validate_session_id(session_id)}.json"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _new_session(
    home: CareerVault,
    case_ref: str | None,
    *,
    workflow: str,
    entrypoint: str,
    subject: dict[str, Any],
) -> dict[str, Any]:
    session_id = f"session-{uuid.uuid4().hex[:16]}"
    stage = {
        "career_inventory": "experience",
        "self_analysis": "reflection",
        "application": "target",
    }[workflow]
    missing = {
        "career_inventory": [
            "role",
            "direct_actions",
            "individual_contribution",
            "outcome",
            "confidentiality.external_use",
        ],
        "self_analysis": ["profile"],
        "application": ["target_company", "position"],
    }[workflow]
    return {
        "session_id": session_id,
        "session_schema_version": CURRENT_SESSION_SCHEMA_VERSION,
        "workflow": workflow,
        "stage": stage,
        "status": "draft",
        "revision": 0,
        "started_by": entrypoint,
        "last_entrypoint": entrypoint,
        "subject": subject,
        "case_ref": case_ref,
        "current_item_ref": None,
        "missing_fields": missing,
        "completed": [],
        "draft_ref": draft_path(home, session_id).relative_to(home.path).as_posix(),
        "proposal_refs": [],
        "next_action": "continue",
        "updated_at": _timestamp(),
    }


def _validate_session(record: Any, home: CareerVault, session_id: str) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise CareerError("session record must be an object", code="SESSION_INVALID")
    if "session_schema_version" not in record:
        raise CareerError(
            "session_schema_version is missing; legacy session formats are not supported",
            code="SESSION_SCHEMA_MISSING",
            retryable=False,
        )
    version = record["session_schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise CareerError("session_schema_version must be an integer", code="SESSION_INVALID")
    if version > CURRENT_SESSION_SCHEMA_VERSION:
        raise CareerError(
            "this session was created by a newer version; upgrade the Career Agent before resuming",
            code="SESSION_SCHEMA_NEWER",
            retryable=False,
        )
    if version < CURRENT_SESSION_SCHEMA_VERSION:
        record = _migrate_session(record)
        version = record.get("session_schema_version")
    required = {
        "session_id",
        "session_schema_version",
        "workflow",
        "stage",
        "status",
        "revision",
        "started_by",
        "last_entrypoint",
        "subject",
        "case_ref",
        "current_item_ref",
        "missing_fields",
        "completed",
        "draft_ref",
        "proposal_refs",
        "next_action",
        "updated_at",
    }
    missing = sorted(required - set(record))
    if missing:
        raise CareerError(
            f"session is incomplete; missing fields: {', '.join(missing)}",
            code="SESSION_INVALID",
        )
    if record.get("session_id") != session_id:
        raise CareerError("session id does not match its file", code="SESSION_INVALID")
    workflow = record.get("workflow")
    if version != CURRENT_SESSION_SCHEMA_VERSION or workflow not in SESSION_WORKFLOW_STAGES:
        raise CareerError("session workflow or schema is unsupported", code="SESSION_INVALID")
    if record.get("stage") not in SESSION_WORKFLOW_STAGES[workflow]:
        raise CareerError("session stage is not valid for its workflow", code="SESSION_INVALID")
    if record.get("status") not in SESSION_STATUSES:
        raise CareerError("session status is invalid", code="SESSION_INVALID")
    revision = record.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise CareerError("session revision must be a non-negative integer", code="SESSION_INVALID")
    for field in ("started_by", "last_entrypoint"):
        if record.get(field) not in SESSION_ENTRYPOINTS:
            raise CareerError(f"session.{field} is invalid", code="SESSION_INVALID")
    subject = record.get("subject")
    if not isinstance(subject, dict) or any(
        not isinstance(key, str)
        or not key.strip()
        or value is not None and (not isinstance(value, str) or not value.strip())
        for key, value in subject.items()
    ):
        raise CareerError("session.subject must contain string labels or references", code="SESSION_INVALID")
    for field in ("case_ref", "current_item_ref"):
        value = record.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise CareerError(f"session.{field} must be a non-empty string or null", code="SESSION_INVALID")
    for field in ("missing_fields", "completed", "proposal_refs"):
        value = record.get(field)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise CareerError(f"session.{field} must be a list of strings", code="SESSION_INVALID")
    if not isinstance(record.get("draft_ref"), str) or not record["draft_ref"].strip():
        raise CareerError("session.draft_ref must be a non-empty relative path", code="SESSION_INVALID")
    if Path(record["draft_ref"]).is_absolute() or ".." in Path(record["draft_ref"]).parts:
        raise CareerError("session.draft_ref must stay inside the Vault", code="SESSION_INVALID")
    if not isinstance(record.get("updated_at"), str) or not record["updated_at"].strip():
        raise CareerError("session.updated_at must be a timestamp", code="SESSION_INVALID")
    if not isinstance(record.get("next_action"), str) or not record["next_action"].strip():
        raise CareerError("session.next_action must be a non-empty string", code="SESSION_INVALID")
    return record


def _migrate_session(record: dict[str, Any]) -> dict[str, Any]:
    current = record
    version = current.get("session_schema_version")
    while isinstance(version, int) and version < CURRENT_SESSION_SCHEMA_VERSION:
        migration = SESSION_MIGRATIONS.get(version)
        if migration is None:
            raise CareerError(
                f"session schema migration is unavailable: v{version} -> v{version + 1}",
                code="SESSION_MIGRATION_UNAVAILABLE",
                retryable=False,
            )
        migrated = migration(dict(current))
        if not isinstance(migrated, dict) or migrated.get("session_schema_version") == version:
            raise CareerError(
                f"session schema migration did not advance from v{version}",
                code="SESSION_MIGRATION_INVALID",
                retryable=False,
            )
        current = migrated
        version = current.get("session_schema_version")
    return current


def _migrate_v0_session(record: dict[str, Any]) -> dict[str, Any]:
    """Convert the pre-semantic ``page`` field without guessing numeric UI pages."""
    migrated = dict(record)
    legacy_stage = migrated.pop("page", None)
    current_stage = migrated.get("stage")
    if current_stage is None:
        current_stage = legacy_stage
        migrated["stage"] = current_stage
    if legacy_stage is not None and legacy_stage != current_stage:
        raise CareerError(
            "v0 session page and stage disagree; the session was not changed",
            code="SESSION_MIGRATION_INVALID",
            retryable=False,
        )
    if not isinstance(current_stage, str) or current_stage not in {
        "experience_evidence", "review", "completed"
    }:
        raise CareerError(
            "v0 session has no supported semantic stage; the session was not changed",
            code="SESSION_MIGRATION_INVALID",
            retryable=False,
        )
    migrated["session_schema_version"] = 1
    return migrated


def _migrate_v1_session(record: dict[str, Any]) -> dict[str, Any]:
    """Generalize the GUI-only inventory record without rewriting historical files."""
    migrated = dict(record)
    stage = {
        "experience_evidence": "experience",
        "review": "review",
        "completed": "completed",
    }.get(str(migrated.get("stage")))
    if migrated.get("workflow") not in {"tanaoroshi", "career_inventory"} or stage is None:
        raise CareerError(
            "v1 session has no supported workflow or stage; the session was not changed",
            code="SESSION_MIGRATION_INVALID",
            retryable=False,
        )
    migrated.update(
        {
            "session_schema_version": CURRENT_SESSION_SCHEMA_VERSION,
            "workflow": "career_inventory",
            "stage": stage,
            "status": "completed" if stage == "completed" else (
                "review_pending" if stage == "review" else "draft"
            ),
            "revision": 0,
            "started_by": "unknown",
            "last_entrypoint": "unknown",
            "subject": (
                {"case_ref": migrated["case_ref"]} if migrated.get("case_ref") else {}
            ),
            "next_action": "done" if stage == "completed" else (
                "review" if stage == "review" else "continue"
            ),
        }
    )
    return migrated


def register_session_migration(
    from_version: int, migration: Callable[[dict[str, Any]], dict[str, Any]]
) -> None:
    """Provide the explicit hook used by the later v0→v1 migration PR."""
    if from_version < 0 or not callable(migration):
        raise CareerError("invalid session migration", code="INVALID_INPUT")
    SESSION_MIGRATIONS[from_version] = migration


register_session_migration(0, _migrate_v0_session)
register_session_migration(1, _migrate_v1_session)


def _migrate_v0_draft(record: dict[str, Any]) -> dict[str, Any]:
    """A v0 draft differs from a v1 draft only by its version stamp.

    The v0→v1 change was to the session record: `page` became a semantic `stage`. Drafts held the
    user's field values then and hold them now. Stamping the version is the whole migration, and
    saying so explicitly is what keeps the pair resumable — migrating the session while refusing
    the draft written beside it leaves a vault that opens halfway.
    """
    migrated = dict(record)
    migrated["session_schema_version"] = 1
    return migrated


def _migrate_v1_draft(record: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(record)
    if migrated.get("workflow") not in {"tanaoroshi", "career_inventory"}:
        raise CareerError(
            "v1 draft has no supported workflow; the draft was not changed",
            code="SESSION_MIGRATION_INVALID",
            retryable=False,
        )
    migrated.update(
        {
            "session_schema_version": CURRENT_SESSION_SCHEMA_VERSION,
            "workflow": "career_inventory",
            "revision": 0,
        }
    )
    return migrated


DRAFT_MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    0: _migrate_v0_draft,
    1: _migrate_v1_draft,
}


def _migrate_draft(record: dict[str, Any]) -> dict[str, Any]:
    current = record
    version = current.get("session_schema_version")
    while isinstance(version, int) and version < CURRENT_SESSION_SCHEMA_VERSION:
        migration = DRAFT_MIGRATIONS.get(version)
        if migration is None:
            raise CareerError(
                f"draft schema migration is unavailable: v{version} -> v{version + 1}",
                code="SESSION_MIGRATION_UNAVAILABLE",
                retryable=False,
            )
        migrated = migration(dict(current))
        if not isinstance(migrated, dict) or migrated.get("session_schema_version") == version:
            raise CareerError(
                "draft migration did not advance the schema version; the draft was not changed",
                code="SESSION_MIGRATION_INVALID",
                retryable=False,
            )
        current = migrated
        version = current.get("session_schema_version")
    return current


def _read_session(home: CareerVault, session_id: str) -> dict[str, Any]:
    path = session_path(home, session_id)
    record = read_json(path, None)
    if record is None:
        raise CareerError(f"session not found: {session_id}", code="SESSION_NOT_FOUND")
    return _validate_session(record, home, session_id)


def _draft_values(
    value: Any,
    *,
    workflow: str = SESSION_WORKFLOW,
    allow_empty_summary: bool = True,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CareerError("draft must be an object", code="INVALID_INPUT")
    if workflow == "application":
        if value:
            raise CareerError(
                "application workflow content belongs to application cases",
                code="INVALID_INPUT",
            )
        return {}
    if workflow == "self_analysis":
        if set(value) - {"profile"}:
            raise CareerError(
                "self-analysis draft contains unsupported fields",
                code="INVALID_INPUT",
            )
        profile = value.get("profile")
        if profile is None:
            return {}
        try:
            self_analysis_profile.validate_self_analysis_profile(profile)
        except self_analysis_profile.ProfileValidationError as exc:
            raise CareerError(str(exc), code="INVALID_INPUT") from exc
        return {"profile": dict(profile)}
    if workflow != SESSION_WORKFLOW:
        raise CareerError("unsupported workflow", code="INVALID_INPUT")
    draft = dict(value)
    non_work = draft.get("non_work", False)
    if not isinstance(non_work, bool):
        raise CareerError("draft.non_work must be an explicit boolean", code="INVALID_INPUT")
    summary = draft.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise CareerError("draft.summary must be a string or null", code="INVALID_INPUT")
    if not allow_empty_summary and not str(summary or "").strip():
        raise CareerError("draft.summary is required before creating a proposal", code="INVALID_INPUT")
    # The browser sends incomplete controls as empty strings. Empty means Unknown here, not a
    # malformed canonical value; the strict validator still owns every non-empty field shape.
    for key in (
        "summary",
        "role",
        "scope",
        "problem",
        "individual_contribution",
        "team_result",
        "work_date",
        "context_id",
        "experience_kind",
        "experience_ref",
    ):
        if isinstance(draft.get(key), str) and not draft[key].strip():
            draft.pop(key)
    evidence = draft.get("evidence", [])
    if not isinstance(evidence, list) or any(not isinstance(item, str) or not item.strip() for item in evidence):
        raise CareerError("draft.evidence must be a list of non-empty strings", code="INVALID_INPUT")
    payload = {key: item for key, item in draft.items() if key not in {"summary", "evidence", "non_work"}}
    validate_work_event(payload, field="draft.evidence_payload")
    return draft


def _read_draft(home: CareerVault, session_id: str) -> dict[str, Any]:
    path = draft_path(home, session_id)
    record = read_json(path, None)
    if record is None:
        return {
            "session_id": session_id,
            "session_schema_version": CURRENT_SESSION_SCHEMA_VERSION,
            "workflow": SESSION_WORKFLOW,
            "revision": 0,
            "updated_at": "",
            "draft": {},
        }
    if not isinstance(record, dict):
        raise CareerError("draft record must be an object", code="SESSION_INVALID")
    if "session_schema_version" not in record:
        raise CareerError(
            "draft session_schema_version is missing; legacy draft formats are not supported",
            code="SESSION_SCHEMA_MISSING",
            retryable=False,
        )
    version = record["session_schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise CareerError("draft session_schema_version must be an integer", code="SESSION_INVALID")
    if version > CURRENT_SESSION_SCHEMA_VERSION:
        raise CareerError(
            "this draft was created by a newer version; upgrade the Career Agent before resuming",
            code="SESSION_SCHEMA_NEWER",
            retryable=False,
        )
    if version < CURRENT_SESSION_SCHEMA_VERSION:
        # Same contract as the session record: migrate in memory, leave the file alone. A resume
        # is a read; rewriting on open would edit the user's work before they asked for anything.
        record = _migrate_draft(record)
    if record.get("session_id") != session_id or not isinstance(record.get("draft"), dict):
        raise CareerError("draft record does not match its session", code="SESSION_INVALID")
    revision = record.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise CareerError("draft revision must be a non-negative integer", code="SESSION_INVALID")
    _draft_values(record["draft"], workflow=str(record.get("workflow") or SESSION_WORKFLOW))
    return record


def create_session(
    home: CareerVault,
    *,
    case_ref: str | None = None,
    workflow: str = SESSION_WORKFLOW,
    entrypoint: str = "unknown",
    subject: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if case_ref is not None and (not isinstance(case_ref, str) or not case_ref.strip()):
        raise CareerError("case_ref must be a non-empty string or null", code="INVALID_INPUT")
    if workflow not in SESSION_WORKFLOW_STAGES:
        raise CareerError("unsupported workflow", code="INVALID_INPUT")
    if entrypoint not in SESSION_ENTRYPOINTS:
        raise CareerError("unsupported workflow entrypoint", code="INVALID_INPUT")
    if subject is None:
        subject = {"case_ref": case_ref} if case_ref else {}
    if not isinstance(subject, dict):
        raise CareerError("session subject must be an object", code="INVALID_INPUT")
    with vault_lock(home):
        # Resolve the parent while holding the same Vault lock used by case lifecycle changes.
        # Otherwise an archive can land between validation and session creation.
        if workflow == SESSION_WORKFLOW and case_ref:
            subject = {**subject, **career_project_subject(home, case_ref)}
        session = _new_session(
            home,
            case_ref,
            workflow=workflow,
            entrypoint=entrypoint,
            subject=dict(subject),
        )
        _validate_session(session, home, session["session_id"])
        paths = storage_paths(home)
        paths["sessions"].mkdir(parents=True, exist_ok=True)
        paths["drafts"].mkdir(parents=True, exist_ok=True)
        _write_json(session_path(home, session["session_id"]), session)
        _write_json(
            draft_path(home, session["session_id"]),
            {
                "session_id": session["session_id"],
                "session_schema_version": CURRENT_SESSION_SCHEMA_VERSION,
                "workflow": workflow,
                "revision": 0,
                "draft": {},
                "updated_at": "",
            },
        )
    return session


def load_session(home: CareerVault, session_id: str) -> dict[str, Any]:
    return _read_session(home, session_id)


def _current_revision(session: dict[str, Any], draft_record: dict[str, Any]) -> int:
    return max(int(session.get("revision", 0)), int(draft_record.get("revision", 0)))


def _write_draft_revision(
    home: CareerVault, session: dict[str, Any], revision: int
) -> None:
    """Keep the paired draft revision aligned after semantic-only workflow changes."""
    record = _read_draft(home, session["session_id"])
    if record["revision"] == revision and record.get("session_schema_version") == CURRENT_SESSION_SCHEMA_VERSION:
        return
    _write_json(
        draft_path(home, session["session_id"]),
        {
            **record,
            "session_schema_version": CURRENT_SESSION_SCHEMA_VERSION,
            "workflow": session["workflow"],
            "revision": revision,
        },
    )


def _expect_revision(expected_revision: int | None, current_revision: int) -> None:
    # `None` keeps the historical in-process API readable. Every supported mutable entrypoint
    # supplies the revision it read; that is the path which prevents stale-host overwrites.
    if expected_revision is None:
        return
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
        raise CareerError("expected_revision must be an integer", code="INVALID_INPUT")
    if expected_revision != current_revision:
        raise CareerError(
            "the workflow changed in another entrypoint; reload before saving",
            code="REVISION_STALE",
            retryable=True,
            details={"expected_revision": expected_revision, "current_revision": current_revision},
        )


def _display_context(session: dict[str, Any]) -> list[str]:
    subject = session.get("subject") if isinstance(session.get("subject"), dict) else {}
    preferred = (
        "context_label",
        "project_label",
        "experience_label",
        "profile_label",
        "target_company_label",
        "position_label",
    )
    return [str(subject[key]) for key in preferred if subject.get(key)]


def list_sessions(
    home: CareerVault,
    *,
    workflow: str | None = None,
    include_archived: bool = False,
    context: str | None = None,
) -> dict[str, Any]:
    """Every resumable session, so a client never has to remember an id across restarts.

    The server binds port 0, so each run gives the browser a different origin and localStorage
    starts empty. The sessions on disk are the only thing that survives; without this the user
    cannot reach work that is sitting there intact.
    """
    if workflow is not None and workflow not in SESSION_WORKFLOW_STAGES:
        raise CareerError("unsupported workflow", code="INVALID_INPUT")
    if context is not None and not str(context).strip():
        raise CareerError("context must be a visible non-empty label", code="INVALID_INPUT")
    rows: list[dict[str, Any]] = []
    for path in sorted(storage_paths(home)["sessions"].glob("session-*.json")):
        if SESSION_ID.fullmatch(path.stem) is None:
            continue
        session = _read_session(home, path.stem)
        if workflow is not None and session["workflow"] != workflow:
            continue
        if session["status"] != "completed" and (
            include_archived or session["status"] != "archived"
        ):
            rows.append(
                {
                    **session,
                    "display_context": _display_context(session),
                    "remaining_work": list(session["missing_fields"]),
                    "review_status": session["status"],
                }
            )
    if context is not None:
        needle = str(context).strip().casefold()
        rows = [
            row
            for row in rows
            if needle
            in {
                *(str(label).strip().casefold() for label in row["display_context"]),
                " / ".join(str(label).strip().casefold() for label in row["display_context"]),
                " → ".join(str(label).strip().casefold() for label in row["display_context"]),
            }
        ]
    rows.sort(key=lambda item: (item["updated_at"], item["session_id"]), reverse=True)
    return {"mode": "sessions", "sessions": rows, "count": len(rows), "read_only": True}


def resume_workflow(
    home: CareerVault, *, workflow: str | None = None, context: str | None = None
) -> dict[str, Any]:
    """Resume one unambiguous workflow without requiring a caller to know its id."""
    listed = list_sessions(home, workflow=workflow, context=context)
    rows = listed["sessions"]
    if not rows:
        raise CareerError("no resumable workflow was found", code="SESSION_NOT_FOUND")
    if len(rows) > 1:
        raise CareerError(
            "more than one workflow can be resumed; choose by its visible context",
            code="SESSION_AMBIGUOUS",
            details={
                "choices": [
                    {
                        "session_ref": row["session_id"],
                        "workflow": row["workflow"],
                        "context": row["display_context"],
                        "status": row["status"],
                        "updated_at": row["updated_at"],
                    }
                    for row in rows
                ]
            },
        )
    return resume_session(home, rows[0]["session_id"])


def assign_session_project(
    home: CareerVault,
    session_id: str,
    case_ref: str,
    *,
    expected_revision: int,
    entrypoint: str = "unknown",
) -> dict[str, Any]:
    """Attach an unplaced inventory draft to one confirmed project without guessing."""
    if entrypoint not in SESSION_ENTRYPOINTS:
        raise CareerError("unsupported workflow entrypoint", code="INVALID_INPUT")
    with vault_lock(home):
        session = _read_session(home, session_id)
        _refuse_completed_session(home, session, "connect")
        if session["workflow"] != SESSION_WORKFLOW:
            raise CareerError("only a career experience needs a project", code="INVALID_INPUT")
        current_revision = _current_revision(session, _read_draft(home, session_id))
        _expect_revision(expected_revision, current_revision)
        if session.get("case_ref"):
            if session["case_ref"] == case_ref:
                return resume_session(home, session_id)
            raise CareerError(
                "this experience is already connected to another project",
                code="REVISION_STALE",
                retryable=True,
            )
        if session.get("proposal_refs"):
            raise CareerError(
                "return this experience to editing before changing its project",
                code="REVISION_STALE",
                retryable=True,
            )
        subject = career_project_subject(home, case_ref)
        revision = current_revision + 1
        draft_record = _read_draft(home, session_id)
        updated_session = {
            **session,
            "case_ref": case_ref,
            "subject": {**session.get("subject", {}), **subject},
            "revision": revision,
            "last_entrypoint": entrypoint,
            "updated_at": _timestamp(),
        }
        values = _draft_values(
            _anchored_career_draft(home, updated_session, draft_record.get("draft", {}))
        )
        _validate_session(updated_session, home, session_id)
        _write_json(draft_path(home, session_id), {
            **draft_record,
            "session_schema_version": CURRENT_SESSION_SCHEMA_VERSION,
            "workflow": SESSION_WORKFLOW,
            "revision": revision,
            "draft": values,
            "updated_at": _timestamp(),
        })
        _write_json(session_path(home, session_id), updated_session)
    return resume_session(home, session_id)


def archive_session(
    home: CareerVault,
    session_id: str,
    *,
    expected_revision: int | None = None,
    entrypoint: str = "unknown",
) -> dict[str, Any]:
    """Abandon transient work without deleting its draft or canonical history."""
    with vault_lock(home):
        session = _read_session(home, session_id)
        _refuse_completed_session(home, session, "archive")
        current_revision = _current_revision(session, _read_draft(home, session_id))
        _expect_revision(expected_revision, current_revision)
        updated = {
            **session,
            "status": "archived",
            "revision": current_revision + 1,
            "last_entrypoint": entrypoint if entrypoint != "unknown" else session["last_entrypoint"],
            "next_action": "restore_or_discard",
            "updated_at": _timestamp(),
        }
        _validate_session(updated, home, session_id)
        _write_json(session_path(home, session_id), updated)
        _write_draft_revision(home, updated, updated["revision"])
    return updated


def restore_session(
    home: CareerVault,
    session_id: str,
    *,
    expected_revision: int | None = None,
    entrypoint: str = "unknown",
) -> dict[str, Any]:
    with vault_lock(home):
        session = _read_session(home, session_id)
        if session["status"] != "archived":
            raise CareerError("only archived work can be restored", code="INVALID_INPUT")
        current_revision = _current_revision(session, _read_draft(home, session_id))
        _expect_revision(expected_revision, current_revision)
        status = "review_pending" if session["stage"] == "review" else "draft"
        updated = {
            **session,
            "status": status,
            "revision": current_revision + 1,
            "last_entrypoint": entrypoint if entrypoint != "unknown" else session["last_entrypoint"],
            "next_action": "review" if status == "review_pending" else "continue",
            "updated_at": _timestamp(),
        }
        _validate_session(updated, home, session_id)
        _write_json(session_path(home, session_id), updated)
        _write_draft_revision(home, updated, updated["revision"])
    return updated


def missing_fields(
    draft: dict[str, Any], *, workflow: str = SESSION_WORKFLOW
) -> list[str]:
    _draft_values(draft, workflow=workflow)
    if workflow == "self_analysis":
        return [] if draft.get("profile") else ["profile"]
    if workflow == "application":
        return []
    missing: list[str] = []
    if not str(draft.get("role") or "").strip():
        missing.append("role")
    if not draft.get("direct_actions"):
        missing.append("direct_actions")
    if not str(draft.get("individual_contribution") or "").strip():
        missing.append("individual_contribution")
    outcome = draft.get("outcome_state")
    if outcome not in OUTCOME_STATES:
        missing.append("outcome")
    elif outcome == "quantitative" and not draft.get("metrics"):
        missing.append("metrics")
    confidentiality = draft.get("confidentiality")
    external_use = confidentiality.get("external_use") if isinstance(confidentiality, dict) else None
    if external_use in (None, "", "unknown"):
        missing.append("confidentiality.external_use")
    return missing


def field_status(
    draft: dict[str, Any], *, workflow: str = SESSION_WORKFLOW
) -> list[dict[str, str]]:
    if workflow == "self_analysis":
        return [{"field": "profile", "status": "entered" if draft.get("profile") else "not_entered"}]
    if workflow == "application":
        return []
    outcome = draft.get("outcome_state")
    confidentiality = draft.get("confidentiality")
    external_use = confidentiality.get("external_use") if isinstance(confidentiality, dict) else None
    states = {
        "role": "entered" if str(draft.get("role") or "").strip() else "not_entered",
        "direct_actions": "entered" if draft.get("direct_actions") else "not_entered",
        "individual_contribution": (
            "entered" if str(draft.get("individual_contribution") or "").strip() else "not_entered"
        ),
        "outcome": (
            "explicitly_unknown" if outcome == "unknown" else (
                "entered" if outcome in OUTCOME_STATES else "not_entered"
            )
        ),
        "metrics": (
            "entered" if outcome == "quantitative" and draft.get("metrics") else (
                "needs_review" if outcome == "quantitative" else (
                    "explicitly_unknown" if outcome == "unknown" else (
                        "not_applicable" if outcome in {"qualitative", "not_measured"} else "not_entered"
                    )
                )
            )
        ),
        "confidentiality.external_use": (
            "explicitly_unknown" if external_use == "unknown" else (
                "entered" if external_use in {"allowed", "blocked"} else "not_entered"
            )
        ),
    }
    return [{"field": field, "status": status} for field, status in states.items()]


def save_draft(
    home: CareerVault,
    session_id: str,
    draft: dict[str, Any],
    *,
    expected_revision: int | None = None,
    entrypoint: str = "unknown",
) -> dict[str, Any]:
    if entrypoint not in SESSION_ENTRYPOINTS:
        raise CareerError("unsupported workflow entrypoint", code="INVALID_INPUT")
    with vault_lock(home):
        session = _read_session(home, session_id)
        _refuse_completed_session(home, session, "record another experience")
        draft_record = _read_draft(home, session_id)
        current_revision = _current_revision(session, draft_record)
        _expect_revision(expected_revision, current_revision)
        revision = current_revision + 1
        anchored = (
            _anchored_career_draft(home, session, draft)
            if session["workflow"] == SESSION_WORKFLOW
            else draft
        )
        values = _draft_values(anchored, workflow=session["workflow"])
        record = {
            "session_id": session_id,
            "session_schema_version": CURRENT_SESSION_SCHEMA_VERSION,
            "workflow": session["workflow"],
            "revision": revision,
            "draft": values,
            "updated_at": _timestamp(),
        }
        _write_json(draft_path(home, session_id), record)
        session = _checkpoint_unlocked(
            home,
            session,
            stage=(
                {"career_inventory": "experience", "self_analysis": "hypotheses", "application": "target"}[
                    session["workflow"]
                ]
                if session["stage"] == "review"
                else None
            ),
            missing=(
                missing_fields(values, workflow=session["workflow"])
                if session["workflow"] != "application"
                else session["missing_fields"]
            ),
            revision=revision,
            entrypoint=entrypoint,
        )
        return {
            "session": session,
            "draft": values,
            "missing_fields": missing_fields(values, workflow=session["workflow"]),
            "field_status": field_status(values, workflow=session["workflow"]),
            "unconfirmed_input": True,
            "revision": revision,
        }


def resume_session(home: CareerVault, session_id: str) -> dict[str, Any]:
    session = _read_session(home, session_id)
    draft_record = _read_draft(home, session_id)
    draft = draft_record.get("draft", {})
    draft_updated = str(draft_record.get("updated_at") or "")
    session_updated = str(session.get("updated_at") or "")
    revision = _current_revision(session, draft_record)
    return {
        "mode": "tanaoroshi-resume",
        "session": session,
        "draft": draft,
        "missing_fields": missing_fields(draft, workflow=session["workflow"]),
        "field_status": field_status(draft, workflow=session["workflow"]),
        "unconfirmed_input": bool(
            draft
            and session.get("status") not in {"review_pending", "completed"}
        ) or bool(draft_updated and draft_updated > session_updated),
        "revision": revision,
        "write_recovery_required": int(session.get("revision", 0)) != int(
            draft_record.get("revision", 0)
        ),
        "ok": True,
    }


def _checkpoint_unlocked(
    home: CareerVault,
    session: dict[str, Any],
    *,
    stage: str | None = None,
    current_item_ref: str | None = None,
    missing: list[str] | None = None,
    completed: list[str] | None = None,
    proposal_refs: list[str] | None = None,
    revision: int | None = None,
    entrypoint: str = "unknown",
) -> dict[str, Any]:
    next_stage = stage or session["stage"]
    if next_stage not in SESSION_WORKFLOW_STAGES[session["workflow"]]:
        raise CareerError("checkpoint stage is not valid for this workflow", code="INVALID_INPUT")
    if entrypoint not in SESSION_ENTRYPOINTS:
        raise CareerError("unsupported workflow entrypoint", code="INVALID_INPUT")
    if current_item_ref is not None and (not isinstance(current_item_ref, str) or not current_item_ref.strip()):
        raise CareerError("current_item_ref must be a non-empty string or null", code="INVALID_INPUT")
    for name, value in (("missing_fields", missing), ("completed", completed), ("proposal_refs", proposal_refs)):
        if value is not None and (not isinstance(value, list) or any(not isinstance(item, str) for item in value)):
            raise CareerError(f"{name} must be a list of strings", code="INVALID_INPUT")
    next_revision = int(session.get("revision", 0)) + 1 if revision is None else revision
    status = (
        "completed" if next_stage == "completed" else (
            "review_pending" if next_stage == "review" else "draft"
        )
    )
    updated = {
        **session,
        "stage": next_stage,
        "status": status,
        "revision": next_revision,
        "last_entrypoint": entrypoint if entrypoint != "unknown" else session["last_entrypoint"],
        "current_item_ref": current_item_ref if current_item_ref is not None else session["current_item_ref"],
        "missing_fields": list(missing if missing is not None else session["missing_fields"]),
        "completed": list(completed if completed is not None else session["completed"]),
        "proposal_refs": list(proposal_refs if proposal_refs is not None else session["proposal_refs"]),
        "next_action": "done" if status == "completed" else (
            "review" if status == "review_pending" else "continue"
        ),
        "updated_at": _timestamp(),
    }
    _validate_session(updated, home, session["session_id"])
    _write_json(session_path(home, session["session_id"]), updated)
    _write_draft_revision(home, updated, updated["revision"])
    return updated


def checkpoint_session(
    home: CareerVault,
    session_id: str,
    *,
    stage: str | None = None,
    current_item_ref: str | None = None,
    missing: list[str] | None = None,
    completed: list[str] | None = None,
    expected_revision: int | None = None,
    entrypoint: str = "unknown",
) -> dict[str, Any]:
    with vault_lock(home):
        session = _read_session(home, session_id)
        current_revision = _current_revision(session, _read_draft(home, session_id))
        _expect_revision(expected_revision, current_revision)
        return _checkpoint_unlocked(
            home,
            session,
            stage=stage,
            current_item_ref=current_item_ref,
            missing=missing,
            completed=completed,
            revision=current_revision + 1,
            entrypoint=entrypoint,
        )


def _proposal_rows(home: CareerVault) -> list[dict[str, Any]]:
    return read_jsonl(home.proposals)


def _refuse_completed_session(
    home: CareerVault, session: dict[str, Any], action: str
) -> None:
    """An approved session is a closed record; the next experience needs its own session.

    Without this a completed session keeps accepting drafts, and the proposal it already had
    approved is the one the next approval finds.
    """
    approved = {
        row.get("id")
        for row in _proposal_rows(home)
        if row.get("status") == "approved"
    }
    if session.get("stage") == "completed" or approved.intersection(session["proposal_refs"]):
        raise CareerError(
            f"this 棚卸し session is already approved; start a new session to {action}",
            code="SESSION_COMPLETED",
        )
    if session.get("status") == "archived":
        raise CareerError(
            "this workflow is archived; restore it before changing it",
            code="SESSION_ARCHIVED",
        )


def _proposal_response(
    proposal: dict[str, Any], session_id: str, revision: int, *, review_before: dict[str, Any] | None = None
) -> dict[str, Any]:
    # The event travels with the response so the screen can show what approval will write. An
    # approval button next to text the caller never received is a button the user cannot check.
    result = {
        "mode": "tanaoroshi-proposal",
        "session_id": session_id,
        "revision": revision,
        "proposal": {
            "id": proposal["id"],
            "status": proposal["status"],
            "created_at": proposal.get("created_at", ""),
            "draft_updated_at": proposal.get("draft_updated_at", ""),
            "event": proposal.get("event", {}),
        },
        "ok": True,
    }
    if review_before is not None:
        result["review_before"] = review_before
    return result


def _proposal_event(draft: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    values = _draft_values(draft, allow_empty_summary=False)
    if values.get("outcome_state") == "quantitative" and not values.get("metrics"):
        raise CareerError(
            "metrics are required for a quantitative outcome",
            code="INVALID_INPUT",
        )
    event = make_work_event(str(values["summary"]), non_work=values.get("non_work", False))
    event["evidence"] = list(values.get("evidence", [])) or [USER_CONFIRMATION_EVIDENCE]
    payload = {key: item for key, item in values.items() if key not in {"summary", "evidence", "non_work"}}
    event["experience" if values.get("non_work", False) else "work_event"] = payload
    validate_event(event)
    return event, values


def _create_self_analysis_proposal(
    home: CareerVault,
    session_id: str,
    *,
    expected_revision: int | None,
    entrypoint: str,
) -> dict[str, Any]:
    session = _read_session(home, session_id)
    _refuse_completed_session(home, session, "propose from")
    draft_record = _read_draft(home, session_id)
    current_revision = _current_revision(session, draft_record)
    _expect_revision(expected_revision, current_revision)
    values = _draft_values(draft_record.get("draft", {}), workflow="self_analysis")
    profile = values.get("profile")
    if not isinstance(profile, dict):
        raise CareerError(
            "a reviewed SELF_ANALYSIS_PROFILE is required before proposing",
            code="INVALID_INPUT",
        )
    draft_stamp = str(draft_record.get("updated_at") or "")

    def proposal_precondition() -> None:
        latest_session = _read_session(home, session_id)
        _refuse_completed_session(home, latest_session, "propose from")
        latest_draft = _read_draft(home, session_id)
        _expect_revision(
            expected_revision,
            _current_revision(latest_session, latest_draft),
        )
        if str(latest_draft.get("updated_at") or "") != draft_stamp:
            raise CareerError(
                "the self-analysis changed before review could be prepared",
                code="REVISION_STALE",
                retryable=True,
            )

    proposed = propose_career_context_payload(
        home,
        profile,
        session_id=session_id,
        draft_updated_at=draft_stamp,
        precondition=proposal_precondition,
    )
    proposal = proposed["proposal"]
    with vault_lock(home):
        latest_session = _read_session(home, session_id)
        latest_draft = _read_draft(home, session_id)
        latest_revision = _current_revision(latest_session, latest_draft)
        _expect_revision(expected_revision, latest_revision)
        refs = list(latest_session["proposal_refs"])
        if proposal["id"] not in refs:
            refs.append(proposal["id"])
        updated = _checkpoint_unlocked(
            home,
            latest_session,
            stage="review",
            current_item_ref="self_analysis_profile",
            missing=[],
            proposal_refs=refs,
            revision=latest_revision + 1,
            entrypoint=entrypoint,
        )
    prior = next(
        (
            row.get("career_context")
            for row in reversed(read_jsonl(home.events))
            if row.get("type") == "career_context"
            and row.get("status") == "confirmed"
            and isinstance(row.get("career_context"), dict)
        ),
        None,
    )
    return _proposal_response(
        proposal,
        session_id,
        updated["revision"],
        review_before=prior,
    )


def create_proposal(
    home: CareerVault,
    session_id: str,
    *,
    expected_revision: int | None = None,
    entrypoint: str = "unknown",
) -> dict[str, Any]:
    workflow = _read_session(home, session_id)["workflow"]
    if workflow == "self_analysis":
        return _create_self_analysis_proposal(
            home,
            session_id,
            expected_revision=expected_revision,
            entrypoint=entrypoint,
        )
    if workflow != "career_inventory":
        raise CareerError(
            "this workflow has no canonical proposal",
            code="INVALID_INPUT",
        )
    with vault_lock(home):
        session = _read_session(home, session_id)
        _refuse_completed_session(home, session, "propose from")
        revision_of = (session.get("subject") or {}).get("revision_of")
        if not session.get("case_ref") and not revision_of and entrypoint != "unknown":
            raise CareerError(
                "choose the company or activity and project before review",
                code="CONTEXT_REQUIRED",
            )
        proposal_id = f"proposal-{session_id.removeprefix('session-')}"
        draft_record = _read_draft(home, session_id)
        current_revision = _current_revision(session, draft_record)
        _expect_revision(expected_revision, current_revision)
        review_before = None
        if isinstance(revision_of, str):
            source = _revision_source(home, revision_of, revision_of)
            review_before = {"summary": source.get("summary"), **evidence_payload(source)}
        draft_stamp = str(draft_record.get("updated_at") or "")
        existing = [
            row
            for row in _proposal_rows(home)
            if (row.get("id") in session["proposal_refs"] or row.get("session_id") == session_id)
            and row.get("status") == "pending"
        ]
        if existing:
            proposal = existing[-1]
            if proposal.get("draft_updated_at") == draft_stamp:
                if proposal["id"] not in session["proposal_refs"]:
                    session = _checkpoint_unlocked(
                        home,
                        session,
                        stage="review",
                        current_item_ref=session["current_item_ref"] or "new_experience",
                        proposal_refs=[*session["proposal_refs"], proposal["id"]],
                        revision=current_revision + 1,
                        entrypoint=entrypoint,
                    )
                    current_revision = session["revision"]
                return _proposal_response(proposal, session_id, current_revision, review_before=review_before)
            # The draft moved after this proposal was taken. Re-snapshot in place rather than
            # leaving a pending proposal that no longer matches what the user is looking at.
            event, values = _proposal_event(draft_record.get("draft", {}))
            proposal = home.replace_proposal(
                proposal["id"], event=event, draft_updated_at=draft_stamp,
                supersedes_event_id=revision_of,
            )
            session = _checkpoint_unlocked(
                home,
                session,
                stage="review",
                current_item_ref=values.get("experience_ref") or "new_experience",
                missing=missing_fields(values),
                proposal_refs=session["proposal_refs"],
                revision=current_revision + 1,
                entrypoint=entrypoint,
            )
            return _proposal_response(proposal, session_id, session["revision"], review_before=review_before)
        event, values = _proposal_event(draft_record.get("draft", {}))
        proposal = {
            "id": proposal_id,
            "kind": "event",
            "status": "pending",
            "created_at": utc_now(),
            "session_id": session_id,
            "draft_updated_at": draft_stamp,
            "next_action": "approve this proposal after checking the evidence and contribution",
            "event": event,
        }
        if isinstance(revision_of, str):
            proposal["supersedes_event_id"] = revision_of
        home.add_proposal(proposal)
        session = _checkpoint_unlocked(
            home,
            session,
            stage="review",
            current_item_ref=values.get("experience_ref") or "new_experience",
            missing=missing_fields(values),
            proposal_refs=[*session["proposal_refs"], proposal["id"]],
            revision=current_revision + 1,
            entrypoint=entrypoint,
        )
    return _proposal_response(proposal, session_id, session["revision"], review_before=review_before)


def _approved_result(home: CareerVault, proposal: dict[str, Any]) -> dict[str, Any]:
    event_id = proposal.get("approved_event_id")
    event = next((row for row in read_jsonl(home.events) if row.get("id") == event_id), None)
    if event is None:
        raise CareerError("approved proposal has no canonical event", code="APPROVAL_RECOVERY_FAILED")
    return {
        "approved": True,
        "idempotent": True,
        "event": event,
        "proposal": proposal,
        "version": proposal.get("version"),
    }


def _mark_approved_session(
    home: CareerVault, session_id: str, *, entrypoint: str = "unknown"
) -> dict[str, Any]:
    with vault_lock(home):
        session = _read_session(home, session_id)
        if session["status"] == "completed":
            return session
        completed = list(session["completed"])
        if "evidence_approved" not in completed:
            completed.append("evidence_approved")
        return _checkpoint_unlocked(
            home,
            session,
            stage="completed",
            current_item_ref=session["current_item_ref"],
            missing=session["missing_fields"],
            completed=completed,
            entrypoint=entrypoint,
        )


def approve_proposal(
    home: CareerVault,
    session_id: str,
    proposal_id: str,
    *,
    expected_revision: int | None = None,
    entrypoint: str = "unknown",
) -> dict[str, Any]:
    _validate_session_id(session_id)
    if not isinstance(proposal_id, str) or not proposal_id.strip():
        raise CareerError("proposal id is required", code="INVALID_INPUT")
    session = _read_session(home, session_id)
    current_revision = _current_revision(session, _read_draft(home, session_id))
    _expect_revision(expected_revision, current_revision)
    if proposal_id not in session["proposal_refs"]:
        raise CareerError("proposal does not belong to this session", code="INVALID_INPUT")
    proposal = next((row for row in _proposal_rows(home) if row.get("id") == proposal_id), None)
    if proposal is None:
        raise CareerError("proposal not found", code="PROPOSAL_NOT_FOUND")
    if proposal.get("status") == "approved":
        completed = _mark_approved_session(home, session_id, entrypoint=entrypoint)
        result = _approved_result(home, proposal)
        result["revision"] = completed["revision"]
        return result
    if proposal.get("status") != "pending":
        raise CareerError("proposal is not pending", code="PROPOSAL_NOT_PENDING")
    event = proposal.get("event")
    if not isinstance(event, dict):
        raise CareerError("proposal event is invalid", code="PROPOSAL_INVALID")

    def approval_precondition() -> None:
        """Recheck the browser's snapshot while the canonical approval lock is held."""
        latest_session = _read_session(home, session_id)
        latest_draft = _read_draft(home, session_id)
        latest_revision = _current_revision(latest_session, latest_draft)
        _expect_revision(expected_revision, latest_revision)
        if proposal_id not in latest_session["proposal_refs"]:
            raise CareerError("proposal does not belong to this session", code="INVALID_INPUT")
        latest_proposal = next(
            (row for row in _proposal_rows(home) if row.get("id") == proposal_id),
            None,
        )
        if latest_proposal is None:
            raise CareerError("proposal not found", code="PROPOSAL_NOT_FOUND")
        draft_stamp = str(latest_draft.get("updated_at") or "")
        if str(latest_proposal.get("draft_updated_at") or "") != draft_stamp:
            raise CareerError(
                "the draft changed after this proposal was created; create the proposal again",
                code="PROPOSAL_STALE",
            )
        latest_event = latest_proposal.get("event")
        if not isinstance(latest_event, dict):
            raise CareerError("proposal event is invalid", code="PROPOSAL_INVALID")
        revision_of = (latest_session.get("subject") or {}).get("revision_of")
        if isinstance(revision_of, str):
            _revision_source(home, revision_of, revision_of)
            if latest_proposal.get("supersedes_event_id") != revision_of:
                raise CareerError("experience revision is invalid", code="PROPOSAL_INVALID")
        # Preflight here prevents a rejected GUI approval from appending a failure trajectory.
        validate_event(latest_event, for_confirmation=True)

    result = approve_canonical(home, proposal_id, precondition=approval_precondition)
    completed = _mark_approved_session(home, session_id, entrypoint=entrypoint)
    result["session_id"] = session_id
    result["revision"] = completed["revision"]
    return result
