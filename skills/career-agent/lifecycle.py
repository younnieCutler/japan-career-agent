"""Approval, recovery, and safe-stop lifecycle for the Career Agent.

The lifecycle owns append-only approval semantics and recovery. Projection and
state-transition functions are injected by the compatibility facade so this
module remains independent of the runtime and can be tested in isolation.
"""

from __future__ import annotations

import hashlib
import json
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

from models import (
    EVIDENCE_EVENT_TYPES,
    ApprovalStage,
    ApprovalTransactionRecord,
    CareerError,
    DOCUMENT_EVIDENCE_PREFIX,
    ProposalKind,
    ProposalStatus,
    WORK_EVENT_TYPE,
    document_evidence_ids,
)
from personal_timeline import derive_intervals, facts_from_events
from persistence import append_jsonl, read_json, read_jsonl, write_json
from private_store import PrivateHome, resolve_private_home, resolve_document
from validation import validate_event, validate_work_event
from vault import CareerVault, utc_now


PipelineWriter = Callable[[dict[str, Any]], Path | None]
StateProjector = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]

APPROVAL_TRANSACTION_STAGES = tuple(stage.value for stage in ApprovalStage)
APPROVAL_TRANSACTION_FILENAME = "approval-transaction.json"


def approval_transaction_path(home: CareerVault) -> Path:
    return home.runtime / APPROVAL_TRANSACTION_FILENAME


def read_approval_transaction(home: CareerVault) -> dict[str, Any] | None:
    path = approval_transaction_path(home)
    if not path.exists():
        return None
    value = read_json(path, None)
    if not isinstance(value, dict):
        raise CareerError(
            f"invalid approval transaction: {path}",
            code="APPROVAL_RECOVERY_FAILED",
            retryable=False,
        )
    if value.get("stage") not in APPROVAL_TRANSACTION_STAGES:
        raise CareerError(
            f"invalid approval transaction stage: {value.get('stage')!r}",
            code="APPROVAL_RECOVERY_FAILED",
            retryable=False,
        )
    if not isinstance(value.get("proposal_id"), str) or not isinstance(value.get("event"), dict):
        raise CareerError(
            "approval transaction is missing its proposal or event",
            code="APPROVAL_RECOVERY_FAILED",
            retryable=False,
        )
    return value


def _event_fingerprint(event: dict[str, Any]) -> str:
    payload = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_transaction(home: CareerVault, transaction: dict[str, Any]) -> None:
    home.ensure_runtime()
    try:
        record = ApprovalTransactionRecord.from_dict(transaction)
    except ValueError as exc:
        raise _recovery_error("invalid approval transaction record") from exc
    write_json(approval_transaction_path(home), record.to_dict())


def _advance_transaction(home: CareerVault, transaction: dict[str, Any], stage: str, **changes: Any) -> None:
    transaction.update(changes)
    transaction["stage"] = stage
    _write_transaction(home, transaction)


def _clear_transaction(home: CareerVault) -> None:
    approval_transaction_path(home).unlink(missing_ok=True)


def _recovery_error(message: str, **details: Any) -> CareerError:
    return CareerError(
        message,
        code="APPROVAL_RECOVERY_FAILED",
        retryable=False,
        details=details,
        state_changed=True,
    )


@contextmanager
def vault_lock(home: CareerVault) -> Iterator[None]:
    """Serialize read-modify-write sections against other processes on one Vault."""
    home.ensure_runtime()
    lock_path = home.runtime / "lock"
    with lock_path.open("a+b") as handle:
        # msvcrt.locking refuses a zero-length range on some Windows runners. Keep one stable
        # byte in the runtime-only lock file and always lock from offset zero.
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
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
                handle.seek(0)
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


def _recover_locked(
    home: CareerVault,
    transaction: dict[str, Any],
    *,
    pipeline_writer: PipelineWriter | None,
    state_projector: StateProjector | None,
) -> dict[str, Any]:
    event = dict(transaction["event"])
    expected_fingerprint = transaction.get("event_fingerprint")
    if expected_fingerprint != _event_fingerprint(event):
        raise _recovery_error("approval transaction event fingerprint does not match")

    proposal_id = str(transaction["proposal_id"])
    proposal_rows = read_jsonl(home.proposals)
    proposal = next((row for row in proposal_rows if row.get("id") == proposal_id), None)
    if proposal is None:
        raise _recovery_error("approval transaction proposal is missing", proposal_id=proposal_id)
    existing_events = read_jsonl(home.events)
    matching_events = [row for row in existing_events if row.get("id") == event.get("id")]
    if matching_events and any(_event_fingerprint(row) != expected_fingerprint for row in matching_events):
        raise _recovery_error("event id already exists with different content", event_id=event.get("id"))
    if not matching_events:
        try:
            validate_event(event, for_confirmation=True)
            preflight_confirmation(home, event, existing_events)
            append_jsonl(home.events, event)
        except Exception as exc:
            if isinstance(exc, CareerError):
                raise _recovery_error(str(exc), proposal_id=proposal_id) from exc
            raise _recovery_error("could not recover the canonical event ledger", error=str(exc)) from exc
    _advance_transaction(home, transaction, "ledger_written")

    state = home.load_state()
    if state.get("last_event_id") == event.get("id") and state_version_is_persisted(home, state):
        version = str(state["version"])
    else:
        projected_state = state_projector(state, event) if state_projector else state
        version = home.save_state(projected_state)
    _advance_transaction(home, transaction, "state_written", state_version=version)

    if event.get("company"):
        workspace = transaction.get("workspace")
        if workspace and not Path(str(workspace)).is_dir():
            raise _recovery_error("approval workspace is no longer available", workspace=str(workspace))
        if pipeline_writer is None:
            raise _recovery_error("approval transaction requires a workspace projection writer")
        try:
            pipeline = pipeline_writer(event)
        except Exception as exc:
            raise _recovery_error("could not recover the workspace projection", error=str(exc)) from exc
    else:
        pipeline = None
    _advance_transaction(home, transaction, "projection_written", pipeline=str(pipeline) if pipeline else None)

    resolved_at = utc_now()
    updated = proposal
    if proposal.get("status") == ProposalStatus.PENDING:
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
    elif proposal.get("status") == ProposalStatus.APPROVED:
        if proposal.get("approved_event_id") not in {None, event.get("id")}:
            raise _recovery_error("proposal was approved for a different event", proposal_id=proposal_id)
    else:
        raise _recovery_error("approval transaction proposal has an invalid status", proposal_id=proposal_id)

    _advance_transaction(home, transaction, "committed", state_version=version)
    _clear_transaction(home)
    result: dict[str, Any] = {
        "approved": True,
        "event": event,
        "version": version,
        "proposal": updated,
        "recovered": True,
    }
    if pipeline:
        result["pipeline"] = str(pipeline)
    return result


def recover_pending(
    home: CareerVault,
    *,
    pipeline_writer: PipelineWriter | None = None,
    state_projector: StateProjector | None = None,
) -> dict[str, Any] | None:
    """Replay one incomplete approval transaction while holding the Vault lock."""
    if not approval_transaction_path(home).exists():
        return None
    with vault_lock(home):
        try:
            transaction = read_approval_transaction(home)
        except CareerError as exc:
            if exc.code == "APPROVAL_RECOVERY_FAILED":
                raise
            raise _recovery_error(str(exc)) from exc
        if transaction is None:
            return None
        try:
            return _recover_locked(
                home,
                transaction,
                pipeline_writer=pipeline_writer,
                state_projector=state_projector,
            )
        except CareerError:
            raise
        except Exception as exc:
            raise _recovery_error("approval transaction replay failed", error=str(exc)) from exc


def _merge_work_event(stored: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Merge a review patch into the stored payload, one level deeper for `confidentiality`.

    Everything else replaces wholesale: a corrected `direct_actions` list means that list, not the
    old one with additions. `confidentiality` is the exception because its two keys answer
    different questions and are naturally answered at different times — the material is flagged
    when the note is captured, and whether it may leave is decided after review. A shallow merge
    would let `{"external_use": "blocked"}` drop `contains_confidential: true` and quietly turn a
    flagged record into an unflagged one, which is the wrong direction to fail in.
    """
    merged = {**stored, **patch}
    old = stored.get("confidentiality")
    new = patch.get("confidentiality")
    if isinstance(old, dict) and isinstance(new, dict):
        merged["confidentiality"] = {**old, **new}
    return merged


def review_work_event(
    home: CareerVault, proposal_id: str, payload: dict[str, Any], *, replace: bool = False,
) -> dict[str, Any]:
    """Fill the structured fields of a pending work event, before it is confirmed.

    Capture is one sentence on purpose, so the structure has to arrive afterwards — and the
    approval path only ever accepted evidence, deadline, company, compensation, currency, and
    next_action. Without this the payload stayed `{}` from capture through confirmation, and the
    downstream requirement mapping, which reads `individual_contribution` and the rest, had
    nothing to read.

    Pending only. Once an event is confirmed it is history, and history is corrected by recording
    a superseding event rather than by editing the record. Keys merge by default so a review can
    happen over several turns; `replace` is there for the case where a whole field was wrong,
    including clearing one back to Unknown.
    """
    with vault_lock(home):
        proposal = next((row for row in read_jsonl(home.proposals) if row.get("id") == proposal_id), None)
        if not proposal:
            raise CareerError(f"proposal not found: {proposal_id}", code="PROPOSAL_NOT_FOUND")
        if proposal.get("status") != ProposalStatus.PENDING:
            raise CareerError(
                f"proposal is not pending: {proposal_id}; a confirmed event is corrected by "
                "recording a superseding one",
                code="PROPOSAL_NOT_PENDING",
            )
        event = dict(proposal.get("event") or {})
        if event.get("type") not in EVIDENCE_EVENT_TYPES:
            raise CareerError(
                f"proposal {proposal_id} is not an evidence event", code="INVALID_INPUT",
            )
        if not isinstance(payload, dict):
            raise CareerError("evidence payload must be an object", code="INVALID_INPUT")
        # Which key holds the payload follows the type, and the type was decided at capture. A
        # seminar and a release ask the same questions; only one of them says the user was employed.
        key = "work_event" if event["type"] == WORK_EVENT_TYPE else "experience"
        merged = payload if replace else _merge_work_event(event.get(key) or {}, payload)
        # Validate the merged result, not the patch: a payload that is fine alone can still be
        # rejected once combined, and what gets stored is what has to hold.
        validate_work_event(merged, field=f"event.{key}")
        event[key] = merged
        validate_event(event)
        updated = home.replace_proposal(proposal_id, event=event)
    result = {
        "mode": "review-work-event",
        "vault": str(home.path),
        "proposal": {"id": updated["id"], "status": updated["status"]},
        "evidence_type": event["type"],
        "evidence_payload": merged,
        "filled": sorted(key for key, value in merged.items() if value not in (None, [], {})),
        "ok": True,
    }
    if key == "work_event":
        # Compatibility with readers written before there were two evidence types. Present only
        # when the event really is a work event: echoing the payload under this name for a thesis
        # would tell a caller the user had a job at their university, which is the exact confusion
        # the separate type exists to prevent. A non-work review returns `evidence_payload` alone.
        result["work_event"] = merged
    return result


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
    recovered = recover_pending(
        home,
        pipeline_writer=pipeline_writer,
        state_projector=state_projector,
    )
    if recovered and recovered.get("proposal", {}).get("id") == proposal_id:
        return recovered
    with vault_lock(home):
        proposal = next((row for row in read_jsonl(home.proposals) if row.get("id") == proposal_id), None)
        if not proposal:
            raise CareerError(f"proposal not found: {proposal_id}")
        if proposal.get("status") != ProposalStatus.PENDING:
            raise CareerError(f"proposal is not pending: {proposal_id}")
        if proposal.get("kind") in {ProposalKind.EVENT, ProposalKind.CAREER_CONTEXT}:
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
            transaction_workspace = None
            if event.get("company") and pipeline_writer:
                transaction_workspace = str(Path(workspace).expanduser().resolve()) if workspace else str(Path.cwd().resolve())
            transaction: dict[str, Any] = {
                "version": 1,
                "transaction_id": f"approval-{uuid.uuid4().hex[:12]}",
                "proposal_id": proposal_id,
                "proposal_kind": proposal.get("kind"),
                "event": event,
                "event_fingerprint": _event_fingerprint(event),
                "workspace": transaction_workspace,
                "created_at": utc_now(),
                "stage": "prepared",
            }
            _write_transaction(home, transaction)
            if not any(row.get("id") == event.get("id") for row in existing_events):
                append_jsonl(home.events, event)
            _advance_transaction(home, transaction, "ledger_written")

            state = home.load_state()
            projected_state = state_projector(state, event) if state_projector else state
            if state.get("last_event_id") == event.get("id") and state_version_is_persisted(home, state):
                version = state["version"]
            elif projected_state == state and state_version_is_persisted(home, state):
                version = state["version"]
            else:
                version = home.save_state(projected_state)
            _advance_transaction(home, transaction, "state_written", state_version=version)

            pipeline = pipeline_writer(event) if pipeline_writer and event.get("company") else None
            _advance_transaction(
                home,
                transaction,
                "projection_written",
                pipeline=str(pipeline) if pipeline else None,
            )
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
            _advance_transaction(home, transaction, "committed", state_version=version)
            _clear_transaction(home)
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
