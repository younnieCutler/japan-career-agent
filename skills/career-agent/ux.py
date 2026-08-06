"""Thin, deterministic UX projection for Career Agent command results.

This module only translates already-computed command results and expected ``CareerError``
metadata into a common state/reason/transition shape.  It never validates evidence, derives
matching states, reads files, or mutates canonical state.
"""

from __future__ import annotations

from typing import Any, Mapping

from models import CareerError


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
    }


def _proposal_id(result: Mapping[str, Any]) -> str | None:
    proposal = result.get("proposal")
    if isinstance(proposal, Mapping):
        value = proposal.get("id")
        return str(value) if value else None
    return None


def _proposal_actions(proposal_id: str | None) -> list[dict[str, Any]]:
    review_command = "proposals"
    approve_command = "approve <proposal_id>"
    if proposal_id:
        review_command = f"proposals --id {proposal_id}"
        approve_command = f"approve {proposal_id}"
    return [
        _action("review_proposal", "Review proposal", command=review_command),
        _action(
            "approve_proposal",
            "Approve proposal",
            command=approve_command,
            operation_kind="approve",
            requires_confirmation=True,
        ),
        _action("keep_pending", "Keep pending", operation_kind="keep_state"),
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
) -> dict[str, Any]:
    if not issues:
        return outcome
    outcome["issues"] = issues
    ids = {str(item.get("code")) for item in issues}
    if "FACT_UNKNOWN" in ids:
        outcome["next"]["actions"].extend(
            [
                _action("inspect_context", "Inspect related evidence", command="context"),
                _action("keep_unknown", "Keep Unknown", operation_kind="keep_state"),
            ]
        )
    if "FACT_CONFLICT" in ids:
        outcome["next"]["actions"].extend(
            [
                _action("inspect_conflict", "Inspect conflicting evidence", command="personal-profile"),
                _action("keep_conflict", "Keep Conflict", operation_kind="keep_state"),
            ]
        )
    if outcome["state"] == "ready":
        outcome["state"] = "review"
        outcome["reason"] = {
            "code": "REVIEW_REQUIRED",
            "message": "The command completed, but one or more evidence states need review.",
        }
    return outcome


def attach(command: str, result: Mapping[str, Any], *, args: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Add the additive ``ux`` block to one successful command result."""
    args = args or {}
    mode = str(result.get("mode") or command)
    proposal_id = _proposal_id(result)
    proposal = result.get("proposal")
    proposal_pending = isinstance(proposal, Mapping) and proposal.get("status") == "pending"
    pending = result.get("pending_proposals")
    if not isinstance(pending, int):
        pending = 1 if proposal_pending else 0

    if command == "setup":
        needs_input = result.get("needs_input") or []
        diagnosis = result.get("doctor") if isinstance(result.get("doctor"), Mapping) else {}
        if needs_input:
            outcome = _outcome(
                "needs_input",
                "Career Agent setup needs profile input.",
                reason_code="SETUP_REQUIRED",
                reason_message="The profile is missing required setup fields.",
                actions=[_action("run_setup", "Complete setup", command="setup", operation_kind="repair", requires_confirmation=True)],
                issues=[{"code": "SETUP_REQUIRED", "subject": str(field), "message": "This setup field is required."} for field in needs_input],
            )
        elif diagnosis.get("ok") is False:
            outcome = _outcome(
                "blocked",
                "Career Agent setup is blocked by doctor errors.",
                reason_code="SETUP_REQUIRED",
                reason_message="Setup completed its write step, but the vault still has blocking errors.",
                actions=[_action("run_doctor", "Inspect setup errors", command="doctor", operation_kind="repair", requires_confirmation=False)],
                unchanged=["canonical career facts"],
            )
        else:
            outcome = _outcome(
                "ready",
                "Career Agent setup is ready.",
                reason_code="SETUP_COMPLETE",
                reason_message="The vault and profile passed the setup checks.",
                actions=[_action("inspect_status", "Inspect current status", command="status")],
                changed=["vault/profile setup" if result.get("created") else "profile setup"],
            )
        return {**dict(result), "ux": outcome}

    if command == "doctor":
        errors = result.get("errors") if isinstance(result.get("errors"), list) else []
        warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
        if errors:
            outcome = _outcome(
                "blocked",
                "Doctor found blocking setup or workspace issues.",
                reason_code="SETUP_REQUIRED",
                reason_message="The reported errors must be inspected before dependent operations can proceed.",
                actions=[_action("run_doctor", "Run doctor with repair", command="doctor --fix", operation_kind="repair", requires_confirmation=True)],
                issues=[{"code": "DOCTOR_ERROR", "subject": "doctor", "message": str(item)} for item in errors],
                unchanged=["canonical career state"],
            )
        elif warnings:
            outcome = _outcome(
                "review",
                "Doctor completed with warnings to review.",
                reason_code="REVIEW_REQUIRED",
                reason_message="The vault is usable, but some profile or context warnings remain.",
                actions=[_action("inspect_status", "Inspect current status", command="status")],
                issues=[{"code": "DOCTOR_WARNING", "subject": "doctor", "message": str(item)} for item in warnings],
            )
        else:
            outcome = _outcome("ready", "Doctor checks passed.", reason_code="DOCTOR_OK", reason_message="No blocking doctor findings were reported.", actions=[_action("inspect_status", "Inspect current status", command="status")])
        return {**dict(result), "ux": outcome}

    if command == "status":
        if not result.get("profile", {}).get("track"):
            outcome = _outcome(
                "needs_input",
                "A career track is still required.",
                reason_code="SETUP_REQUIRED",
                reason_message="The vault is initialized, but profile.track is not set.",
                actions=[_action("run_setup", "Complete setup", command="setup", operation_kind="repair", requires_confirmation=True)],
            )
        elif pending:
            outcome = _outcome(
                "needs_confirmation",
                f"{pending} proposal(s) are waiting for explicit approval.",
                reason_code="PENDING_PROPOSAL",
                reason_message="Draft proposals are not canonical until explicitly approved.",
                actions=_proposal_actions(None),
                unchanged=["canonical state until approval"],
            )
        else:
            outcome = _outcome(
                "ready",
                "Career Agent is ready for the next user-owned action.",
                reason_code="STATUS_READY",
                reason_message="No pending approval is blocking the current status.",
                actions=[_action("inspect_profile", "Inspect personal profile", command="personal-profile"), _action("inspect_context", "Inspect shared context", command="context")],
            )
        return {**dict(result), "ux": outcome}

    if command in {"run", "propose-fact", "propose-context"}:
        operation_created_pending = command == "run" and str(result.get("mode")) in {"heartbeat", "discover"}
        if proposal_pending or pending or operation_created_pending:
            outcome = _outcome(
                "needs_confirmation",
                "A proposal was created and is waiting for review.",
                reason_code="PENDING_PROPOSAL",
                reason_message="The proposal is not canonical until explicit approval.",
                actions=_proposal_actions(proposal_id),
                unchanged=["personal profile and canonical state"],
            )
        elif result.get("needs_confirmation"):
            outcome = _outcome(
                "needs_input",
                str(result.get("question") or "More setup input is required before a proposal can be created."),
                reason_code="SETUP_REQUIRED",
                reason_message="The existing routing contract requested missing user input.",
                actions=[_action("run_setup", "Complete required setup", command="setup", operation_kind="repair", requires_confirmation=True)],
            )
        else:
            outcome = _outcome("completed", f"{mode} completed.", reason_code="OPERATION_COMPLETE", reason_message="The existing command completed without a pending proposal.", actions=[_action("inspect_status", "Inspect current status", command="status")])
        return {**dict(result), "ux": _with_state_actions(outcome, _state_issues(result), command=command)}

    if command == "proposals":
        if result.get("proposal"):
            status = str(result["proposal"].get("status") or "")
            if status == "pending":
                outcome = _outcome("needs_confirmation", "Review this proposal before approval.", reason_code="PENDING_PROPOSAL", reason_message="The proposal remains a draft until explicit approval.", actions=_proposal_actions(proposal_id), unchanged=["canonical state"])
            else:
                outcome = _outcome("review", "Proposal review completed.", reason_code="PROPOSAL_REVIEWED", reason_message="The proposal status is shown without changing it.", actions=[_action("inspect_status", "Inspect current status", command="status")])
        elif pending:
            outcome = _outcome("needs_confirmation", f"{pending} pending proposal(s) need review.", reason_code="PENDING_PROPOSAL", reason_message="Pending proposals are not canonical state.", actions=_proposal_actions(None), unchanged=["canonical state"])
        else:
            outcome = _outcome("ready", "No pending proposals need approval.", reason_code="NO_PENDING_PROPOSALS", reason_message="The proposal queue is clear for the current filter.", actions=[_action("inspect_status", "Inspect current status", command="status")])
        return {**dict(result), "ux": outcome}

    if command == "approve":
        outcome = _outcome("completed", "Proposal approved and canonical state updated.", reason_code="APPROVAL_COMPLETE", reason_message="The existing approval and evidence checks passed.", actions=[_action("inspect_profile", "Inspect personal profile", command="personal-profile"), _action("inspect_status", "Inspect current status", command="status")], changed=["approved event/canonical state"], unchanged=["original private document"])
        return {**dict(result), "ux": _with_state_actions(outcome, _state_issues(result), command=command)}

    if command == "restore-state":
        outcome = _outcome("completed", "State snapshot restored for recovery.", reason_code="STATE_RECOVERY_COMPLETE", reason_message="Only the current snapshot changed; append-only history was retained.", actions=[_action("inspect_status", "Inspect current status", command="status")], changed=["current state snapshot"], unchanged=["events.jsonl", "proposals.jsonl", "workspace pipeline"])
        return {**dict(result), "ux": outcome}

    if command in {"private-import", "private-list", "private-doctor"}:
        changed = ["private-store copy and metadata"] if command == "private-import" else []
        unchanged = ["original source file"] if command == "private-import" else []
        outcome = _outcome("completed" if command == "private-import" else "ready", f"{mode} completed.", reason_code="PRIVATE_STORE_READY", reason_message="Private-store boundaries were preserved.", actions=[_action("inspect_status", "Inspect current status", command="status")], changed=changed, unchanged=unchanged)
        return {**dict(result), "ux": outcome}

    if command in {"personal-profile", "personal-context", "context"}:
        outcome = _outcome("ready", f"{mode} is available for inspection.", reason_code="READ_ONLY_RESULT", reason_message="This command did not change canonical state.", actions=[_action("inspect_status", "Inspect current status", command="status")], unchanged=["canonical state"])
        return {**dict(result), "ux": _with_state_actions(outcome, _state_issues(result), command=command)}

    outcome = _outcome("ready", f"{mode} completed.", reason_code="OPERATION_COMPLETE", reason_message="The command completed.", actions=[_action("inspect_status", "Inspect current status", command="status")])
    return {**dict(result), "ux": _with_state_actions(outcome, _state_issues(result), command=command)}


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


def error_payload(error: CareerError) -> dict[str, Any]:
    code = _error_code(error)
    message = str(error)
    action_map: dict[str, list[dict[str, Any]]] = {
        "SETUP_REQUIRED": [_action("run_setup", "Run setup", command="setup", operation_kind="repair", requires_confirmation=True)],
        "WORKSPACE_NOT_FOUND": [_action("inspect_status", "Choose an existing workspace", command="status", operation_kind="navigate")],
        "PROPOSAL_NOT_FOUND": [_action("review_proposal", "List pending proposals", command="proposals")],
        "PROPOSAL_NOT_PENDING": [_action("review_proposal", "Review proposal status", command="proposals")],
        "EVIDENCE_REQUIRED": [_action("provide_evidence", "Provide evidence and retry", operation_kind="provide_evidence")],
        "EVIDENCE_MISMATCH": [_action("provide_evidence", "Provide matching evidence and retry", operation_kind="provide_evidence")],
        "DOCUMENT_NOT_FOUND": [_action("inspect_context", "Inspect private-store documents", command="private-list")],
        "DOCUMENT_AMBIGUOUS": [_action("inspect_context", "Inspect private-store documents", command="private-list")],
        "PRIVATE_STORE_UNSAFE_PATH": [_action("inspect_context", "Choose a private store outside the worktree", command="private-doctor", operation_kind="repair")],
        "STATE_VERSION_NOT_FOUND": [_action("restore_state", "Choose a persisted state version", command="restore-state <version>", operation_kind="repair", requires_confirmation=True)],
        "INVALID_STAGE": [_action("inspect_context", "Inspect supported stages", command="context")],
    }
    actions = action_map.get(code, [_action("retry", "Review the input and retry", operation_kind="retry")])
    return {
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
            "The operation was not completed.",
            reason_code=code,
            reason_message=message.splitlines()[0],
            actions=actions,
            unchanged=["canonical state"] if not error.state_changed else [],
        ),
    }


def render_human(payload: Mapping[str, Any]) -> str:
    """Render only the UX projection; JSON remains the default machine contract."""
    ux = payload.get("ux") if isinstance(payload.get("ux"), Mapping) else {}
    lines = [f"State: {ux.get('state', 'blocked' if payload.get('ok') is False else 'ready')}"]
    if ux.get("summary"):
        lines.append(f"Summary: {ux['summary']}")
    reason = ux.get("reason") if isinstance(ux.get("reason"), Mapping) else {}
    if reason.get("message"):
        lines.append(f"Reason: {reason['message']}")
    actions = ux.get("next", {}).get("actions", []) if isinstance(ux.get("next"), Mapping) else []
    if actions:
        lines.append("Next actions:")
        for action in actions:
            suffix = " (confirmation required)" if action.get("requires_confirmation") else ""
            command = f" -> {action['command']}" if action.get("command") else ""
            lines.append(f"- {action.get('id')}: {action.get('label')}{command}{suffix}")
    effects = ux.get("effects") if isinstance(ux.get("effects"), Mapping) else {}
    for label, key in (("Changed", "changed"), ("Unchanged", "unchanged")):
        values = effects.get(key) or []
        if values:
            lines.append(f"{label}: {', '.join(str(value) for value in values)}")
    if payload.get("ok") is False and payload.get("error"):
        lines.insert(0, f"Problem: {payload['error']}")
    return "\n".join(lines)
