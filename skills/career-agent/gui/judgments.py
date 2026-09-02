"""GUI adapter for consequential human judgment.

The HTTP server delegates here so transport code never chooses an impact level or interprets a
judgment timeline.  Agent evidence references remain opaque in this slice: the adapter reports only
how many were recorded until the existing evidence boundary can resolve every reference safely.
"""

from __future__ import annotations

from typing import Any

import gui.cases as cases
from judgments import (
    judgment_timeline,
    list_judgments,
    record_agent_assessment,
    record_final_judgment,
    record_initial_judgment,
    record_outcome,
)
from review_policy import CareerError, judgment_policy


_PHASES = ("human_initial", "agent_assessment", "human_final", "outcome")


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise CareerError("expected a list of strings", code="INVALID_INPUT")
    return [item.strip() for item in value if item.strip()]


def _validate_target(home: Any, subject: str, target_ref: str) -> None:
    """Bind production judgment subjects to durable GUI cases when such a case must exist."""
    if subject not in {"application", "company_fit"}:
        return
    record = cases.get_case(home, target_ref)
    expected = "application" if subject == "application" else "company"
    if record.get("kind") != expected:
        raise CareerError(
            "judgment target does not match its subject",
            code="INVALID_RELATIONSHIP",
            details={"subject": subject, "expected_kind": expected},
        )


def _present_timeline(home: Any, judgment_id: str) -> dict[str, Any]:
    rows = judgment_timeline(home, judgment_id)
    if not rows:
        raise CareerError("judgment was not found", code="JUDGMENT_NOT_FOUND")
    by_phase = {row["phase"]: row for row in rows}
    initial = by_phase["human_initial"]
    agent = by_phase.get("agent_assessment")
    final = by_phase.get("human_final")
    outcome = by_phase.get("outcome")
    policy = judgment_policy(initial["subject"])
    next_phase = _PHASES[len(rows)] if len(rows) < len(_PHASES) else None
    return {
        "judgment_id": judgment_id,
        "subject": initial["subject"],
        "target_ref": initial["target_ref"],
        "impact": initial["impact"],
        "policy": policy,
        "next_phase": next_phase,
        "human_initial": {
            "decision": initial["decision"],
            "reasons": list(initial.get("reasons", [])),
            "created_at": initial["created_at"],
        },
        "agent_assessment": None if agent is None else {
            "recommendation": agent["recommendation"],
            "confidence": agent["confidence"],
            "reasons": list(agent.get("reasons", [])),
            "unknowns": list(agent.get("unknowns", [])),
            # Raw refs are deliberately not exposed to the browser until every ref has been
            # resolved through the existing evidence boundary.  Syntax alone is not evidence.
            "evidence_ref_count": len(agent.get("evidence_refs", [])),
            "created_at": agent["created_at"],
        },
        "human_final": None if final is None else {
            "decision": final["decision"],
            "reasons": list(final.get("reasons", [])),
            "created_at": final["created_at"],
        },
        "outcome": None if outcome is None else {
            "value": outcome["outcome"],
            "notes": outcome.get("notes"),
            "created_at": outcome["created_at"],
        },
    }


def payload(home: Any, *, target_ref: str | None = None) -> dict[str, Any]:
    """Return browser-safe judgment timelines, newest first, optionally for one durable target."""
    summaries = list_judgments(home)
    if target_ref is not None:
        summaries = [row for row in summaries if row.get("target_ref") == target_ref]
    rows = [_present_timeline(home, row["judgment_id"]) for row in summaries]
    rows.sort(key=lambda row: row["human_initial"]["created_at"], reverse=True)
    return {
        "mode": "judgments",
        "target_ref": target_ref,
        "judgments": rows,
        "canonical_write_performed": False,
    }


def start(home: Any, request: dict[str, Any]) -> dict[str, Any]:
    subject = str(request.get("subject") or "").strip()
    target_ref = str(request.get("target_ref") or "").strip()
    policy = judgment_policy(subject)
    if request.get("impact") is not None and request.get("impact") != policy["impact"]:
        raise CareerError(
            "caller cannot override the deterministic impact policy",
            code="INVALID_INPUT",
        )
    _validate_target(home, subject, target_ref)
    row = record_initial_judgment(
        home,
        subject=subject,
        target_ref=target_ref,
        impact=policy["impact"],
        decision=str(request.get("decision") or ""),
        reasons=_strings(request.get("reasons")),
    )
    return _present_timeline(home, row["judgment_id"])


def assess(home: Any, request: dict[str, Any]) -> dict[str, Any]:
    judgment_id = str(request.get("judgment_id") or "").strip()
    record_agent_assessment(
        home,
        judgment_id,
        recommendation=str(request.get("recommendation") or ""),
        confidence=str(request.get("confidence") or "unknown"),
        reasons=_strings(request.get("reasons")),
        evidence_refs=_strings(request.get("evidence_refs")),
        unknowns=_strings(request.get("unknowns")),
    )
    return _present_timeline(home, judgment_id)


def finalize(home: Any, request: dict[str, Any]) -> dict[str, Any]:
    judgment_id = str(request.get("judgment_id") or "").strip()
    record_final_judgment(
        home,
        judgment_id,
        decision=str(request.get("decision") or ""),
        reasons=_strings(request.get("reasons")),
    )
    return _present_timeline(home, judgment_id)


def record_result(home: Any, request: dict[str, Any]) -> dict[str, Any]:
    judgment_id = str(request.get("judgment_id") or "").strip()
    notes = request.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise CareerError("notes must be a string", code="INVALID_INPUT")
    record_outcome(
        home,
        judgment_id,
        outcome=str(request.get("outcome") or ""),
        notes=notes.strip() if isinstance(notes, str) and notes.strip() else None,
    )
    return _present_timeline(home, judgment_id)
