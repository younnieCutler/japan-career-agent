#!/usr/bin/env python3
"""Deterministic guided interaction over the runtime facades.

The presentation shapes live in `guided`, which never touches the Vault. This module reads and
writes through the same commands a user could type, so a guided run and a typed run cannot
diverge.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from approvals import approve
from experiences import run_context
from guided import (
    build_summary,
    derive_actions,
    guided_state,
    render_human as render_guided_human,
    resolve_choice,
)
from lifecycle import restore_state
from localization import normalize_language, text
from models import CareerError, default_state, TRACKS
from onboarding import complete_onboarding, setup
from persistence import read_jsonl
from personal_timeline import project
from projection import pipeline_file, workspace_path
from proposals import list_proposals, run_chat
from routing import language_for
from ux import error_payload
from vault import CareerVault
from views import status


def _guided_workspace_fallback(
    workspace: str | Path | None, error: CareerError | None = None,
) -> dict[str, Any]:
    """Return safe workspace metadata when the normal status read is blocked."""
    resolved = workspace_path(workspace)
    return {
        "path": str(resolved),
        "exists": resolved.is_dir(),
        "pipeline": str(pipeline_file(workspace)),
        "pipeline_exists": pipeline_file(workspace).is_file(),
        "company_count": 0,
        "updated": None,
        "error": {
            "code": error.code if error and error.code else "WORKSPACE_NOT_FOUND",
            "message": str(error) if error else "workspace could not be resolved",
        } if error else None,
    }


def _guided_snapshot(
    home: CareerVault, workspace: str | Path | None, as_of: str,
) -> dict[str, Any]:
    """Collect the existing read projections used to render one guided menu."""
    initialized = home.initialized()
    profile = home.load_profile() if home.profile.is_file() else {}
    state = home.load_state() if home.state_toml.is_file() else default_state()
    status_error: dict[str, Any] | None = None
    pending_kind: str | None = None
    if initialized:
        try:
            status_result = status(home, workspace=workspace)
            workspace_result = status_result.get("workspace")
            if not isinstance(workspace_result, dict):
                workspace_result = _guided_workspace_fallback(workspace)
            pending = status_result.get("pending_proposals", 0)
            pending_kind = str(status_result.get("pending_kind") or "") or None
        except CareerError as exc:
            status_error = {
                "code": exc.code or "WORKSPACE_NOT_FOUND",
                "message": str(exc),
            }
            workspace_result = _guided_workspace_fallback(workspace, exc)
            pending = sum(1 for row in read_jsonl(home.proposals) if row.get("status") == "pending")
            pending_rows = [row for row in read_jsonl(home.proposals) if row.get("status") == "pending"]
            if len(pending_rows) == 1:
                pending_kind = str(pending_rows[0].get("kind") or "") or None
    else:
        workspace_result = _guided_workspace_fallback(workspace)
        pending = 0
    personal_profile = project(read_jsonl(home.events), as_of) if initialized else {}
    summary = build_summary(
        initialized=initialized,
        vault=str(home.path),
        profile=profile,
        state=state,
        workspace=workspace_result,
        pending_proposals=pending,
        pending_kind=pending_kind,
        personal_profile=personal_profile,
        status_error=status_error,
    )
    return {
        "summary": summary,
        "available_actions": derive_actions(summary),
        "state": guided_state(summary),
        "personal_profile": personal_profile,
    }


def _guided_result(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Wrap one snapshot in the additive guided command result shape."""
    return {
        "mode": "guided",
        "ok": True,
        "guided": {
            "state": snapshot["state"],
            "summary": snapshot["summary"],
            "available_actions": snapshot["available_actions"],
        },
        "read_only": True,
        "state_changed": False,
        "selection": {"status": "menu", "requested": None, "action": None},
    }


def _guided_selection(
    result: dict[str, Any],
    *,
    requested: str | None,
    action: str | None,
    status_value: str,
    error: str | None = None,
    next_command: str | None = None,
) -> dict[str, Any]:
    result["selection"] = {
        "status": status_value,
        "requested": requested,
        "action": action,
    }
    if error:
        result["ok"] = False
        result["error"] = error
        result["error_code"] = "INVALID_INPUT" if status_value == "invalid" else "OPERATION_BLOCKED"
        result["safe_stop"] = True
        result["state_changed"] = False
        result["read_only"] = True
    if next_command:
        result["next_command"] = next_command
    return result


def run_guided(
    home: CareerVault,
    *,
    workspace: str | Path | None = None,
    as_of: str,
    choices: Iterable[str] | None = None,
    interactive: bool = False,
    confirm: bool = False,
    message: str | None = None,
    proposal_id: str | None = None,
    evidence: list[str] | None = None,
    deadline: str | None = None,
    company: str | None = None,
    compensation: float | None = None,
    currency: str | None = None,
    next_action: str | None = None,
    version: str | None = None,
    track: str | None = None,
    target_role: str | None = None,
    graduation_year: int | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Run one deterministic guided interaction over existing runtime facades.

    ``choices`` is the CI/test seam.  Interactive prompting is used only for a real TTY and is
    deliberately kept at this frontend boundary; every operation still dispatches to the same
    setup/approve/read functions used by the canonical commands.
    """
    snapshot = _guided_snapshot(home, workspace, as_of)
    result = _guided_result(snapshot)
    queue = list(choices or [])
    if interactive and not queue:
        print(render_guided_human(result))
        try:
            queue.append(input(text(normalize_language(snapshot["summary"].get("language")), "guided.prompt")).strip() or "exit")
        except EOFError:
            queue.append("exit")
    if not queue:
        return result

    requested = str(queue[0])
    resolved = resolve_choice(requested, snapshot["available_actions"])
    if resolved is None:
        return _guided_selection(
            result,
            requested=requested,
            action=None,
            status_value="invalid",
            error="guided choice is not one of the available action IDs or menu numbers",
        )
    if resolved == "exit":
        return _guided_selection(result, requested=requested, action=resolved, status_value="cancelled")

    write_action = resolved in {"complete_setup", "start_task", "approve_proposal", "restore_state"}
    effective_confirm = confirm
    if write_action and not effective_confirm and len(queue) > 1:
        confirmation = str(queue[1]).strip().casefold()
        if confirmation in {"confirm", "confirmed", "yes", "y", "approve"}:
            effective_confirm = True
        elif confirmation in {"cancel", "cancelled", "no", "n", "exit"}:
            return _guided_selection(result, requested=requested, action=resolved, status_value="cancelled")
    if write_action and not effective_confirm:
        command = {
            "complete_setup": "setup",
            "start_task": "run --mode chat --message <message>",
            "approve_proposal": "approve <proposal_id>",
            "restore_state": "restore-state <version>",
        }[resolved]
        return _guided_selection(
            result,
            requested=requested,
            action=resolved,
            status_value="confirmation_required",
            next_command=f"{command} (confirm explicitly before writing)",
        )

    try:
        if resolved == "complete_setup":
            profile = home.load_profile() if home.profile.is_file() else {}
            selected_track = track or profile.get("track")
            if selected_track not in TRACKS:
                return _guided_selection(
                    result,
                    requested=requested,
                    action=resolved,
                    status_value="blocked",
                    error="guided setup needs --track shinsotsu or --track chuto",
                    next_command="setup --track <shinsotsu|chuto>",
                )
            selected_year = graduation_year or profile.get("graduation_year")
            if selected_track == "shinsotsu" and not isinstance(selected_year, int):
                return _guided_selection(
                    result,
                    requested=requested,
                    action=resolved,
                    status_value="blocked",
                    error="guided setup needs --graduation-year for shinsotsu",
                    next_command="setup --track shinsotsu --graduation-year <YYYY>",
                )
            action_result = setup(
                home.path,
                track=selected_track,
                target_role=target_role,
                graduation_year=graduation_year,
                language=language,
            )
        elif resolved == "approve_proposal":
            pending = list_proposals(home, include_all=False).get("proposals", [])
            selected_id = proposal_id or (pending[0].get("id") if len(pending) == 1 else None)
            if not selected_id:
                return _guided_selection(
                    result,
                    requested=requested,
                    action=resolved,
                    status_value="blocked",
                    error="guided approval needs exactly one pending proposal or --proposal-id",
                    next_command="proposals",
                )
            action_result = approve(
                home,
                str(selected_id),
                evidence=evidence,
                deadline=deadline,
                company=company,
                compensation=compensation,
                currency=currency,
                workspace=workspace,
                next_action=next_action,
            )
        elif resolved == "start_task":
            if not str(message or "").strip():
                return _guided_selection(
                    result,
                    requested=requested,
                    action=resolved,
                    status_value="blocked",
                    error="guided task needs --message; it never invents a task for the user",
                    next_command="run --mode chat --message <message>",
                )
            action_result = run_chat(
                home,
                Path(__file__).resolve().parent.parent,
                str(message).strip(),
                track,
                as_of,
            )
            complete_onboarding(home, action_result)
        elif resolved == "restore_state":
            selected_version = version
            if not selected_version:
                return _guided_selection(
                    result,
                    requested=requested,
                    action=resolved,
                    status_value="blocked",
                    error="guided recovery needs --version for a saved state snapshot",
                    next_command="restore-state <version>",
                )
            action_result = restore_state(home, str(selected_version))
        elif resolved == "review_proposals":
            action_result = list_proposals(home, include_all=False)
        elif resolved in {"inspect_unknown", "inspect_conflict", "inspect_status", "inspect_workspace_state"}:
            action_result = (
                status(home, workspace=workspace)
                if resolved != "inspect_unknown" and resolved != "inspect_conflict"
                else project(read_jsonl(home.events), as_of)
            )
        elif resolved == "inspect_context":
            action_result = run_context(home, None, None, as_of)
        elif resolved == "inspect_workspace":
            action_result = {
                "mode": "workspace",
                "workspace": _guided_workspace_fallback(workspace),
                "read_only": True,
            }
        else:
            return _guided_selection(
                result,
                requested=requested,
                action=resolved,
                status_value="invalid",
                error="guided action is not dispatchable",
            )
    except CareerError as exc:
        failed = _guided_snapshot(home, workspace, as_of)
        failed_result = _guided_result(failed)
        failed_result.update(error_payload(exc, language=language_for(message or "") if message else normalize_language(home.load_profile().get("language"))))
        failed_result["guided"] = {
            "state": guided_state(failed["summary"], selection_status="blocked"),
            "summary": failed["summary"],
            "available_actions": failed["available_actions"],
        }
        failed_result["selection"] = {
            "status": "blocked",
            "requested": requested,
            "action": resolved,
        }
        failed_result["state_changed"] = bool(exc.state_changed)
        failed_result["read_only"] = not bool(exc.state_changed)
        return failed_result

    result["selection"] = {
        "status": "completed",
        "requested": requested,
        "action": resolved,
    }
    result["action_result"] = action_result
    result["read_only"] = not write_action
    result["write_performed"] = write_action
    result["state_changed"] = resolved in {"complete_setup", "restore_state"} or (
        resolved == "approve_proposal" and action_result.get("applied", True) is not False
    )
    if write_action:
        refreshed = _guided_snapshot(home, workspace, as_of)
        result["guided"] = {
            "state": refreshed["state"],
            "summary": refreshed["summary"],
            "available_actions": refreshed["available_actions"],
        }
    return result
