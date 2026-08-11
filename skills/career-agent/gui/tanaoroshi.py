"""Semantic-state adapter for the GUI's deterministic 棚卸し form."""

from __future__ import annotations

from typing import Any

from sessions import (
    approve_proposal,
    checkpoint_session,
    create_proposal,
    create_session,
    resume_session,
    save_draft,
)


def start(home: Any, *, case_ref: str | None = None) -> dict[str, Any]:
    session = create_session(home, case_ref=case_ref)
    resumed = resume_session(home, session["session_id"])
    return {"mode": "tanaoroshi", **resumed}


def resume(home: Any, session_id: str) -> dict[str, Any]:
    return resume_session(home, session_id)


def autosave(home: Any, session_id: str, draft: dict[str, Any]) -> dict[str, Any]:
    return save_draft(home, session_id, draft)


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
    )


def submit(home: Any, session_id: str) -> dict[str, Any]:
    return create_proposal(home, session_id)


def approve_session(home: Any, session_id: str, proposal_id: str) -> dict[str, Any]:
    return approve_proposal(home, session_id, proposal_id)
