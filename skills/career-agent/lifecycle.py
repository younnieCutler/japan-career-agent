"""Approval, recovery, and safe-stop lifecycle for the Career Agent.

The lifecycle owns append-only approval semantics and recovery. Projection and
state-transition functions are injected by the compatibility facade so this
module remains independent of the runtime and can be tested in isolation.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None

from models import DOCUMENT_EVIDENCE_PREFIX, CareerError, document_evidence_ids
from personal_timeline import derive_intervals, facts_from_events
from persistence import append_jsonl, read_json, read_jsonl
from private_store import PrivateHome, resolve_private_home, resolve_document
from validation import validate_event
from vault import CareerVault, utc_now


PipelineWriter = Callable[[dict[str, Any]], Path | None]
StateProjector = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


@contextmanager
def vault_lock(home: CareerVault) -> Iterator[None]:
    """Serialize read-modify-write sections against other processes on one Vault."""
    home.ensure_runtime()
    lock_path = home.runtime / "lock"
    with lock_path.open("a+") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        elif msvcrt is not None:
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def count_consecutive_safe_stops(home: CareerVault, goal: str) -> int:
    count = 0
    for trajectory in reversed(read_jsonl(home.trajectories)):
        if trajectory.get("mode") == "chat" and trajectory.get("plan", {}).get("goal") == goal:
            count += 1
        else:
            break
    return count


def record_failed_attempt(
    home: CareerVault,
    mode: str,
    observe: dict[str, Any],
    error: Exception,
    *,
    retry_count: int = 0,
) -> None:
    home.append_trajectory(
        {
            "id": f"traj-{uuid.uuid4().hex[:12]}",
            "created_at": utc_now(),
            "mode": mode,
            "observe": observe,
            "plan": {"goal": "attempt failed"},
            "act": {"attempted": True},
            "verify": {"passed": False, "error": str(error)},
            "correct": {"action": "safe_stop", "escalated_to_user": True, "retry_count": retry_count},
            "persist": {"trajectory_only": True},
        }
    )


def state_version_is_persisted(home: CareerVault, state: dict[str, Any]) -> bool:
    version = state.get("version")
    if not isinstance(version, str) or not version:
        return False
    if not (home.versions / f"{version}.json").is_file():
        return False
    return any(row.get("version") == version for row in read_jsonl(home.checkpoints) if isinstance(row, dict))


def preflight_confirmation(home: CareerVault, event: dict[str, Any], ledger: list[dict[str, Any]]) -> None:
    """Check what confirming this event would make true, before anything is written.

    Approval *is* the canonical commit, so this is the last place an invariant can be enforced
    while it is still cheap. Validating the proposal alone is not enough: two corrections of the
    same fact are each individually valid, and only the pair is a fork. The check therefore runs
    against the whole ledger with the candidate appended, inside the approval lock.

    It runs before the pipeline writer for the same reason. An event carrying `--company` would
    otherwise update the workspace projection and then fail to reach the ledger, leaving the two
    disagreeing about something that never happened.
    """
    for document_id in document_evidence_ids(event.get("evidence")):
        # Re-resolved here, not trusted from proposal time: the private root can change between
        # proposing a fact and confirming it, and a reference that resolves to nothing looks
        # provenance-backed without being it.
        resolve_document(PrivateHome(resolve_private_home(None, home.path)), document_id)
    if event.get("fact") is None:
        return
    # `derive_intervals` owns every supersession invariant. Calling it here means the writer cannot
    # store a state the reader would reject -- previously the ledger accepted a fork and only the
    # next projection reported it, by which point the bad row was canonical.
    derive_intervals(facts_from_events([*ledger, event]))


def approve(
    home: CareerVault,
    proposal_id: str,
    evidence: list[str] | None = None,
    deadline: str | None = None,
    company: str | None = None,
    compensation: float | None = None,
    currency: str | None = None,
    workspace: str | Path | None = None,
    next_action: str | None = None,
    *,
    pipeline_writer: PipelineWriter | None = None,
    state_projector: StateProjector | None = None,
) -> dict[str, Any]:
    """Approve one pending proposal exactly once and preserve retry safety."""
    del workspace  # The injected writer owns workspace resolution.
    with vault_lock(home):
        proposal = next((row for row in read_jsonl(home.proposals) if row.get("id") == proposal_id), None)
        if not proposal:
            raise CareerError(f"proposal not found: {proposal_id}")
        if proposal.get("status") != "pending":
            raise CareerError(f"proposal is not pending: {proposal_id}")
        if proposal.get("kind") in {"event", "career_context"}:
            event = dict(proposal["event"])
            if evidence is not None:
                # `--evidence` replaces the list, which would silently destroy the provenance link
                # a fact proposal was built around: the reference to the document backing it. The
                # user adding a note is not the user saying the document is no longer the source.
                provenance = [
                    item for item in proposal["event"].get("evidence") or []
                    if isinstance(item, str) and item.startswith(DOCUMENT_EVIDENCE_PREFIX)
                ]
                event["evidence"] = evidence + [
                    item for item in provenance if item not in evidence
                ]
            if deadline is not None:
                event["deadline"] = deadline
            if company is not None:
                event["company"] = company
            if compensation is not None:
                event["compensation"] = compensation
            if currency is not None:
                event["currency"] = currency
            event["next_action"] = next_action.strip() if next_action and next_action.strip() else None
            try:
                validate_event(event, for_confirmation=True)
            except CareerError as exc:
                record_failed_attempt(home, "approve", {"proposal_id": proposal_id, "event": event}, exc)
                if str(exc).startswith("confirmed events require evidence"):
                    raise CareerError(
                        "confirmed events require evidence.\n"
                        f"Retry with: approve {proposal_id} --evidence \"<source or confirmation>\"\n"
                        "Unsupported claims remain drafts."
                    ) from exc
                if str(exc).startswith("numeric claim is not present in evidence"):
                    raise CareerError(
                        "numeric claim is not present in evidence.\n"
                        f'Retry with: approve {proposal_id} --evidence "<source or confirmation containing the exact numeric claim>"'
                    ) from exc
                raise
            event["status"] = "confirmed"
            existing_events = read_jsonl(home.events)
            try:
                preflight_confirmation(home, event, existing_events)
            except CareerError as exc:
                record_failed_attempt(home, "approve", {"proposal_id": proposal_id, "event": event}, exc)
                raise
            pipeline = pipeline_writer(event) if pipeline_writer and event.get("company") else None

            if not any(row.get("id") == event.get("id") for row in existing_events):
                append_jsonl(home.events, event)

            state = home.load_state()
            projected_state = state_projector(state, event) if state_projector else state
            if projected_state == state and state_version_is_persisted(home, state):
                version = state["version"]
            else:
                version = home.save_state(projected_state)
            resolved_at = utc_now()
            resolution = {
                "status": "approved",
                "resolved_at": resolved_at,
                "approved_event_id": event["id"],
                "state_version": version,
            }
            updated = home.replace_proposal(
                proposal_id,
                status="approved",
                approved_at=resolved_at,
                version=version,
                approved_event_id=event["id"],
                resolution=resolution,
            )
            result = {"approved": True, "event": event, "version": version, "proposal": updated}
            if pipeline:
                result["pipeline"] = str(pipeline)
            return result
        updated = home.replace_proposal(proposal_id, status="approved", approved_at=utc_now())
        return {
            "approved": True,
            "proposal": updated,
            "applied": False,
            "message": "Only event proposals change the local ledger; skill changes remain offline proposals.",
        }


def restore_state(home: CareerVault, version: str) -> dict[str, Any]:
    """Restore a state snapshot without rewinding append-only ledgers or projections."""
    snapshot = home.versions / f"{version}.json"
    if not snapshot.exists():
        raise CareerError(f"version not found: {version}")
    state = read_json(snapshot, {})
    if not isinstance(state, dict):
        raise CareerError(f"invalid version snapshot: {version}")
    with vault_lock(home):
        home.write_state(state)
        append_jsonl(home.checkpoints, {"version": version, "restored_at": utc_now(), "state": state})
    return {
        "restored": True,
        "version": version,
        "state": state,
        "ledger_retained": True,
        "note": "State only. events.jsonl, proposals.jsonl and data/pipeline.yml are unchanged.",
    }
