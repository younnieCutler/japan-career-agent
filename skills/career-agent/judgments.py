"""Human judgment ledger for consequential career decisions.

Judgment is deliberately separate from approval. Approval answers whether a reviewed
proposal may become canonical career state. Judgment records how the human and the agent
assessed a consequential decision so the product can preserve human reasoning, show
meaningful disagreement, and later calibrate outcomes without turning either assessment
into career truth.

The ledger is append-only and local to the Career Vault. It never mutates ``events.jsonl``,
``proposals.jsonl``, or canonical state, and it never treats an agent recommendation as an
authoritative fact.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from typing import Any

from lifecycle import vault_lock
from models import CareerError
from persistence import append_jsonl, read_jsonl_strict
from vault import CareerVault, utc_now


JUDGMENT_SCHEMA_VERSION = 1
JUDGMENT_PHASES = ("human_initial", "agent_assessment", "human_final", "outcome")
IMPACT_LEVELS = {"l0", "l1", "l2", "l3"}
JUDGMENT_SUBJECTS = {
    "company_fit",
    "application",
    "career_direction",
    "role_fit",
    "offer",
    "strategy",
    "other",
}
JUDGMENT_DECISIONS = {"proceed", "hold", "stop", "unknown"}
AGENT_CONFIDENCE = {"low", "medium", "high", "unknown"}
OUTCOME_STATES = {"positive", "mixed", "negative", "unknown"}
_JUDGMENT_ID = re.compile(r"^jdg-[a-f0-9]{12}$")
_SOURCE_BY_PHASE = {
    "human_initial": "human",
    "agent_assessment": "agent",
    "human_final": "human",
    "outcome": "human",
}


def judgment_ledger(home: CareerVault):
    """Return the local append-only judgment ledger path."""
    return home.state_dir / "judgments.jsonl"


def _text(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise CareerError(f"{field} must be a string", code="INVALID_INPUT")
    normalized = value.strip()
    if not normalized and not allow_empty:
        raise CareerError(f"{field} is required", code="INVALID_INPUT")
    return normalized


def _enum(value: Any, field: str, allowed: set[str]) -> str:
    normalized = _text(value, field)
    if normalized not in allowed:
        raise CareerError(
            f"{field} must be one of: {', '.join(sorted(allowed))}",
            code="INVALID_INPUT",
        )
    return normalized


def _reasons(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise CareerError("reasons must be a list", code="INVALID_INPUT")
    reasons: list[str] = []
    for item in value:
        reason = _text(item, "reason")
        if reason not in reasons:
            reasons.append(reason)
    return reasons


def _refs(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise CareerError(f"{field} must be a list", code="INVALID_INPUT")
    refs: list[str] = []
    for item in value:
        ref = _text(item, field)
        if ref not in refs:
            refs.append(ref)
    return refs


def _corrupted(message: str) -> CareerError:
    return CareerError(message, code="STATE_CORRUPTED", retryable=False)


def _stored_text(row: dict[str, Any], field: str, *, allow_empty: bool = False) -> str:
    value = row.get(field)
    if not isinstance(value, str):
        raise _corrupted(f"judgment {field} must be a string")
    if not allow_empty and not value.strip():
        raise _corrupted(f"judgment {field} is required")
    return value.strip()


def _stored_enum(row: dict[str, Any], field: str, allowed: set[str]) -> str:
    value = _stored_text(row, field)
    if value not in allowed:
        raise _corrupted(f"invalid judgment {field}: {value!r}")
    return value


def _stored_string_list(row: dict[str, Any], field: str) -> list[str]:
    value = row.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise _corrupted(f"judgment {field} must be a list of non-empty strings")
    if len(value) != len(dict.fromkeys(value)):
        raise _corrupted(f"judgment {field} contains duplicate values")
    return value


def _validate_stored_row(row: dict[str, Any]) -> None:
    version = row.get("schema_version")
    if isinstance(version, int) and version > JUDGMENT_SCHEMA_VERSION:
        raise CareerError(
            f"judgment schema {version} is newer than supported {JUDGMENT_SCHEMA_VERSION}",
            code="JUDGMENT_SCHEMA_NEWER",
            retryable=False,
        )
    if version != JUDGMENT_SCHEMA_VERSION:
        raise _corrupted(f"unsupported judgment schema version: {version!r}")

    judgment_id = _stored_text(row, "judgment_id")
    if not _JUDGMENT_ID.fullmatch(judgment_id):
        raise _corrupted(f"invalid judgment id: {judgment_id!r}")
    phase = _stored_enum(row, "phase", set(JUDGMENT_PHASES))
    source = _stored_text(row, "source")
    if source != _SOURCE_BY_PHASE[phase]:
        raise _corrupted(f"judgment phase {phase!r} has invalid source {source!r}")
    _stored_text(row, "created_at")

    if phase == "human_initial":
        _stored_enum(row, "subject", JUDGMENT_SUBJECTS)
        _stored_text(row, "target_ref")
        impact = _stored_enum(row, "impact", IMPACT_LEVELS)
        if impact != "l3":
            raise _corrupted("stored human judgment must be impact level l3")
        _stored_enum(row, "decision", JUDGMENT_DECISIONS)
        _stored_string_list(row, "reasons")
    elif phase == "agent_assessment":
        _stored_enum(row, "recommendation", JUDGMENT_DECISIONS)
        _stored_enum(row, "confidence", AGENT_CONFIDENCE)
        _stored_string_list(row, "reasons")
        _stored_string_list(row, "evidence_refs")
        _stored_string_list(row, "unknowns")
    elif phase == "human_final":
        _stored_enum(row, "decision", JUDGMENT_DECISIONS)
        _stored_string_list(row, "reasons")
    else:
        _stored_enum(row, "outcome", OUTCOME_STATES)
        notes = row.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise _corrupted("judgment outcome notes must be a string or null")
        _stored_string_list(row, "evidence_refs")


def _validated_rows(home: CareerVault) -> list[dict[str, Any]]:
    rows = read_jsonl_strict(judgment_ledger(home))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        _validate_stored_row(row)
        grouped[str(row["judgment_id"])].append(row)

    for judgment_id, timeline in grouped.items():
        phases = [str(row["phase"]) for row in timeline]
        expected = list(JUDGMENT_PHASES[: len(phases)])
        if phases != expected:
            raise _corrupted(
                f"judgment {judgment_id} has invalid phase sequence {phases!r}; expected {expected!r}"
            )
    return rows


def _rows_for(home: CareerVault, judgment_id: str) -> list[dict[str, Any]]:
    return [row for row in _validated_rows(home) if row["judgment_id"] == judgment_id]


def _require_phase_sequence(home: CareerVault, judgment_id: str, phase: str) -> None:
    rows = _rows_for(home, judgment_id)
    phases = [str(row["phase"]) for row in rows]
    if phase in phases:
        raise CareerError(
            f"judgment phase already recorded: {phase}",
            code="JUDGMENT_PHASE_EXISTS",
        )
    expected = JUDGMENT_PHASES[len(phases)] if len(phases) < len(JUDGMENT_PHASES) else None
    if phase != expected:
        raise CareerError(
            f"judgment phase {phase!r} cannot follow {phases[-1] if phases else 'nothing'!r}; "
            f"expected {expected!r}",
            code="JUDGMENT_PHASE_ORDER",
        )


def _append_phase(home: CareerVault, row: dict[str, Any]) -> dict[str, Any]:
    """Validate phase order and append while holding the Vault-wide lifecycle lock."""
    _validate_stored_row(row)
    with vault_lock(home):
        _require_phase_sequence(home, str(row["judgment_id"]), str(row["phase"]))
        append_jsonl(judgment_ledger(home), row)
    return row


def record_initial_judgment(
    home: CareerVault,
    *,
    subject: str,
    target_ref: str,
    impact: str,
    decision: str,
    reasons: list[str] | None = None,
) -> dict[str, Any]:
    """Record the user's pre-agent assessment for one L3 consequential decision."""
    impact = _enum(impact, "impact", IMPACT_LEVELS)
    if impact != "l3":
        raise CareerError("human judgment is only valid for l3 decisions", code="INVALID_INPUT")
    judgment_id = f"jdg-{uuid.uuid4().hex[:12]}"
    row = {
        "schema_version": JUDGMENT_SCHEMA_VERSION,
        "judgment_id": judgment_id,
        "phase": "human_initial",
        "subject": _enum(subject, "subject", JUDGMENT_SUBJECTS),
        "target_ref": _text(target_ref, "target_ref"),
        "impact": impact,
        "decision": _enum(decision, "decision", JUDGMENT_DECISIONS),
        "reasons": _reasons(reasons),
        "created_at": utc_now(),
        "source": "human",
    }
    return _append_phase(home, row)


def record_agent_assessment(
    home: CareerVault,
    judgment_id: str,
    *,
    recommendation: str,
    confidence: str,
    reasons: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    unknowns: list[str] | None = None,
) -> dict[str, Any]:
    """Record the agent assessment only after the human's initial judgment exists."""
    judgment_id = _text(judgment_id, "judgment_id")
    if not _JUDGMENT_ID.fullmatch(judgment_id):
        raise CareerError("invalid judgment_id", code="INVALID_INPUT")
    row = {
        "schema_version": JUDGMENT_SCHEMA_VERSION,
        "judgment_id": judgment_id,
        "phase": "agent_assessment",
        "recommendation": _enum(recommendation, "recommendation", JUDGMENT_DECISIONS),
        "confidence": _enum(confidence, "confidence", AGENT_CONFIDENCE),
        "reasons": _reasons(reasons),
        "evidence_refs": _refs(evidence_refs, "evidence_refs"),
        "unknowns": _refs(unknowns, "unknowns"),
        "created_at": utc_now(),
        "source": "agent",
    }
    return _append_phase(home, row)


def record_final_judgment(
    home: CareerVault,
    judgment_id: str,
    *,
    decision: str,
    reasons: list[str] | None = None,
) -> dict[str, Any]:
    """Record the user's final decision after the agent assessment is visible."""
    judgment_id = _text(judgment_id, "judgment_id")
    if not _JUDGMENT_ID.fullmatch(judgment_id):
        raise CareerError("invalid judgment_id", code="INVALID_INPUT")
    row = {
        "schema_version": JUDGMENT_SCHEMA_VERSION,
        "judgment_id": judgment_id,
        "phase": "human_final",
        "decision": _enum(decision, "decision", JUDGMENT_DECISIONS),
        "reasons": _reasons(reasons),
        "created_at": utc_now(),
        "source": "human",
    }
    return _append_phase(home, row)


def record_outcome(
    home: CareerVault,
    judgment_id: str,
    *,
    outcome: str,
    notes: str | None = None,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Attach a later outcome without rewriting the decision that preceded it."""
    judgment_id = _text(judgment_id, "judgment_id")
    if not _JUDGMENT_ID.fullmatch(judgment_id):
        raise CareerError("invalid judgment_id", code="INVALID_INPUT")
    row = {
        "schema_version": JUDGMENT_SCHEMA_VERSION,
        "judgment_id": judgment_id,
        "phase": "outcome",
        "outcome": _enum(outcome, "outcome", OUTCOME_STATES),
        "notes": _text(notes, "notes", allow_empty=True) if notes is not None else None,
        "evidence_refs": _refs(evidence_refs, "evidence_refs"),
        "created_at": utc_now(),
        "source": "human",
    }
    return _append_phase(home, row)


def judgment_timeline(home: CareerVault, judgment_id: str) -> list[dict[str, Any]]:
    """Return one validated judgment in append order."""
    judgment_id = _text(judgment_id, "judgment_id")
    if not _JUDGMENT_ID.fullmatch(judgment_id):
        raise CareerError("invalid judgment_id", code="INVALID_INPUT")
    return _rows_for(home, judgment_id)


def list_judgments(home: CareerVault) -> list[dict[str, Any]]:
    """Project the validated append-only ledger into one read model per judgment."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _validated_rows(home):
        grouped[str(row["judgment_id"])].append(row)

    projected: list[dict[str, Any]] = []
    for judgment_id, rows in grouped.items():
        phases = {str(row["phase"]): row for row in rows}
        initial = phases.get("human_initial", {})
        agent = phases.get("agent_assessment", {})
        final = phases.get("human_final", {})
        outcome = phases.get("outcome", {})
        initial_decision = initial.get("decision")
        agent_decision = agent.get("recommendation")
        projected.append(
            {
                "judgment_id": judgment_id,
                "subject": initial.get("subject"),
                "target_ref": initial.get("target_ref"),
                "impact": initial.get("impact"),
                "human_initial": initial_decision,
                "agent_recommendation": agent_decision,
                "agent_confidence": agent.get("confidence"),
                "human_final": final.get("decision"),
                "outcome": outcome.get("outcome"),
                "human_agent_diverged": (
                    initial_decision != agent_decision
                    if initial_decision is not None and agent_decision is not None
                    else None
                ),
                "complete": "human_final" in phases,
                "outcome_known": outcome.get("outcome") not in {None, "unknown"},
            }
        )
    return projected
