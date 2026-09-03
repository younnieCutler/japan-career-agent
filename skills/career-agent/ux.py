"""Thin, deterministic UX projection for Career Agent command results.

This module only translates already-computed command results and expected ``CareerError``
metadata into a common state/reason/transition shape.  It never validates evidence, derives
matching states, reads files, or mutates canonical state.
"""

from __future__ import annotations

from typing import Any, Mapping

from models import CareerError
from localization import (
    UX_TEXT,
    action_label,
    domain_label,
    effect_label,
    normalize_language,
    state_label,
    text,
)

__all__ = ["UX_TEXT", "attach", "error_payload", "render_human", "text"]


UX_STATES = {
    "ready",
    "needs_input",
    "needs_confirmation",
    "blocked",
    "completed",
    "recovery_required",
    "review",
}


def _action(
    action_id: str,
    label: str,
    *,
    command: str | None = None,
    operation_kind: str = "inspect",
    requires_confirmation: bool = False,
) -> dict[str, Any]:
    return {
        "id": action_id,
        "label": label,
        "command": command,
        "operation_kind": operation_kind,
        "requires_confirmation": requires_confirmation,
    }


def _disclosure(disclosure_id: str, topic: str, message: str) -> dict[str, str]:
    """Return a short, stable explanation shown only at the relevant UX boundary."""
    return {"id": disclosure_id, "topic": topic, "message": message}


def _outcome(
    state: str,
    summary: str,
    *,
    reason_code: str,
    reason_message: str,
    actions: list[dict[str, Any]] | None = None,
    issues: list[dict[str, Any]] | None = None,
    changed: list[str] | None = None,
    unchanged: list[str] | None = None,
    disclosures: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    if state not in UX_STATES:
        raise ValueError(f"unsupported UX state: {state}")
    return {
        "state": state,
        "summary": summary,
        "reason": {"code": reason_code, "message": reason_message},
        "issues": list(issues or []),
        "next": {
            "type": "allowed_transitions",
            "actions": list(actions or []),
        },
        "effects": {
            "changed": list(changed or []),
            "unchanged": list(unchanged or []),
        },
        "disclosures": list(disclosures or []),
    }


def _proposal_id(result: Mapping[str, Any]) -> str | None:
    proposal = result.get("proposal")
    if isinstance(proposal, Mapping):
        value = proposal.get("id")
        return str(value) if value else None
    return None


def _proposal_actions(
    proposal_id: str | None,
    language: str,
    proposal_kind: str | None = None,
) -> list[dict[str, Any]]:
    review_command = "proposals"
    approve_command = "approve <proposal_id>"
    if proposal_id:
        review_command = f"proposals --id {proposal_id}"
        approve_command = f"approve {proposal_id}"
    return [
        _action("review_proposal", action_label(language, "review_proposal"), command=review_command),
        _action(
            "approve_proposal",
            action_label(language, "approve_proposal", proposal_kind=proposal_kind),
            command=approve_command,
            operation_kind="approve",
            requires_confirmation=True,
        ),
        _action("keep_pending", action_label(language, "keep_pending"), operation_kind="keep_state"),
    ]


def _walk_states(value: Any, path: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """Collect explicit Unknown/Conflict fields without changing their domain meaning."""
    found: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        state = str(value.get("state") or "").casefold()
        if state in {"unknown", "conflict"}:
            code = "FACT_UNKNOWN" if state == "unknown" else "FACT_CONFLICT"
            subject = ".".join(path) or "current evidence"
            reason = str(value.get("reason") or "evidence is insufficient")
            found.append({"code": code, "subject": subject, "message": reason})
        for key, child in value.items():
            if key in {"evidence", "candidates", "context"}:
                # Evidence identifiers may be shown by domain commands, but are not UX state
                # nodes. Avoid duplicating private content into a generic summary.
                continue
            found.extend(_walk_states(child, (*path, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_states(child, (*path, str(index))))
    return found


def _state_issues(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues = _walk_states(result)
    # Stable, deterministic de-duplication keeps repeated projections readable.
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        marker = (str(issue.get("code")), str(issue.get("subject")))
        if marker not in seen:
            seen.add(marker)
            unique.append(issue)
    return unique


def _with_state_actions(
    outcome: dict[str, Any], issues: list[dict[str, Any]], *, command: str,
    language: str,
) -> dict[str, Any]:
    if not issues:
        return outcome
    outcome["issues"] = issues
    ids = {str(item.get("code")) for item in issues}
    if "FACT_UNKNOWN" in ids:
        outcome["next"]["actions"].extend(
            [
                _action("inspect_context", action_label(language, "inspect_context"), command="context"),
                _action("keep_unknown", action_label(language, "keep_unknown"), operation_kind="keep_state"),
            ]
        )
        outcome["disclosures"].append(
            _disclosure(
                "unknown-state",
                "unknown",
                text(language, "disclosure.unknown"),
            )
        )
    if "FACT_CONFLICT" in ids:
        outcome["next"]["actions"].extend(
            [
                _action("inspect_conflict", action_label(language, "inspect_conflict"), command="personal-profile"),
                _action("keep_conflict", action_label(language, "keep_conflict"), operation_kind="keep_state"),
            ]
        )
        outcome["disclosures"].append(
            _disclosure(
                "conflict-state",
                "conflict",
                text(language, "disclosure.conflict"),
            )
        )
    if outcome["state"] == "ready":
        outcome["state"] = "review"
        outcome["reason"] = {
            "code": "REVIEW_REQUIRED",
            "message": text(language, "reason.review_required"),
        }
    return outcome


def attach(
    command: str,
    result: Mapping[str, Any],
    *,
    args: Mapping[str, Any] | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Add the additive ``ux`` block to one successful command result."""
    args = args or {}
    language = normalize_language(
        language
        or result.get("language")
        or (result.get("profile", {}).get("language") if isinstance(result.get("profile"), Mapping) else None)
    )
    proposal_id = _proposal_id(result)
    proposal = result.get("proposal")
    proposal_pending = isinstance(proposal, Mapping) and proposal.get("status") == "pending"
    pending = result.get("pending_proposals")
    if not isinstance(pending, int):
        pending = int(result.get("count") or 0) if command == "proposals" else (1 if proposal_pending else 0)
    proposal_kind = str(proposal.get("kind") or "") if isinstance(proposal, Mapping) else None
    if command == "run" and str(args.get("mode") or result.get("mode")) == "heartbeat":
        proposal_kind = "heartbeat"
    if command == "proposals" and not proposal:
        listed = result.get("proposals") if isinstance(result.get("proposals"), list) else []
        if len(listed) == 1 and isinstance(listed[0], Mapping):
            proposal_kind = str(listed[0].get("kind") or "") or None
    if proposal_kind is None:
        pending_kind = result.get("pending_kind")
        if pending_kind:
            proposal_kind = str(pending_kind)

    def finish(outcome: dict[str, Any]) -> dict[str, Any]:
        outcome["language"] = language
        for item in outcome.get("next", {}).get("actions", []):
            if isinstance(item, dict) and item.get("id"):
                if command != "guided":
                    item["label"] = action_label(language, str(item["id"]), proposal_kind=proposal_kind)
        return {**dict(result), "ux": outcome}

    if command == "setup":
        needs_input = result.get("needs_input") or []
        diagnosis = result.get("doctor") if isinstance(result.get("doctor"), Mapping) else {}
        if needs_input:
            outcome = _outcome(
                "needs_input",
                text(language, "summary.setup_needs_input"),
                reason_code="SETUP_REQUIRED",
                reason_message=text(language, "reason.setup_required"),
                actions=[_action("run_setup", action_label(language, "run_setup"), command="setup", operation_kind="repair", requires_confirmation=True)],
                issues=[{"code": "SETUP_REQUIRED", "subject": str(field), "message": "This setup field is required."} for field in needs_input],
                disclosures=[
                    _disclosure(
                        "vault-purpose",
                        "vault",
                        text(language, "disclosure.vault"),
                    )
                ],
            )
        elif diagnosis.get("ok") is False:
            outcome = _outcome(
                "blocked",
                text(language, "summary.setup_blocked"),
                reason_code="SETUP_REQUIRED",
                reason_message=text(language, "reason.setup_blocked"),
                actions=[_action("run_doctor", action_label(language, "run_doctor"), command="doctor", operation_kind="repair", requires_confirmation=False)],
                unchanged=["canonical career facts"],
                disclosures=[
                    _disclosure(
                        "vault-purpose",
                        "vault",
                        text(language, "disclosure.vault"),
                    )
                ],
            )
        else:
            outcome = _outcome(
                "ready",
                text(language, "summary.setup_ready"),
                reason_code="SETUP_COMPLETE",
                reason_message=text(language, "reason.setup_complete"),
                actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")],
                changed=["vault/profile setup" if result.get("created") else "profile setup"],
                disclosures=[
                    _disclosure(
                        "vault-purpose",
                        "vault",
                        text(language, "disclosure.vault"),
                    )
                ],
            )
        return finish(outcome)

    if command == "guided":
        guided = result.get("guided") if isinstance(result.get("guided"), Mapping) else {}
        summary = guided.get("summary") if isinstance(guided.get("summary"), Mapping) else {}
        available = guided.get("available_actions") if isinstance(guided.get("available_actions"), list) else []
        selection = result.get("selection") if isinstance(result.get("selection"), Mapping) else {}
        selection_status = str(selection.get("status") or "menu")
        if not result.get("ok", True) or selection_status in {"invalid", "blocked"}:
            state = "blocked"
            reason_code = str(result.get("error_code") or "OPERATION_BLOCKED")
            reason_message = text(language, "error.guided_choice")
        elif selection_status == "confirmation_required":
            state = "needs_confirmation"
            confirmation_reason = {
                "complete_setup": (
                    "SETUP_REQUIRED",
                    text(language, "reason.guided_confirmation"),
                ),
                "start_task": (
                    "GUIDED_CONFIRMATION_REQUIRED",
                    text(language, "reason.guided_confirmation"),
                ),
                "approve_proposal": (
                    "PENDING_PROPOSAL",
                    text(language, "reason.pending_proposal"),
                ),
                "restore_state": (
                    "STATE_RECOVERY_REQUIRED",
                    text(language, "reason.guided_confirmation"),
                ),
            }
            reason_code, reason_message = confirmation_reason.get(
                str(selection.get("action")),
                ("GUIDED_CONFIRMATION_REQUIRED", text(language, "reason.guided_confirmation")),
            )
        else:
            state = str(guided.get("state") or "ready")
            if state == "needs_input":
                reason_code = "SETUP_REQUIRED"
                reason_message = text(language, "reason.setup_required")
            elif state == "needs_confirmation":
                reason_code = "PENDING_PROPOSAL"
                reason_message = text(language, "reason.pending_proposal")
            elif state == "review":
                reason_code = "REVIEW_REQUIRED"
                reason_message = text(language, "reason.review_required")
            elif state == "blocked":
                reason_code = str((summary.get("workspace_error") or {}).get("code") or "OPERATION_BLOCKED") if isinstance(summary.get("workspace_error"), Mapping) else "OPERATION_BLOCKED"
                reason_message = str(
                    text(language, "reason.operation_blocked")
                    if isinstance(summary.get("workspace_error"), Mapping)
                    else text(language, "reason.operation_blocked")
                )
            else:
                reason_code = "GUIDED_READY"
                reason_message = text(language, "reason.guided_ready")
        disclosures: list[dict[str, str]] = []
        if not summary.get("setup_complete"):
            disclosures.append(_disclosure("vault-purpose", "vault", text(language, "disclosure.vault")))
        if summary.get("pending_proposals"):
            disclosures.append(_disclosure("proposal-approval-boundary", "proposal", text(language, "disclosure.approval")))
        if summary.get("unknown_count"):
            disclosures.append(_disclosure("unknown-state", "unknown", text(language, "disclosure.unknown")))
        if summary.get("conflict_count"):
            disclosures.append(_disclosure("conflict-state", "conflict", text(language, "disclosure.conflict")))
        if isinstance(summary.get("workspace"), Mapping):
            path = summary["workspace"].get("path") or text(language, "guided.workspace_unresolved")
            disclosures.append(_disclosure("workspace-purpose", "workspace", f"{text(language, 'section.workspace')}: {path}"))
        action_result = result.get("action_result") if isinstance(result.get("action_result"), Mapping) else {}
        queue_only = action_result.get("applied") is False
        if queue_only:
            reason_code = "APPROVAL_COMPLETE"
            reason_message = text(language, "reason.approval_queue_only")
            disclosures.append(_disclosure("heartbeat-approval", "heartbeat", text(language, "disclosure.heartbeat")))
            summary_text = text(language, "summary.approval_queue_only")
        elif str(selection.get("action") or "") == "approve_proposal" and action_result:
            reason_code = "APPROVAL_COMPLETE"
            reason_message = text(language, "reason.approval_event")
            summary_text = text(language, "summary.approval_event")
        else:
            summary_text = text(language, "summary.guided_ready")
        effects_changed = ["guided-selected operation"] if result.get("write_performed") or result.get("state_changed") else []
        effects_unchanged = [] if result.get("state_changed") else ["canonical state"]
        outcome = _outcome(
            state,
            summary_text,
            reason_code=reason_code,
            reason_message=reason_message,
            actions=available,
            changed=effects_changed,
            unchanged=effects_unchanged,
            disclosures=disclosures,
        )
        return finish(outcome)

    if command == "doctor":
        errors = result.get("errors") if isinstance(result.get("errors"), list) else []
        warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
        if errors:
            outcome = _outcome(
                "blocked",
                text(language, "summary.doctor_blocked"),
                reason_code="SETUP_REQUIRED",
                reason_message=text(language, "reason.doctor_error"),
                actions=[_action("run_doctor", action_label(language, "run_doctor"), command="doctor --fix", operation_kind="repair", requires_confirmation=True)],
                issues=[{"code": "DOCTOR_ERROR", "subject": "doctor", "message": str(item)} for item in errors],
                unchanged=["canonical career state"],
            )
        elif warnings:
            outcome = _outcome(
                "review",
                text(language, "summary.doctor_warning"),
                reason_code="REVIEW_REQUIRED",
                reason_message=text(language, "reason.doctor_warning"),
                actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")],
                issues=[{"code": "DOCTOR_WARNING", "subject": "doctor", "message": str(item)} for item in warnings],
            )
        else:
            outcome = _outcome("ready", text(language, "summary.doctor_ok"), reason_code="DOCTOR_OK", reason_message=text(language, "reason.doctor_ok"), actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")])
        return finish(outcome)

    if command == "status":
        if not result.get("profile", {}).get("track"):
            outcome = _outcome(
                "needs_input",
                text(language, "summary.status_needs_track"),
                reason_code="SETUP_REQUIRED",
                reason_message=text(language, "reason.setup_required"),
                actions=[_action("run_setup", action_label(language, "run_setup"), command="setup", operation_kind="repair", requires_confirmation=True)],
                disclosures=[
                    _disclosure(
                        "vault-purpose",
                        "vault",
                        text(language, "disclosure.vault"),
                    )
                ],
            )
        elif pending:
            heartbeat_pending = proposal_kind == "heartbeat"
            disclosure_key = (
                "disclosure.heartbeat"
                if heartbeat_pending
                else "disclosure.event_approval"
                if proposal_kind == "event"
                else "disclosure.approval"
            )
            outcome = _outcome(
                "needs_confirmation",
                text(language, "summary.heartbeat_pending" if heartbeat_pending else "summary.status_pending_count", count=pending),
                reason_code="PENDING_PROPOSAL",
                reason_message=text(language, "reason.heartbeat_pending" if heartbeat_pending else "reason.pending_proposal"),
                actions=_proposal_actions(None, language, proposal_kind),
                unchanged=["canonical state until approval"],
                disclosures=[
                    _disclosure(
                        "proposal-approval-boundary",
                        "proposal",
                        text(language, disclosure_key),
                    ),
                    _disclosure(
                        "workspace-purpose",
                        "workspace",
                        f"{text(language, 'section.workspace')}: {result.get('workspace', {}).get('path') if isinstance(result.get('workspace'), Mapping) else text(language, 'guided.workspace_unresolved')}",
                    ),
                ],
            )
        else:
            outcome = _outcome(
                "ready",
                text(language, "summary.status_ready"),
                reason_code="STATUS_READY",
                reason_message=text(language, "reason.status_ready"),
                actions=[_action("inspect_profile", action_label(language, "inspect_profile"), command="personal-profile"), _action("inspect_context", action_label(language, "inspect_context"), command="context")],
                disclosures=[
                    _disclosure(
                        "workspace-purpose",
                        "workspace",
                        f"{text(language, 'section.workspace')}: {result.get('workspace', {}).get('path') if isinstance(result.get('workspace'), Mapping) else text(language, 'guided.workspace_unresolved')}",
                    )
                ],
            )
        return finish(outcome)

    if command in {"run", "propose-fact", "propose-context"}:
        operation_created_pending = command == "run" and str(args.get("mode") or result.get("mode")) in {"heartbeat", "discover"}
        if proposal_pending or pending or operation_created_pending:
            outcome = _outcome(
                "needs_confirmation",
                text(language, "summary.heartbeat_pending" if proposal_kind == "heartbeat" else "summary.operation_pending"),
                reason_code="PENDING_PROPOSAL",
                reason_message=text(language, "reason.heartbeat_pending" if proposal_kind == "heartbeat" else "reason.operation_pending"),
                actions=_proposal_actions(proposal_id, language, proposal_kind),
                unchanged=["personal profile and canonical state"],
                disclosures=[
                    _disclosure(
                        "proposal-approval-boundary",
                        "proposal",
                        text(language, "disclosure.heartbeat" if proposal_kind == "heartbeat" else "disclosure.event_approval" if proposal_kind == "event" else "disclosure.approval"),
                    )
                ],
            )
        elif result.get("needs_confirmation"):
            outcome = _outcome(
                "needs_input",
                str(result.get("question") or text(language, "reason.setup_required")),
                reason_code="SETUP_REQUIRED",
                reason_message=text(language, "reason.setup_required"),
                actions=[_action("run_setup", action_label(language, "complete_required_setup"), command="setup", operation_kind="repair", requires_confirmation=True)],
            )
        else:
            outcome = _outcome("completed", text(language, "summary.operation_complete"), reason_code="OPERATION_COMPLETE", reason_message=text(language, "reason.operation_complete"), actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")])
        return finish(_with_state_actions(outcome, _state_issues(result), command=command, language=language))

    if command == "proposals":
        if result.get("proposal"):
            status = str(result["proposal"].get("status") or "")
            if status == "pending":
                kind = str(result["proposal"].get("kind") or "")
                outcome = _outcome("needs_confirmation", text(language, "summary.proposal_review"), reason_code="PENDING_PROPOSAL", reason_message=text(language, "reason.proposal_review"), actions=_proposal_actions(proposal_id, language, kind), unchanged=["canonical state"], disclosures=[_disclosure("proposal-approval-boundary", "proposal", text(language, "disclosure.heartbeat" if kind == "heartbeat" else "disclosure.event_approval" if kind == "event" else "disclosure.approval"))])
            else:
                outcome = _outcome("review", text(language, "summary.proposal_reviewed"), reason_code="PROPOSAL_REVIEWED", reason_message=text(language, "reason.proposal_reviewed"), actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")])
        elif pending:
            outcome = _outcome("needs_confirmation", text(language, "summary.status_pending_count", count=pending), reason_code="PENDING_PROPOSAL", reason_message=text(language, "reason.pending_proposal"), actions=_proposal_actions(None, language), unchanged=["canonical state"], disclosures=[_disclosure("proposal-approval-boundary", "proposal", text(language, "disclosure.approval"))])
        else:
            outcome = _outcome("ready", text(language, "summary.no_pending"), reason_code="NO_PENDING_PROPOSALS", reason_message=text(language, "reason.no_pending"), actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")])
        return finish(outcome)

    if command == "approve":
        approved_proposal = result.get("proposal") if isinstance(result.get("proposal"), Mapping) else {}
        queue_only = result.get("applied") is False or approved_proposal.get("kind") == "heartbeat"
        if queue_only:
            outcome = _outcome(
                "completed",
                text(language, "summary.approval_queue_only"),
                reason_code="APPROVAL_COMPLETE",
                reason_message=text(language, "reason.approval_queue_only"),
                actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")],
                unchanged=["canonical state"],
                disclosures=[_disclosure("heartbeat-approval", "heartbeat", text(language, "disclosure.heartbeat"))],
            )
        else:
            outcome = _outcome(
                "completed",
                text(language, "summary.approval_event"),
                reason_code="APPROVAL_COMPLETE",
                reason_message=text(language, "reason.approval_event"),
                actions=[_action("inspect_profile", action_label(language, "inspect_profile"), command="personal-profile"), _action("inspect_status", action_label(language, "inspect_status"), command="status")],
                changed=["approved event/canonical state"],
                unchanged=["original private document"],
                disclosures=[_disclosure("proposal-approval-boundary", "proposal", text(language, "disclosure.event_approval"))],
            )
        return finish(_with_state_actions(outcome, _state_issues(result), command=command, language=language))

    if command == "restore-state":
        outcome = _outcome("completed", text(language, "summary.restore_complete"), reason_code="STATE_RECOVERY_COMPLETE", reason_message=text(language, "reason.restore_complete"), actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")], changed=["current state snapshot"], unchanged=["events.jsonl", "proposals.jsonl", "workspace pipeline"], disclosures=[_disclosure("restore-state-semantics", "recovery", text(language, "disclosure.restore"))])
        return finish(outcome)

    if command in {"private-import", "private-list", "private-doctor"}:
        changed = ["private-store copy and metadata"] if command == "private-import" else []
        unchanged = ["original source file"] if command == "private-import" else []
        outcome = _outcome("completed" if command == "private-import" else "ready", text(language, "summary.private_store_ready"), reason_code="PRIVATE_STORE_READY", reason_message=text(language, "reason.private_store"), actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")], changed=changed, unchanged=unchanged, disclosures=[_disclosure("private-store-boundary", "private_store", text(language, "disclosure.private_store"))])
        return finish(outcome)

    if command in {"personal-profile", "personal-context", "context", "skills"}:
        outcome = _outcome("ready", text(language, "summary.read_only"), reason_code="READ_ONLY_RESULT", reason_message=text(language, "reason.read_only"), actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")], unchanged=["canonical state"])
        return finish(_with_state_actions(outcome, _state_issues(result), command=command, language=language))

    if command in {"plan", "plan-next", "plan-status"}:
        plan_state = str(result.get("status") or "running")
        ux_state = {
            "completed": "completed",
            "blocked": "blocked",
            "failed": "blocked",
            "unsupported": "blocked",
            "paused": "needs_input",
        }.get(plan_state, "ready")
        outcome = _outcome(
            ux_state,
            text(language, "summary.operation_complete"),
            reason_code="EXECUTION_PLAN_RESULT",
            reason_message=text(language, "reason.operation_complete"),
            actions=[_action("inspect_status", action_label(language, "inspect_status"), command="plan-status")],
            changed=["execution plan snapshot"] if command == "plan" else [],
        )
        return finish(outcome)

    if command in {"skill-open", "skill-report"}:
        # AC-7: `skill-open` on a host_required Skill from cli/gui closes itself as `unsupported`
        # instead of leaving an open record. That refusal must not read as success -- the whole
        # point of this gate is that a Skill not actually run must not look like one that was.
        if result.get("status") == "unsupported":
            outcome = _outcome(
                "blocked",
                text(language, "summary.skill_unsupported"),
                reason_code="SKILL_HOST_REQUIRED",
                reason_message=text(language, "reason.skill_unsupported"),
                actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")],
                unchanged=["canonical career facts"],
            )
        else:
            outcome = _outcome(
                "completed",
                text(language, "summary.skill_invocation_recorded"),
                reason_code="SKILL_INVOCATION_RECORDED",
                reason_message=text(language, "reason.skill_invocation_recorded"),
                actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")],
                changed=["skill invocation record"],
            )
        return finish(outcome)

    outcome = _outcome("ready", text(language, "summary.operation_complete"), reason_code="OPERATION_COMPLETE", reason_message=text(language, "reason.operation_complete"), actions=[_action("inspect_status", action_label(language, "inspect_status"), command="status")])
    return finish(_with_state_actions(outcome, _state_issues(result), command=command, language=language))


def _error_code(error: CareerError) -> str:
    if error.code:
        return error.code
    message = str(error).casefold()
    patterns = (
        ("SETUP_REQUIRED", ("not initialized", "career_vault is required", "--vault or career_vault is required", "requires profile.track", "track must be explicit")),
        ("WORKSPACE_NOT_FOUND", ("workspace does not exist", "workspace not found")),
        ("PROPOSAL_NOT_FOUND", ("proposal not found",)),
        ("PROPOSAL_NOT_PENDING", ("proposal is not pending",)),
        ("EVIDENCE_MISMATCH", ("numeric claim is not present",)),
        ("EVIDENCE_REQUIRED", ("require evidence", "confirmed events require evidence")),
        ("DOCUMENT_NOT_FOUND", ("no imported document", "stored bytes for document", "source does not exist")),
        ("DOCUMENT_AMBIGUOUS", ("matches", "must identify exactly one document")),
        ("PRIVATE_STORE_UNSAFE_PATH", ("inside a git worktree",)),
        ("STATE_VERSION_NOT_FOUND", ("version not found",)),
        ("INVALID_STAGE", ("stage is not recognized",)),
        ("INVALID_INPUT", ("must be", "invalid", "requires --", "cannot", "expected one of")),
    )
    for code, needles in patterns:
        if any(needle in message for needle in needles):
            return code
    return "OPERATION_BLOCKED"


def error_payload(error: CareerError, *, language: str | None = None) -> dict[str, Any]:
    language = normalize_language(language)
    code = _error_code(error)
    message = str(error)
    action_map: dict[str, list[dict[str, Any]]] = {
        "SETUP_REQUIRED": [_action("run_setup", action_label(language, "run_setup"), command="setup", operation_kind="repair", requires_confirmation=True)],
        "WORKSPACE_NOT_FOUND": [_action("inspect_status", action_label(language, "inspect_workspace"), command="status", operation_kind="navigate")],
        "PROPOSAL_NOT_FOUND": [_action("review_proposal", action_label(language, "review_proposals"), command="proposals")],
        "PROPOSAL_NOT_PENDING": [_action("review_proposal", action_label(language, "review_proposal"), command="proposals")],
        "EVIDENCE_REQUIRED": [_action("provide_evidence", action_label(language, "provide_evidence"), operation_kind="provide_evidence")],
        "EVIDENCE_MISMATCH": [_action("provide_evidence", action_label(language, "provide_matching_evidence"), operation_kind="provide_evidence")],
        "DOCUMENT_NOT_FOUND": [_action("inspect_context", action_label(language, "inspect_context"), command="private-list")],
        "DOCUMENT_AMBIGUOUS": [_action("inspect_context", action_label(language, "inspect_context"), command="private-list")],
        "PRIVATE_STORE_UNSAFE_PATH": [_action("inspect_context", action_label(language, "inspect_context"), command="private-doctor", operation_kind="repair")],
        "STATE_VERSION_NOT_FOUND": [_action("restore_state", action_label(language, "choose_state_version"), command="restore-state <version>", operation_kind="repair", requires_confirmation=True)],
        "INVALID_STAGE": [_action("inspect_context", action_label(language, "inspect_context"), command="context")],
    }
    actions = action_map.get(code, [_action("retry", action_label(language, "retry"), operation_kind="retry")])
    localized_reason = {
        "SETUP_REQUIRED": "reason.setup_required",
        "GUI_START_FAILED": "reason.gui_start_failed",
        "EVIDENCE_REQUIRED": "action.provide_evidence",
        "EVIDENCE_MISMATCH": "action.provide_matching_evidence",
    }.get(code, "reason.operation_blocked")
    localized_disclosures = []
    if code in {"WORKSPACE_NOT_FOUND", "WORKSPACE_AMBIGUOUS"}:
        localized_disclosures.append(
            _disclosure(
                "workspace-resolution",
                "workspace",
                f"{text(language, 'section.workspace')}: {error.details.get('workspace', text(language, 'guided.workspace_unresolved'))}",
            )
        )
    payload = {
        "ok": False,
        "error": message,
        "error_code": code,
        "retryable": bool(error.retryable),
        "details": dict(error.details),
        "state_changed": bool(error.state_changed),
        "safe_stop": True,
        "retry_count": 0,
        "external_side_effect": False,
        "ux": _outcome(
            "blocked" if not error.state_changed else "recovery_required",
            text(language, "summary.operation_not_completed"),
            reason_code=code,
            reason_message=text(language, localized_reason),
            actions=actions,
            unchanged=["canonical state"] if not error.state_changed else [],
            disclosures=localized_disclosures,
        ),
    }
    payload["ux"]["language"] = language
    return payload


def _domain_detail_lines(payload: Mapping[str, Any], language: str) -> list[str]:
    """Render known user concepts only; JSON retains canonical keys and values."""
    lines: list[str] = []
    mode = str(payload.get("mode") or "")
    if mode in {"plan", "plan-next", "plan-status"}:
        plan_id = payload.get("plan_id")
        status = payload.get("status")
        if plan_id and status:
            lines.append(text(language, "section.execution_plan", id=plan_id, status=domain_label(language, "execution_plan_status", status)))
        if payload.get("goal"):
            lines.append(text(language, "section.plan_goal", goal=payload["goal"]))
        current = payload.get("current_step") if isinstance(payload.get("current_step"), Mapping) else None
        next_step = payload.get("next_step") if isinstance(payload.get("next_step"), Mapping) else None
        if current:
            lines.append(text(language, "section.plan_current", step=current.get("skill") or current.get("id")))
        if next_step:
            lines.append(text(language, "section.plan_next", step=next_step.get("skill") or next_step.get("id")))
    elif mode == "status" or (
        not mode and {"profile", "state", "workspace", "pending_proposals"}.issubset(payload)
    ):
        profile = payload.get("profile") if isinstance(payload.get("profile"), Mapping) else {}
        state = payload.get("state") if isinstance(payload.get("state"), Mapping) else {}
        fields = (
            ("section.track", "track", profile.get("track")),
            ("section.career_status", "career_status", profile.get("career_status")),
            ("section.employment_status", "employment", profile.get("employment_status")),
            ("section.job_search", "job_search", profile.get("job_search")),
            ("section.career_mode", "career_mode", state.get("career_mode")),
            ("section.stage", "pipeline_stage", state.get("stage")),
        )
        for label_key, namespace, value in fields:
            if value is not None:
                lines.append(f"{text(language, label_key)}: {domain_label(language, namespace, value)}")
        open_invocations = payload.get("open_skill_invocations")
        if isinstance(open_invocations, list) and open_invocations:
            lines.append(f"{text(language, 'section.open_skill_invocations')}:")
            for invocation in open_invocations:
                if not isinstance(invocation, Mapping):
                    continue
                lines.append(
                    "- " + text(
                        language, "section.skill_invocation",
                        id=invocation.get("invocation_id"), skill=invocation.get("skill"),
                        status=domain_label(language, "skill_invocation_status", invocation.get("status")),
                    )
                )
    elif mode == "readiness":
        dimensions = payload.get("dimensions") if isinstance(payload.get("dimensions"), Mapping) else {}
        if dimensions:
            lines.append(f"{text(language, 'section.readiness')}:")
            for name, value in dimensions.items():
                lines.append(
                    f"- {domain_label(language, 'readiness_dimension', name)}: "
                    f"{domain_label(language, 'fact_state', value)}"
                )
    elif mode == "weekly-review":
        groups = payload.get("groups") if isinstance(payload.get("groups"), list) else []
        if groups:
            lines.append(f"{text(language, 'section.weekly_review')}:")
            for group in groups:
                if not isinstance(group, Mapping):
                    continue
                title = str(group.get("title") or text(language, "section.untitled"))
                lines.append(f"- {title}")
                for event in group.get("events", []):
                    if not isinstance(event, Mapping):
                        continue
                    event_title = str(event.get("title") or text(language, "section.untitled"))
                    status = domain_label(language, "event_status", event.get("status"))
                    gaps = [
                        domain_label(language, "weekly_gap", gap)
                        for gap in event.get("gaps", [])
                    ]
                    suffix = f" · {text(language, 'section.gaps')}: {', '.join(gaps)}" if gaps else ""
                    lines.append(f"  - {event_title} · {status}{suffix}")
    elif mode == "maintenance-check":
        suggestions = payload.get("suggestions") if isinstance(payload.get("suggestions"), list) else []
        if suggestions:
            lines.append(f"{text(language, 'section.suggestions')}:")
            for suggestion in suggestions:
                if not isinstance(suggestion, Mapping):
                    continue
                label = domain_label(language, "maintenance_suggestion", suggestion.get("kind"))
                context = suggestion.get("title")
                lines.append(f"- {label}{f': {context}' if context else ''}")
    elif mode == "proposals":
        proposals = payload.get("proposals") if isinstance(payload.get("proposals"), list) else []
        counts: dict[tuple[str, str], int] = {}
        for proposal in proposals:
            if not isinstance(proposal, Mapping):
                continue
            marker = (str(proposal.get("kind")), str(proposal.get("status")))
            counts[marker] = counts.get(marker, 0) + 1
        if counts:
            lines.append(f"{text(language, 'section.proposal_types')}:")
            for (kind, status), count in sorted(counts.items()):
                lines.append(
                    f"- {domain_label(language, 'proposal_kind', kind)} · "
                    f"{domain_label(language, 'proposal_status', status)}: {count}"
                )
    elif mode == "sessions" or payload.get("error_code") == "SESSION_AMBIGUOUS":
        if mode == "sessions":
            rows = payload.get("sessions") if isinstance(payload.get("sessions"), list) else []
        else:
            details = payload.get("details") if isinstance(payload.get("details"), Mapping) else {}
            rows = details.get("choices") if isinstance(details.get("choices"), list) else []
        if rows:
            lines.append(f"{text(language, 'section.resumable_work')}:")
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                context = row.get("display_context", row.get("context"))
                context = context if isinstance(context, list) else []
                label = " / ".join(str(item) for item in context if item) or domain_label(
                    language, "workflow", row.get("workflow")
                )
                status = domain_label(
                    language, "session_status", row.get("status", row.get("review_status"))
                )
                stage = row.get("stage")
                stage_text = f" · {domain_label(language, 'session_stage', stage)}" if stage else ""
                lines.append(f"- {label} · {status}{stage_text}")
            if len(rows) > 1:
                lines.append(text(language, "session.resume_hint"))
    elif "invocation_id" in payload and "execution" in payload:
        # skill-open / skill-report results carry no `mode` key; matched by shape instead. The
        # id is the one thing `skill-report` needs from a prior `skill-open`, and without this
        # line here the open -> report loop `_shared/agent_context/routing.md` documents was only
        # completable with `--format json`.
        lines.append(
            text(
                language, "section.skill_invocation",
                id=payload.get("invocation_id"), skill=payload.get("skill"),
                status=domain_label(language, "skill_invocation_status", payload.get("status")),
            )
        )
    return lines


def render_human(payload: Mapping[str, Any]) -> str:
    """Render only the UX projection; JSON remains the default machine contract."""
    ux = payload.get("ux") if isinstance(payload.get("ux"), Mapping) else {}
    language = normalize_language(ux.get("language"))
    raw_state = ux.get("state", "blocked" if payload.get("ok") is False else "ready")
    lines = [f"{text(language, 'section.state')}: {state_label(language, raw_state)}"]
    if ux.get("summary"):
        lines.append(f"{text(language, 'section.summary')}: {ux['summary']}")
    lines.extend(_domain_detail_lines(payload, language))
    reason = ux.get("reason") if isinstance(ux.get("reason"), Mapping) else {}
    if reason.get("message"):
        lines.append(f"{text(language, 'section.reason')}: {reason['message']}")
    disclosures = ux.get("disclosures") if isinstance(ux.get("disclosures"), list) else []
    if disclosures:
        lines.append(f"{text(language, 'section.context')}:")
        for disclosure in disclosures:
            if isinstance(disclosure, Mapping) and disclosure.get("message"):
                lines.append(f"- {disclosure['message']}")
    actions = ux.get("next", {}).get("actions", []) if isinstance(ux.get("next"), Mapping) else []
    if actions:
        lines.append(f"{text(language, 'section.next_actions')}:")
        for action in actions:
            suffix = text(language, "guided.confirmation_suffix") if action.get("requires_confirmation") else ""
            lines.append(f"- {action.get('label')}{suffix}")
    effects = ux.get("effects") if isinstance(ux.get("effects"), Mapping) else {}
    for label_key, key in (("section.changed", "changed"), ("section.unchanged", "unchanged")):
        values = effects.get(key) or []
        if values:
            lines.append(f"{text(language, label_key)}: {', '.join(effect_label(language, value) for value in values)}")
    if payload.get("ok") is False and reason.get("message"):
        lines.insert(0, f"{text(language, 'section.problem')}: {reason['message']}")
    return "\n".join(lines)
