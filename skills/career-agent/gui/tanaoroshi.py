"""Semantic-state adapter for the GUI's deterministic 棚卸し form."""

from __future__ import annotations

from typing import Any

from sessions import (
    assign_session_project,
    archive_session,
    approve_proposal,
    checkpoint_session,
    create_proposal,
    create_revision_session,
    create_session,
    list_sessions,
    resume_session,
    restore_session,
    save_draft,
)


_DRAFT_INTERNAL = {
    "context_id", "primary_project_id", "related_project_ids", "experience_ref", "non_work",
}
_PROFILE_INTERNAL = {"id", "episode_ref", "evidence_episode_refs"}


def _public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _public_value(child)
            for key, child in value.items()
            if key not in _PROFILE_INTERNAL
        }
    if isinstance(value, list):
        return [_public_value(child) for child in value]
    return value


def _public_session(session: dict[str, Any]) -> dict[str, Any]:
    subject = session.get("subject") if isinstance(session.get("subject"), dict) else {}
    return {
        "session_ref": session.get("session_id"),
        "workflow": session.get("workflow"),
        "stage": session.get("stage"),
        "status": session.get("status"),
        "revision": session.get("revision"),
        "started_by": session.get("started_by"),
        "last_entrypoint": session.get("last_entrypoint"),
        "subject": {
            key: value
            for key, value in subject.items()
            if key.endswith("_label") or key in {"context_kind"}
        },
        "display_context": list(session.get("display_context", [])),
        "remaining_work": list(session.get("remaining_work", session.get("missing_fields", []))),
        "updated_at": session.get("updated_at"),
    }


def _public_draft(draft: Any) -> dict[str, Any]:
    if not isinstance(draft, dict):
        return {}
    return _public_value({key: value for key, value in draft.items() if key not in _DRAFT_INTERNAL})


def _public_event(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {}
    visible = {
        key: value
        for key, value in event.items()
        if key in {"work_event", "experience", "experience_context", "project", "career_context", "evidence"}
    }
    if ("work_event" in visible or "experience" in visible) and event.get("summary"):
        visible["claim_summary"] = event["summary"]
    return _public_value(visible)


def present(payload: dict[str, Any]) -> dict[str, Any]:
    """Expose user concepts and only the opaque refs required for the next API call."""
    result = {
        key: value
        for key, value in payload.items()
        if key in {
            "mode", "ok", "approved", "idempotent", "revision", "missing_fields",
            "field_status", "unconfirmed_input", "write_recovery_required", "count", "read_only",
        }
    }
    if isinstance(payload.get("session"), dict):
        result["session"] = _public_session(payload["session"])
    elif payload.get("session_id") and payload.get("workflow"):
        result["session"] = _public_session(payload)
    elif payload.get("session_id"):
        result["session_ref"] = payload.get("session_id")
    if isinstance(payload.get("sessions"), list):
        result["sessions"] = [_public_session(row) for row in payload["sessions"]]
    if "draft" in payload:
        result["draft"] = _public_draft(payload.get("draft"))
    if isinstance(payload.get("review_before"), dict):
        result["review_before"] = _public_value(payload["review_before"])
    proposal = payload.get("proposal")
    if isinstance(proposal, dict):
        result["proposal"] = {
            "ref": proposal.get("id"),
            "status": proposal.get("status"),
            "event": _public_event(proposal.get("event")),
        }
    return result


def active(home: Any) -> dict[str, Any]:
    """Resumable sessions from disk. The client cannot remember an id across a restart."""
    return present(list_sessions(home))


def start(home: Any, *, case_ref: str | None = None) -> dict[str, Any]:
    session = create_session(
        home,
        case_ref=case_ref,
        entrypoint="gui",
    )
    resumed = resume_session(home, session["session_id"])
    return present({"mode": "career-inventory", **resumed})


def revise(home: Any, event_id: str, *, expected_revision: str) -> dict[str, Any]:
    session = create_revision_session(
        home, event_id, expected_revision=expected_revision, entrypoint="gui",
    )
    resumed = resume_session(home, session["session_id"])
    return present({"mode": "career-inventory-revision", **resumed})


def resume(home: Any, session_id: str) -> dict[str, Any]:
    return present(resume_session(home, session_id))


def assign_project(
    home: Any,
    session_id: str,
    case_ref: str,
    *,
    expected_revision: int,
) -> dict[str, Any]:
    return assign_session_project(
        home,
        session_id,
        case_ref,
        expected_revision=expected_revision,
        entrypoint="gui",
    )


def autosave(
    home: Any,
    session_id: str,
    draft: dict[str, Any],
    *,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    return save_draft(
        home,
        session_id,
        draft,
        expected_revision=expected_revision,
        entrypoint="gui",
    )


def checkpoint(home: Any, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("checkpoint payload must be an object")
    if "page" in payload or "page_number" in payload:
        raise ValueError("semantic checkpoints must not contain page numbers")
    return checkpoint_session(
        home,
        session_id,
        stage=payload.get("stage"),
        current_item_ref=payload.get("current_item_ref"),
        missing=payload.get("missing_fields"),
        completed=payload.get("completed"),
        expected_revision=payload.get("expected_revision"),
        entrypoint="gui",
    )


def submit(
    home: Any, session_id: str, *, expected_revision: int | None = None
) -> dict[str, Any]:
    return create_proposal(
        home,
        session_id,
        expected_revision=expected_revision,
        entrypoint="gui",
    )


def approve_session(
    home: Any,
    session_id: str,
    proposal_id: str,
    *,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    return approve_proposal(
        home,
        session_id,
        proposal_id,
        expected_revision=expected_revision,
        entrypoint="gui",
    )


def archive(
    home: Any, session_id: str, *, expected_revision: int | None = None
) -> dict[str, Any]:
    return archive_session(
        home,
        session_id,
        expected_revision=expected_revision,
        entrypoint="gui",
    )


def restore(
    home: Any, session_id: str, *, expected_revision: int | None = None
) -> dict[str, Any]:
    return restore_session(
        home,
        session_id,
        expected_revision=expected_revision,
        entrypoint="gui",
    )
