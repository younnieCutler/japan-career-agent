#!/usr/bin/env python3
"""Context, Experience and Evidence orchestration over the confirmed ledger.

Every write here is a proposal awaiting user approval. Reads project the ledger; they never
promote an Unknown, average a Conflict, or infer a link the user did not record.
"""

from __future__ import annotations

import uuid

from pathlib import Path
from typing import Any

from lifecycle import review_work_event, vault_lock
from models import (
    CareerError,
    CHUTO_STAGES,
    SHINSOTSU_STAGES,
    TRACKS,
    UNTRUSTED_DATA_MARKER,
    WORK_EVENT_TYPE,
)
from persistence import read_jsonl
from personal_timeline import select_personal_context
from private_store import documents as private_documents, PrivateHome, resolve_private_home
from projection import (
    contexts_from_events,
    experiences_from_events,
    project_timeline,
    projects_from_events,
    work_event_project_ids,
)
from proposals import make_experience_context_event, make_project_event
from validation import iso_date, validate_career_context, validate_event
from vault import CareerVault, select_context, utc_now


def latest_career_context(home: CareerVault) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    latest: dict[str, Any] | None = None
    for event in read_jsonl(home.events):
        if event.get("status") != "confirmed" or event.get("type") != "career_context":
            continue
        validate_event(event)
        validate_career_context(event.get("career_context"))
        latest = event
    if latest is None:
        return None, None
    return latest["career_context"], latest


def private_records(vault: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Document records for a Vault, or an explained absence.

    A private store is optional (section 25), so its absence or misconfiguration is a state to
    report, not a corruption to stop on. It must not vanish quietly either, hence the reason
    travelling in the payload rather than being swallowed.
    """
    try:
        store = PrivateHome(resolve_private_home(None, vault))
    except CareerError as exc:
        return [], str(exc).splitlines()[0]
    if not store.initialized():
        return [], None
    return private_documents(store), None


def run_context(
    home: CareerVault, requested_track: str | None, requested_stage: str | None, as_of: str,
) -> dict[str, Any]:
    """Shared, metadata-only context for other career skills and agent frontends."""
    profile = home.load_profile()
    state = home.load_state()
    track = requested_track or state.get("track") or profile.get("track")
    if track not in TRACKS:
        raise CareerError("shared context requires profile.track or --track")
    stage = requested_stage or state.get("stage")
    if stage is not None and stage not in SHINSOTSU_STAGES + CHUTO_STAGES:
        raise CareerError("shared context stage is not recognized")
    career_context, career_event = latest_career_context(home)
    profile_keys = ("track", "career_status", "target_role", "start_date", "graduation_year", "language", "flow_phase")
    return {
        "mode": "context",
        "vault": str(home.path),
        "as_of": as_of,
        "profile": {key: profile[key] for key in profile_keys if key in profile and profile[key] not in (None, "")},
        "state": state,
        "context": select_context(home.path, track, stage, as_of) if stage else [],
        "context_trust": {"data": UNTRUSTED_DATA_MARKER, "instruction_authority": "none"},
        "career_context": career_context,
        "career_context_confirmed": career_context is not None,
        "career_context_event_id": career_event.get("id") if career_event else None,
        # Section 12.1. Current, stage-relevant, capped, and confirmed-only -- never the whole
        # `project()` output, which returns every category and key. Documents are not here at all:
        # neither the relevance map nor the cap applies to them, so `private-list` and
        # `personal-context --historical` are the explicit paths.
        # A corrupt fact row raises rather than degrading this block, matching what
        # `latest_career_context` above already does for a corrupt career_context row: corrupt
        # canonical data stops the command. That is a different case from a private root that is
        # merely absent or misconfigured, which `private_records` reports and continues past.
        "personal_context": select_personal_context(read_jsonl(home.events), stage, as_of),
        "read_only": True,
        "note_bodies_included": False,
    }


def work_events(
    home: CareerVault, *, confirmed_only: bool = False, as_of: str | None = None,
) -> dict[str, Any]:
    """Read work events out of the ledger. This is the contract downstream skills use.

    Matching a JD against career evidence needs the evidence, and the alternative to a query is
    every skill parsing `events.jsonl` for itself -- which is how "only confirmed evidence counts"
    stops being one rule and becomes several that drift. Reading is all this does: nothing here
    writes, and the caller receives a copy.

    `as_of` filters by `occurred_at`, inclusive. Note what that is and is not: `occurred_at` is
    when the note was *captured*, not when the work happened. Someone writing up a project from
    last June today gets an event dated today, so this bounds the ledger reproducibly but is not
    yet a recency signal about the work itself. A `work_date` on the payload is the fix and is not
    in this change.

    The boundary is a UTC date because `occurred_at` is a UTC instant; a local calendar boundary
    would compare two different things and silently drop an event recorded minutes ago.
    """
    rows = [row for row in read_jsonl(home.events) if row.get("type") == WORK_EVENT_TYPE]
    if confirmed_only:
        # Confirmed means confirmed: a draft is a proposal the user has not verified, and a
        # superseded row is history that a later record replaced. Neither may be quoted as current
        # evidence in a document that goes to someone else.
        rows = [row for row in rows if row.get("status") == "confirmed"]
    if as_of:
        # `occurred_at` is stored in UTC, as everywhere else on the ledger.
        boundary = iso_date(as_of, "--as-of")
        rows = [row for row in rows if str(row.get("occurred_at") or "")[:10] <= boundary]
    return {
        "mode": "work-events",
        "vault": str(home.path),
        "as_of": as_of,
        "confirmed_only": confirmed_only,
        "count": len(rows),
        "work_events": rows,
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "ok": True,
    }


def add_project(
    home: CareerVault, title: str, *, project_id: str | None = None, **fields: Any,
) -> dict[str, Any]:
    """Propose a project, or an update to one that already exists.

    Goes through the same proposal the rest of the ledger uses, so the confirmation the UX already
    asks for ("연결할까요?") is the approval, not an extra step on top of it.
    """
    known = projects_from_events(read_jsonl(home.events))
    if project_id is not None and project_id not in known:
        raise CareerError(f"unknown project id: {project_id}", code="PROJECT_NOT_FOUND")
    event = make_project_event(title, project_id, fields=fields)
    proposal_id = f"proposal-{uuid.uuid4().hex[:12]}"
    proposal = {
        "id": proposal_id,
        "kind": "event",
        "status": "pending",
        "created_at": utc_now(),
        # The proposal id, not the project id: `approve` takes the former, and naming the latter
        # here handed the user a command that cannot work.
        "next_action": f"approve {proposal_id} after checking the title and role",
        "event": event,
    }
    with vault_lock(home):
        home.add_proposal(proposal)
    return {
        "mode": "add-project",
        "vault": str(home.path),
        "project": event["project"],
        "proposal": {"id": proposal["id"], "status": proposal["status"]},
        "updates_existing": project_id is not None,
        "ok": True,
    }


def add_context(
    home: CareerVault, kind: str, label: str, *, context_id: str | None = None, **fields: Any,
) -> dict[str, Any]:
    """Propose a context, or an update to one that already exists.

    Same proposal path as `add-project`, so the confirmation the UX already asks for is the
    approval rather than a second step on top of it.
    """
    known = contexts_from_events(read_jsonl(home.events))
    if context_id is not None and context_id not in known:
        raise CareerError(f"unknown context id: {context_id}", code="CONTEXT_NOT_FOUND")
    event = make_experience_context_event(kind, label, context_id, fields=fields)
    proposal_id = f"proposal-{uuid.uuid4().hex[:12]}"
    proposal = {
        "id": proposal_id,
        "kind": "event",
        "status": "pending",
        "created_at": utc_now(),
        "next_action": f"approve {proposal_id} after checking the kind and the period",
        "event": event,
    }
    with vault_lock(home):
        home.add_proposal(proposal)
    return {
        "mode": "add-context",
        "vault": str(home.path),
        "context": event["experience_context"],
        "proposal": {"id": proposal["id"], "status": proposal["status"]},
        "updates_existing": context_id is not None,
        "ok": True,
    }


def list_contexts(home: CareerVault, *, kind: str | None = None) -> dict[str, Any]:
    """Every confirmed context with how many experiences and how much evidence hang on it."""
    events = read_jsonl(home.events)
    grouped = experiences_from_events(events)
    per_context_experiences: dict[str, int] = {}
    per_context_evidence: dict[str, int] = {}
    for experience in grouped["experiences"]:
        key = str(experience.get("context_id") or "")
        per_context_experiences[key] = per_context_experiences.get(key, 0) + 1
        per_context_evidence[key] = (
            per_context_evidence.get(key, 0) + len(experience["evidence_event_ids"])
        )
    rows = [
        {
            **record,
            "experiences": per_context_experiences.get(context_id, 0),
            "confirmed_evidence": per_context_evidence.get(context_id, 0),
        }
        for context_id, record in grouped["contexts"].items()
        if kind is None or record.get("kind") == kind
    ]
    rows.sort(key=lambda row: (str(row.get("kind") or ""), str(row.get("label") or "")))
    return {
        "mode": "contexts",
        "vault": str(home.path),
        "count": len(rows),
        "contexts": rows,
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "ok": True,
    }


def list_experiences(home: CareerVault, *, context_id: str | None = None) -> dict[str, Any]:
    """Context -> Experience -> Evidence over the confirmed ledger.

    This is the 棚卸し progress view and the read a document projection starts from. It stores
    nothing: an experience is the set of confirmed evidence naming the same project or the same
    reference, so re-linking a note rewrites no history and the same evidence never exists twice.

    There is no completion percentage. What the view answers is "can a decision quote the user's
    own experience", and the gaps are named individually so a missing contribution stays visible
    instead of being averaged into a number that looks like progress.
    """
    grouped = experiences_from_events(read_jsonl(home.events))
    rows = [
        experience
        for experience in grouped["experiences"]
        if context_id is None or experience.get("context_id") == context_id
    ]
    if context_id is not None and context_id not in grouped["contexts"]:
        raise CareerError(f"unknown context id: {context_id}", code="CONTEXT_NOT_FOUND")
    return {
        "mode": "experiences",
        "vault": str(home.path),
        "count": len(rows),
        "contexts": grouped["contexts"],
        "experiences": rows,
        # Evidence that belongs to no recorded experience is still evidence. Hiding it would make
        # the record look tidier than it is.
        "unattached_evidence_ids": grouped["unattached_evidence_ids"],
        "gaps": {
            "experiences_without_individual_contribution": [
                row["experience_id"] for row in rows if not row["individual_contribution"]
            ],
            "experiences_without_context": [
                row["experience_id"] for row in rows if not row.get("context_id")
            ],
            "evidence_awaiting_external_use_review": [
                event_id for row in rows for event_id in row["external_use_review_required"]
            ],
        },
        "entries_are_references": True,
        "no_total_by_design": True,
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "ok": True,
    }


def list_projects(home: CareerVault, *, status: str | None = None) -> dict[str, Any]:
    """Every confirmed project with how much evidence hangs on it."""
    events = read_jsonl(home.events)
    projects = projects_from_events(events)
    counts: dict[str, int] = {}
    for event in events:
        if event.get("type") != WORK_EVENT_TYPE or event.get("status") != "confirmed":
            continue
        for project_id in work_event_project_ids(event):
            counts[project_id] = counts.get(project_id, 0) + 1
    rows = [
        {**record, "confirmed_work_events": counts.get(project_id, 0)}
        for project_id, record in projects.items()
        if status is None or record.get("status") == status
    ]
    rows.sort(key=lambda row: (row.get("status") != "active", str(row.get("title") or "")))
    return {
        "mode": "projects",
        "vault": str(home.path),
        "count": len(rows),
        "projects": rows,
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "ok": True,
    }


def show_project_timeline(home: CareerVault, project_id: str) -> dict[str, Any]:
    """One project's confirmed work events in time order, as references to the ledger."""
    events = read_jsonl(home.events)
    projects = projects_from_events(events)
    if project_id not in projects:
        raise CareerError(f"unknown project id: {project_id}", code="PROJECT_NOT_FOUND")
    entries = project_timeline(events, project_id)
    return {
        "mode": "project-timeline",
        "vault": str(home.path),
        "project": projects[project_id],
        "count": len(entries),
        "timeline": entries,
        # Every row points at a ledger event. Nothing here is a second copy of the history.
        "entries_are_references": True,
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "ok": True,
    }


def link_work_event(
    home: CareerVault,
    proposal_id: str,
    *,
    primary: str | None = None,
    related: list[str] | None = None,
    clear: bool = False,
) -> dict[str, Any]:
    """Point a pending work event at projects, or at none.

    A link is a reference. One canonical work event is pointed at by every project it belongs to,
    so a note spanning three projects is stored once and appears in three timelines -- copying it
    per project would create three facts where the user lived one.

    `clear` records "no project / general work", which is a real answer. Capture is never blocked
    on choosing a project.
    """
    known = set(projects_from_events(read_jsonl(home.events)))
    unknown = sorted({item for item in [primary, *(related or [])] if item and item not in known})
    if unknown:
        raise CareerError(f"unknown project id: {', '.join(unknown)}", code="PROJECT_NOT_FOUND")
    if clear:
        patch: dict[str, Any] = {"primary_project_id": None, "related_project_ids": []}
    else:
        patch = {}
        if primary is not None:
            patch["primary_project_id"] = primary
        if related is not None:
            patch["related_project_ids"] = [item for item in related if item != primary]
    result = review_work_event(home, proposal_id, patch)
    result["mode"] = "link-work-event"
    return result


def pending_work_events(home: CareerVault) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Work events captured but not yet approved, and the proposal id each one came in on.

    A quick note lives on `proposals.jsonl` until it is approved, so any view that reads only the
    ledger shows a week with nothing in it precisely when the user has been capturing all week.
    Every view of recent activity needs these, which is why they are read in one place.
    """
    pending: list[dict[str, Any]] = []
    proposal_of: dict[str, str] = {}
    for row in read_jsonl(home.proposals):
        event = row.get("event")
        if row.get("status") != "pending" or not isinstance(event, dict):
            continue
        if event.get("type") != WORK_EVENT_TYPE:
            continue
        proposal_of[event["id"]] = row["id"]
        pending.append(event)
    return pending, proposal_of
