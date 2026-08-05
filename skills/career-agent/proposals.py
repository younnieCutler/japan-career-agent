"""Approval-gated proposal creation and metadata-only listing."""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path
from typing import Any

_SHARED_ROOT = Path(__file__).resolve().parent.parent.parent / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))
import self_analysis_profile  # noqa: E402

from lifecycle import count_consecutive_safe_stops, vault_lock  # noqa: E402
from models import CHUTO_STAGES, DOCUMENT_EVIDENCE_PREFIX, SHINSOTSU_STAGES, TRACKS, UNTRUSTED_DATA_MARKER, CareerError  # noqa: E402
from personal_timeline import select_personal_context  # noqa: E402
from persistence import read_jsonl, write_jsonl  # noqa: E402
from routing import flow_phase_for, infer_track, language_for, load_flow_reference, skill_context, stage_for  # noqa: E402
from validation import validate_career_context, validate_event  # noqa: E402
from vault import CareerVault, select_context, utc_now  # noqa: E402


def approval_action_for(message: str) -> str:
    return {
        "ko": "근거를 확인한 뒤 이벤트 확정",
        "ja": "根拠を確認してからイベントを確定する",
        "en": "Confirm evidence before saving",
    }[language_for(message)]


def make_event(message: str, track: str, stage: str, flow_phase: str, *, status: str = "draft") -> dict[str, Any]:
    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    language = language_for(message)
    title = {
        "ko": "사용자 입력 기반 경력 이벤트",
        "ja": "ユーザー入力に基づくキャリアイベント",
        "en": "User-reported career event",
    }[language]
    event = {
        "id": event_id,
        "track": track,
        "stage": stage,
        "flow_phase": flow_phase,
        "type": "user_report",
        "occurred_at": utc_now(),
        "title": title,
        "summary": message.strip(),
        "evidence": [],
        "source": "user_message",
        "next_action": None,
        "deadline": None,
        "status": status,
    }
    validate_event(event)
    return event


def run_chat(
    home: CareerVault, skills_root: Path, message: str, requested_track: str | None, as_of: str,
) -> dict[str, Any]:
    state = home.load_state()
    profile = home.load_profile()
    recent_events = read_jsonl(home.events)[-5:]
    track = infer_track(message, requested_track) or state.get("track") or profile.get("track")
    if not track:
        goal = "resolve track before routing"
        retry_count = count_consecutive_safe_stops(home, goal)
        trajectory = {
            "id": f"traj-{uuid.uuid4().hex[:12]}",
            "created_at": utc_now(),
            "mode": "chat",
            "observe": {"track": state.get("track"), "stage": state.get("stage"), "deadlines": state.get("deadlines", []), "recent_events": recent_events, "message": message, "data_trust": UNTRUSTED_DATA_MARKER, "instruction_authority": "none"},
            "plan": {"goal": goal},
            "act": {"proposal": None},
            "verify": {"track": "ambiguous", "external_side_effect": False},
            "correct": {"retry_count": retry_count, "needs_user_confirmation": True},
            "persist": {"trajectory_only": True},
        }
        home.append_trajectory(trajectory)
        question = "track must be explicit: shinsotsu or chuto"
        if retry_count >= 2:
            question += " (asked before — reply with your track, or set it directly in career-profile.toml)"
        return {"mode": "chat", "language": language_for(message), "needs_confirmation": True, "question": question, "saved": str(home.trajectories)}
    if track == "shinsotsu" and not isinstance(profile.get("graduation_year"), int):
        goal = "collect required shinsotsu graduation year before proposing an event"
        retry_count = count_consecutive_safe_stops(home, goal)
        home.append_trajectory(
            {
                "id": f"traj-{uuid.uuid4().hex[:12]}",
                "created_at": utc_now(),
                "mode": "chat",
                "observe": {"track": track, "profile_has_graduation_year": False, "message": message, "data_trust": UNTRUSTED_DATA_MARKER, "instruction_authority": "none"},
                "plan": {"goal": goal},
                "act": {"proposal": None},
                "verify": {"safe_stop": True, "external_side_effect": False},
                "correct": {"retry_count": retry_count, "needs_user_confirmation": True},
                "persist": {"trajectory_only": True},
            }
        )
        question = "profile.graduation_year is required for shinsotsu before an event proposal can be created"
        if retry_count >= 2:
            question += " (asked before — set profile.graduation_year directly in career-profile.toml)"
        return {"mode": "chat", "language": language_for(message), "track": track, "needs_confirmation": True, "question": question, "saved": str(home.trajectories)}
    stage = stage_for(message, track, state.get("stage"))
    reference = load_flow_reference()
    flow_phase = flow_phase_for(message, track, state, profile, reference)
    context = select_context(home.path, track, stage, as_of)
    # Section 12.1. The same selector the shared `context` command uses -- one implementation, so
    # the chat path and the shared API cannot disagree about what "current personal context" means.
    personal = select_personal_context(read_jsonl(home.events), stage, as_of)
    event = make_event(message, track, stage, flow_phase)
    approval_action = approval_action_for(message)
    proposal = {
        "id": f"proposal-{uuid.uuid4().hex[:12]}",
        "kind": "event",
        "status": "pending",
        "created_at": utc_now(),
        "next_action": approval_action,
        "event": event,
    }
    trajectory = {
        "id": f"traj-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "mode": "chat",
        "observe": {"track": state.get("track"), "stage": state.get("stage"), "deadlines": state.get("deadlines", []), "recent_events": recent_events, "message": message, "data_trust": UNTRUSTED_DATA_MARKER, "instruction_authority": "none"},
        "plan": {"track": track, "stage": stage, "flow_phase": flow_phase, "goal": "route and propose a grounded event", "next_action": approval_action},
        "act": {"proposal_id": proposal["id"], "skill": skill_context(skills_root, stage), "context_count": len(context), "personal_fact_count": len(personal["facts"])},
        "verify": {"event_schema": "valid", "context_is_metadata_only": True, "external_side_effect": False},
        "correct": {"retry_count": 0, "needs_user_confirmation": True},
        "persist": {"proposal_id": proposal["id"]},
    }
    with vault_lock(home):
        home.add_proposal(proposal)
        home.append_trajectory(trajectory)
    return {"mode": "chat", "language": language_for(message), "track": track, "stage": stage, "flow_phase": flow_phase, "skill": skill_context(skills_root, stage), "context": context, "personal_context": personal, "context_trust": {"data": UNTRUSTED_DATA_MARKER, "instruction_authority": "none"}, "proposal": proposal, "saved": str(home.proposals)}


def propose_career_context(home: CareerVault, source: str) -> dict[str, Any]:
    """Create an approval-gated proposal from a CWD-relative SELF_ANALYSIS_PROFILE."""
    source_path = Path(source).expanduser().resolve()
    if not source_path.exists():
        raise CareerError(f"career context source not found: {source_path}")
    try:
        import yaml
        raw = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
    except ImportError as exc:
        raise CareerError("PyYAML is required to propose career context") from exc
    except (OSError, yaml.YAMLError) as exc:
        raise CareerError(f"invalid career context YAML: {source_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise CareerError("career context source root must be an object")
    raw_only = sorted(self_analysis_profile.RAW_ONLY_FIELDS.intersection(raw))
    if raw_only:
        raise CareerError("raw checklist submission cannot become canonical career context: " + ", ".join(raw_only))
    if "self_analysis_version" in raw:
        try:
            self_analysis_profile.validate_self_analysis_profile(raw)
        except self_analysis_profile.ProfileValidationError as exc:
            raise CareerError(str(exc)) from exc
    payload = validate_career_context(raw)
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    with vault_lock(home):
        proposals = read_jsonl(home.proposals)
        for row in proposals:
            if row.get("kind") != "career_context" or row.get("profile_digest") != digest:
                continue
            if row.get("status") in {"pending", "approved"}:
                return {"mode": "propose-context", "deduplicated": True, "proposal": row, "source": str(source_path)}
        for row in proposals:
            if row.get("kind") == "career_context" and row.get("status") == "pending":
                row["status"] = "superseded"
                row["updated_at"] = utc_now()
        track = home.load_state().get("track") or home.load_profile().get("track")
        if track not in TRACKS:
            raise CareerError("career context proposal requires profile.track or state.track")
        state = home.load_state()
        stage = state.get("stage") or (SHINSOTSU_STAGES[0] if track == "shinsotsu" else CHUTO_STAGES[0])
        flow_phase = state.get("flow_phase") or "self_analysis"
        event = {
            "id": f"evt-{uuid.uuid4().hex[:12]}",
            "track": track,
            "stage": stage,
            "flow_phase": flow_phase,
            "type": "career_context",
            "occurred_at": utc_now(),
            "title": "User-confirmed career context",
            "summary": "User-confirmed canonical career values",
            "evidence": [f"SELF_ANALYSIS_PROFILE sha256:{digest}"],
            "source": "jiko-bunseki",
            "next_action": "",
            "deadline": None,
            "status": "draft",
            "career_context": payload,
            "profile_digest": digest,
        }
        validate_event(event)
        proposal = {"id": f"proposal-{uuid.uuid4().hex[:12]}", "kind": "career_context", "status": "pending", "created_at": utc_now(), "profile_digest": digest, "event": event}
        write_jsonl(home.proposals, [*proposals, proposal])
    return {"mode": "propose-context", "deduplicated": False, "proposal": proposal, "source": str(source_path)}


def document_evidence(document_id: str) -> str:
    """The one spelling of "this fact came from that document".

    The reference is the `document_id` alone. The registry already maps it to a digest and a
    storage path, and copying either here would be a second source of truth that goes stale the
    moment the registry changes -- the same rule that keeps `effective_to` derived.
    """
    return f"{DOCUMENT_EVIDENCE_PREFIX}{document_id}"


def propose_fact(
    home: CareerVault,
    records: list[dict[str, Any]],
    *,
    document_id: str,
    category: str,
    key: str,
    value: Any,
    effective_from: str | None = None,
    expires_on: str | None = None,
    supersedes: str | None = None,
) -> dict[str, Any]:
    """Propose one personal fact backed by an imported document (PRD phase 5).

    **The tool does not read the document.** Text extraction is a v1 non-goal (section 4), so the
    value is the user's statement and the document is what they are pointing at. Claiming otherwise
    would be a machine-read claim nothing here can support.

    The proposal is a `draft`, and `approve` is the only thing that confirms it (section 5.3). A
    draft fact is inert: it never enters the projection and cannot retire a confirmed fact, so an
    unreviewed proposal cannot change what any skill sees.

    The document must already be in the registry. A fact whose evidence points at nothing is worse
    than no fact -- it looks provenance-backed and is not.
    """
    known = {str(record.get("document_id")) for record in records}
    if document_id not in known:
        raise CareerError(
            f"no imported document with id {document_id!r}; import it first and use the id "
            f"`private-list` reports"
        )
    fact = {"category": category, "key": key, "value": value}
    if effective_from is not None:
        fact["effective_from"] = effective_from
    if expires_on is not None:
        fact["expires_on"] = expires_on
    if supersedes is not None:
        fact["supersedes"] = supersedes
    with vault_lock(home):
        state = home.load_state()
        track = state.get("track") or home.load_profile().get("track")
        if track not in TRACKS:
            raise CareerError("fact proposal requires profile.track or state.track")
        stage = state.get("stage") or (SHINSOTSU_STAGES[0] if track == "shinsotsu" else CHUTO_STAGES[0])
        event = {
            "id": f"evt-{uuid.uuid4().hex[:12]}",
            "track": track,
            "stage": stage,
            "flow_phase": state.get("flow_phase") or "self_analysis",
            "type": "fact",
            "occurred_at": utc_now(),
            # The value stays out of the prose deliberately. A number in `title`/`summary` must
            # appear in the evidence text to be confirmable, and satisfying that by echoing the
            # value into the evidence string would make the check circular -- the record would
            # support itself. The value lives in the structured payload, where `validate_fact`
            # governs it and supersession can correct it.
            "title": f"personal fact: {category}/{key}",
            "summary": "user-stated personal fact backed by an imported private document",
            "evidence": [document_evidence(document_id)],
            "source": "private-store",
            "next_action": None,
            "deadline": None,
            "status": "draft",
            "fact": fact,
        }
        validate_event(event)
        proposal_id = f"proposal-{uuid.uuid4().hex[:12]}"
        proposal = {
            "id": proposal_id,
            "kind": "event",
            "status": "pending",
            "created_at": utc_now(),
            "next_action": f"review the value against the document, then run: approve {proposal_id}",
            "event": event,
        }
        write_jsonl(home.proposals, [*read_jsonl(home.proposals), proposal])
    return {
        "mode": "propose-fact",
        "proposal": proposal,
        "document_id": document_id,
        "machine_read": False,
        "needs_confirmation": True,
    }


def proposal_summary(proposal: dict[str, Any]) -> dict[str, Any]:
    """Expose proposal metadata without leaking event/report bodies."""
    event = proposal.get("event") if isinstance(proposal.get("event"), dict) else {}
    report = proposal.get("report") if isinstance(proposal.get("report"), dict) else {}
    return {"id": proposal.get("id"), "kind": proposal.get("kind"), "status": proposal.get("status"), "created_at": proposal.get("created_at"), "title": event.get("title") or report.get("title") or proposal.get("title"), "stage": event.get("stage") or report.get("stage") or proposal.get("stage"), "company": event.get("company") or proposal.get("company")}


def list_proposals(home: CareerVault, *, include_all: bool = False, limit: int | None = None) -> dict[str, Any]:
    rows = read_jsonl(home.proposals)
    if not include_all:
        rows = [row for row in rows if row.get("status") == "pending"]
    rows = [row for _, row in sorted(enumerate(rows), key=lambda item: (str(item[1].get("created_at") or ""), item[0]), reverse=True)]
    if limit is not None:
        rows = rows[:limit]
    return {"mode": "proposals", "count": len(rows), "proposals": [proposal_summary(row) for row in rows]}
