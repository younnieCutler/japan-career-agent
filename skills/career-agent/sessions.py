"""Application-owned, resumable workflow sessions for the local GUI.

Sessions and drafts are transient user work. They never replace the Career Vault ledger: only the
existing proposal and approval path can promote a submitted draft into canonical evidence.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from approvals import approve as approve_canonical
from lifecycle import vault_lock
from models import CareerError
from persistence import atomic_write_text, read_json, read_jsonl
from proposals import make_work_event
from validation import validate_event, validate_work_event
from vault import CareerVault, utc_now


CURRENT_SESSION_SCHEMA_VERSION = 1
SESSION_SCHEMA_VERSION = CURRENT_SESSION_SCHEMA_VERSION
SESSION_WORKFLOW = "tanaoroshi"
SESSION_STAGES = frozenset({"experience_evidence", "review", "completed"})
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


def session_path(home: CareerVault, session_id: str) -> Path:
    return storage_paths(home)["sessions"] / f"{_validate_session_id(session_id)}.json"


def draft_path(home: CareerVault, session_id: str) -> Path:
    return storage_paths(home)["drafts"] / f"{_validate_session_id(session_id)}.json"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _new_session(home: CareerVault, case_ref: str | None) -> dict[str, Any]:
    session_id = f"session-{uuid.uuid4().hex[:16]}"
    return {
        "session_id": session_id,
        "session_schema_version": CURRENT_SESSION_SCHEMA_VERSION,
        "workflow": SESSION_WORKFLOW,
        "stage": "experience_evidence",
        "case_ref": case_ref,
        "current_item_ref": None,
        "missing_fields": [
            "role",
            "direct_actions",
            "individual_contribution",
            "metrics",
            "confidentiality.external_use",
        ],
        "completed": [],
        "draft_ref": draft_path(home, session_id).relative_to(home.path).as_posix(),
        "proposal_refs": [],
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
        "case_ref",
        "current_item_ref",
        "missing_fields",
        "completed",
        "draft_ref",
        "proposal_refs",
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
    if version != CURRENT_SESSION_SCHEMA_VERSION or record.get("workflow") != SESSION_WORKFLOW:
        raise CareerError("session workflow or schema is unsupported", code="SESSION_INVALID")
    if record.get("stage") not in SESSION_STAGES:
        raise CareerError("session stage is not a semantic 棚卸し stage", code="SESSION_INVALID")
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
    if not isinstance(current_stage, str) or current_stage not in SESSION_STAGES:
        raise CareerError(
            "v0 session has no supported semantic stage; the session was not changed",
            code="SESSION_MIGRATION_INVALID",
            retryable=False,
        )
    migrated["session_schema_version"] = CURRENT_SESSION_SCHEMA_VERSION
    return migrated


def register_session_migration(
    from_version: int, migration: Callable[[dict[str, Any]], dict[str, Any]]
) -> None:
    """Provide the explicit hook used by the later v0→v1 migration PR."""
    if from_version < 0 or not callable(migration):
        raise CareerError("invalid session migration", code="INVALID_INPUT")
    SESSION_MIGRATIONS[from_version] = migration


register_session_migration(0, _migrate_v0_session)


def _migrate_v0_draft(record: dict[str, Any]) -> dict[str, Any]:
    """A v0 draft differs from a v1 draft only by its version stamp.

    The v0→v1 change was to the session record: `page` became a semantic `stage`. Drafts held the
    user's field values then and hold them now. Stamping the version is the whole migration, and
    saying so explicitly is what keeps the pair resumable — migrating the session while refusing
    the draft written beside it leaves a vault that opens halfway.
    """
    migrated = dict(record)
    migrated["session_schema_version"] = CURRENT_SESSION_SCHEMA_VERSION
    return migrated


DRAFT_MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {0: _migrate_v0_draft}


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


def _draft_values(value: Any, *, allow_empty_summary: bool = True) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CareerError("draft must be an object", code="INVALID_INPUT")
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
        return {"session_id": session_id, "updated_at": "", "draft": {}}
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
    _draft_values(record["draft"])
    return record


def create_session(home: CareerVault, *, case_ref: str | None = None) -> dict[str, Any]:
    if case_ref is not None and (not isinstance(case_ref, str) or not case_ref.strip()):
        raise CareerError("case_ref must be a non-empty string or null", code="INVALID_INPUT")
    with vault_lock(home):
        session = _new_session(home, case_ref)
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
                "draft": {},
                "updated_at": "",
            },
        )
    return session


def load_session(home: CareerVault, session_id: str) -> dict[str, Any]:
    return _read_session(home, session_id)


def list_sessions(home: CareerVault) -> dict[str, Any]:
    """Every resumable session, so a client never has to remember an id across restarts.

    The server binds port 0, so each run gives the browser a different origin and localStorage
    starts empty. The sessions on disk are the only thing that survives; without this the user
    cannot reach work that is sitting there intact.
    """
    rows: list[dict[str, Any]] = []
    for path in sorted(storage_paths(home)["sessions"].glob("session-*.json")):
        if SESSION_ID.fullmatch(path.stem) is None:
            continue
        session = _read_session(home, path.stem)
        if session["stage"] != "completed":
            rows.append(session)
    rows.sort(key=lambda item: (item["updated_at"], item["session_id"]), reverse=True)
    return {"mode": "sessions", "sessions": rows, "count": len(rows), "read_only": True}


def missing_fields(draft: dict[str, Any]) -> list[str]:
    _draft_values(draft)
    missing: list[str] = []
    if not str(draft.get("role") or "").strip():
        missing.append("role")
    if not draft.get("direct_actions"):
        missing.append("direct_actions")
    if not str(draft.get("individual_contribution") or "").strip():
        missing.append("individual_contribution")
    if not draft.get("metrics"):
        missing.append("metrics")
    confidentiality = draft.get("confidentiality")
    external_use = confidentiality.get("external_use") if isinstance(confidentiality, dict) else None
    if external_use in (None, "", "unknown"):
        missing.append("confidentiality.external_use")
    return missing


def field_status(draft: dict[str, Any]) -> list[dict[str, str]]:
    missing = set(missing_fields(draft))
    labels = {
        "role": "역할",
        "direct_actions": "행동",
        "individual_contribution": "개인 기여",
        "metrics": "결과 수치",
        "confidentiality.external_use": "외부 공개 가능 여부",
    }
    return [
        {"field": field, "label": label, "status": "Unknown" if field in missing else "Confirmed"}
        for field, label in labels.items()
    ]


def save_draft(home: CareerVault, session_id: str, draft: dict[str, Any]) -> dict[str, Any]:
    with vault_lock(home):
        session = _read_session(home, session_id)
        _refuse_completed_session(session, "record another experience")
        values = _draft_values(draft)
        record = {
            "session_id": session_id,
            "session_schema_version": CURRENT_SESSION_SCHEMA_VERSION,
            "workflow": SESSION_WORKFLOW,
            "draft": values,
            "updated_at": _timestamp(),
        }
        _write_json(draft_path(home, session_id), record)
        return {
            "session": session,
            "draft": values,
            "missing_fields": missing_fields(values),
            "field_status": field_status(values),
            "unconfirmed_input": True,
        }


def resume_session(home: CareerVault, session_id: str) -> dict[str, Any]:
    session = _read_session(home, session_id)
    draft_record = _read_draft(home, session_id)
    draft = draft_record.get("draft", {})
    draft_updated = str(draft_record.get("updated_at") or "")
    session_updated = str(session.get("updated_at") or "")
    return {
        "mode": "tanaoroshi-resume",
        "session": session,
        "draft": draft,
        "missing_fields": missing_fields(draft),
        "field_status": field_status(draft),
        "unconfirmed_input": bool(draft_updated and draft_updated > session_updated),
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
) -> dict[str, Any]:
    next_stage = stage or session["stage"]
    if next_stage not in SESSION_STAGES:
        raise CareerError("checkpoint stage is not a semantic 棚卸し stage", code="INVALID_INPUT")
    if current_item_ref is not None and (not isinstance(current_item_ref, str) or not current_item_ref.strip()):
        raise CareerError("current_item_ref must be a non-empty string or null", code="INVALID_INPUT")
    for name, value in (("missing_fields", missing), ("completed", completed), ("proposal_refs", proposal_refs)):
        if value is not None and (not isinstance(value, list) or any(not isinstance(item, str) for item in value)):
            raise CareerError(f"{name} must be a list of strings", code="INVALID_INPUT")
    updated = {
        **session,
        "stage": next_stage,
        "current_item_ref": current_item_ref if current_item_ref is not None else session["current_item_ref"],
        "missing_fields": list(missing if missing is not None else session["missing_fields"]),
        "completed": list(completed if completed is not None else session["completed"]),
        "proposal_refs": list(proposal_refs if proposal_refs is not None else session["proposal_refs"]),
        "updated_at": _timestamp(),
    }
    _validate_session(updated, home, session["session_id"])
    _write_json(session_path(home, session["session_id"]), updated)
    return updated


def checkpoint_session(
    home: CareerVault,
    session_id: str,
    *,
    stage: str | None = None,
    current_item_ref: str | None = None,
    missing: list[str] | None = None,
    completed: list[str] | None = None,
) -> dict[str, Any]:
    with vault_lock(home):
        return _checkpoint_unlocked(
            home,
            _read_session(home, session_id),
            stage=stage,
            current_item_ref=current_item_ref,
            missing=missing,
            completed=completed,
        )


def _proposal_rows(home: CareerVault) -> list[dict[str, Any]]:
    return read_jsonl(home.proposals)


def _refuse_completed_session(session: dict[str, Any], action: str) -> None:
    """An approved session is a closed record; the next experience needs its own session.

    Without this a completed session keeps accepting drafts, and the proposal it already had
    approved is the one the next approval finds.
    """
    if session.get("stage") == "completed":
        raise CareerError(
            f"this 棚卸し session is already approved; start a new session to {action}",
            code="SESSION_COMPLETED",
        )


def _proposal_response(proposal: dict[str, Any], session_id: str) -> dict[str, Any]:
    # The event travels with the response so the screen can show what approval will write. An
    # approval button next to text the caller never received is a button the user cannot check.
    return {
        "mode": "tanaoroshi-proposal",
        "session_id": session_id,
        "proposal": {
            "id": proposal["id"],
            "status": proposal["status"],
            "created_at": proposal.get("created_at", ""),
            "draft_updated_at": proposal.get("draft_updated_at", ""),
            "event": proposal.get("event", {}),
        },
        "ok": True,
    }


def _proposal_event(draft: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    values = _draft_values(draft, allow_empty_summary=False)
    event = make_work_event(str(values["summary"]), non_work=values.get("non_work", False))
    event["evidence"] = list(values.get("evidence", []))
    payload = {key: item for key, item in values.items() if key not in {"summary", "evidence", "non_work"}}
    event["experience" if values.get("non_work", False) else "work_event"] = payload
    validate_event(event)
    return event, values


def create_proposal(home: CareerVault, session_id: str) -> dict[str, Any]:
    with vault_lock(home):
        session = _read_session(home, session_id)
        _refuse_completed_session(session, "propose from")
        proposal_id = f"proposal-{session_id.removeprefix('session-')}"
        draft_record = _read_draft(home, session_id)
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
                    _checkpoint_unlocked(
                        home,
                        session,
                        stage="review",
                        current_item_ref=session["current_item_ref"] or "new_experience",
                        proposal_refs=[*session["proposal_refs"], proposal["id"]],
                    )
                return _proposal_response(proposal, session_id)
            # The draft moved after this proposal was taken. Re-snapshot in place rather than
            # leaving a pending proposal that no longer matches what the user is looking at.
            event, values = _proposal_event(draft_record.get("draft", {}))
            proposal = home.replace_proposal(
                proposal["id"], event=event, draft_updated_at=draft_stamp
            )
            _checkpoint_unlocked(
                home,
                session,
                stage="review",
                current_item_ref=values.get("experience_ref") or "new_experience",
                missing=missing_fields(values),
                proposal_refs=session["proposal_refs"],
            )
            return _proposal_response(proposal, session_id)
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
        home.add_proposal(proposal)
        _checkpoint_unlocked(
            home,
            session,
            stage="review",
            current_item_ref=values.get("experience_ref") or "new_experience",
            missing=missing_fields(values),
            proposal_refs=[*session["proposal_refs"], proposal["id"]],
        )
    return _proposal_response(proposal, session_id)


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


def _mark_approved_session(home: CareerVault, session_id: str) -> None:
    with vault_lock(home):
        session = _read_session(home, session_id)
        completed = list(session["completed"])
        if "evidence_approved" not in completed:
            completed.append("evidence_approved")
        _checkpoint_unlocked(
            home,
            session,
            stage="completed",
            current_item_ref=session["current_item_ref"],
            missing=session["missing_fields"],
            completed=completed,
        )


def approve_proposal(home: CareerVault, session_id: str, proposal_id: str) -> dict[str, Any]:
    _validate_session_id(session_id)
    if not isinstance(proposal_id, str) or not proposal_id.strip():
        raise CareerError("proposal id is required", code="INVALID_INPUT")
    session = _read_session(home, session_id)
    if proposal_id not in session["proposal_refs"]:
        raise CareerError("proposal does not belong to this session", code="INVALID_INPUT")
    proposal = next((row for row in _proposal_rows(home) if row.get("id") == proposal_id), None)
    if proposal is None:
        raise CareerError("proposal not found", code="PROPOSAL_NOT_FOUND")
    if proposal.get("status") == "approved":
        _mark_approved_session(home, session_id)
        return _approved_result(home, proposal)
    if proposal.get("status") != "pending":
        raise CareerError("proposal is not pending", code="PROPOSAL_NOT_PENDING")
    # A proposal is a snapshot of the draft at one moment, and `create_proposal` re-snapshots when
    # the draft has moved. Nothing forces a caller through that path, though: the approve button
    # the browser already rendered carries an id that stays valid across an autosave. Comparing
    # here is what makes the guarantee independent of the client -- approval writes the text the
    # snapshot holds, so if that is no longer the draft, refuse rather than record the older
    # wording as a confirmed fact.
    draft_stamp = str(_read_draft(home, session_id).get("updated_at") or "")
    if str(proposal.get("draft_updated_at") or "") != draft_stamp:
        raise CareerError(
            "the draft changed after this proposal was created; create the proposal again",
            code="PROPOSAL_STALE",
        )
    event = proposal.get("event")
    if not isinstance(event, dict):
        raise CareerError("proposal event is invalid", code="PROPOSAL_INVALID")
    # Preflight through the canonical validator keeps a rejected GUI approval from appending a
    # failure trajectory. The actual commit still goes through approvals.approve -> lifecycle.
    validate_event(event, for_confirmation=True)
    result = approve_canonical(home, proposal_id)
    _mark_approved_session(home, session_id)
    result["session_id"] = session_id
    return result
