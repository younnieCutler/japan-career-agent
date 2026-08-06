"""Pure helpers for the thin guided Career Agent frontend.

The guided layer receives already-computed state from the runtime facade.  It may describe
available transitions and resolve deterministic input, but it never reads or writes the Vault,
validates facts, approves proposals, or mutates the workspace projection.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


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


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def count_fact_states(value: Any) -> dict[str, int]:
    """Count explicit Unknown and Conflict states without interpreting their values."""
    counts = {"unknown": 0, "conflict": 0}

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            state = str(node.get("state") or "").casefold()
            if state in counts:
                counts[state] += 1
            for key, child in node.items():
                # These fields are evidence metadata, not additional domain state nodes.
                if key not in {"evidence", "candidates", "context"}:
                    walk(child)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for child in node:
                walk(child)

    walk(value)
    return counts


def build_summary(
    *,
    initialized: bool,
    vault: str,
    profile: Mapping[str, Any] | None = None,
    state: Mapping[str, Any] | None = None,
    workspace: Mapping[str, Any] | None = None,
    pending_proposals: int = 0,
    personal_profile: Mapping[str, Any] | None = None,
    status_error: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a metadata-only guided summary from existing command projections."""
    profile = profile or {}
    state = state or {}
    workspace = workspace or {}
    counts = count_fact_states(personal_profile or {})
    track = profile.get("track") or state.get("track")
    graduation_year = profile.get("graduation_year")
    setup_complete = initialized and track in {"shinsotsu", "chuto"}
    if track == "shinsotsu" and not isinstance(graduation_year, int):
        setup_complete = False

    workspace_exists = workspace.get("exists") is True
    pipeline_count = _int(workspace.get("company_count"))
    open_actions = state.get("open_actions") if isinstance(state.get("open_actions"), list) else []
    deadlines = state.get("deadlines") if isinstance(state.get("deadlines"), list) else []
    blockers: list[str] = []
    if not initialized or not setup_complete:
        blockers.append("setup")
    if pending_proposals:
        blockers.append("pending_proposals")
    if status_error:
        blockers.append(str(status_error.get("code") or "workspace"))
    if counts["conflict"]:
        blockers.append("conflict")

    summary = {
        "initialized": initialized,
        "vault": vault,
        "track": track,
        "career_status": profile.get("career_status", state.get("career_status", "active")),
        "target_role": profile.get("target_role"),
        "setup_complete": setup_complete,
        "workspace": {
            "path": workspace.get("path"),
            "exists": workspace_exists,
            "pipeline_exists": workspace.get("pipeline_exists") is True,
            "company_count": pipeline_count,
            "updated": workspace.get("updated"),
        },
        "pending_proposals": _int(pending_proposals),
        "unknown_count": counts["unknown"],
        "conflict_count": counts["conflict"],
        "open_action_count": len(open_actions),
        "deadline_count": len(deadlines),
        "state_version": state.get("version"),
        "major_blockers": blockers,
    }
    if status_error:
        summary["workspace_error"] = {
            "code": str(status_error.get("code") or "WORKSPACE_NOT_FOUND"),
            "message": str(status_error.get("message") or "workspace could not be resolved"),
        }
    return summary


def derive_actions(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Derive only transitions that are valid for the supplied canonical summary."""
    actions: list[dict[str, Any]] = []
    workspace_error = isinstance(summary.get("workspace_error"), Mapping)

    if not summary.get("setup_complete"):
        actions.append(
            _action(
                "complete_setup",
                "Complete setup",
                command="setup",
                operation_kind="repair",
                requires_confirmation=True,
            )
        )
    if workspace_error:
        actions.append(
            _action(
                "inspect_workspace",
                "Choose an existing workspace",
                command="status --workspace <path>",
                operation_kind="navigate",
            )
        )
    if _int(summary.get("pending_proposals")):
        actions.append(
            _action(
                "review_proposals",
                "Review pending proposals",
                command="proposals",
            )
        )
        if _int(summary.get("pending_proposals")) == 1:
            actions.append(
                _action(
                    "approve_proposal",
                    "Approve the pending proposal",
                    command="approve <proposal_id>",
                    operation_kind="approve",
                    requires_confirmation=True,
                )
            )
    if _int(summary.get("unknown_count")):
        actions.append(
            _action(
                "inspect_unknown",
                "Inspect Unknown evidence",
                command="personal-profile",
                operation_kind="inspect",
            )
        )
    if _int(summary.get("conflict_count")):
        actions.append(
            _action(
                "inspect_conflict",
                "Inspect conflicting evidence",
                command="personal-profile",
                operation_kind="inspect",
            )
        )
    workspace = summary.get("workspace") if isinstance(summary.get("workspace"), Mapping) else {}
    if _int(workspace.get("company_count")) or _int(summary.get("open_action_count")) or _int(summary.get("deadline_count")):
        actions.append(
            _action(
                "inspect_workspace_state",
                "View workspace and pipeline state",
                command="status",
                operation_kind="inspect",
            )
        )
    if not any(action["id"] in {"inspect_status", "inspect_workspace_state"} for action in actions):
        actions.append(
            _action(
                "inspect_status",
                "Inspect current status",
                command="status",
                operation_kind="inspect",
            )
        )
    if summary.get("setup_complete") and not _int(summary.get("pending_proposals")):
        actions.append(
            _action(
                "start_task",
                "Start a user-described task",
                command="run --mode chat --message <message>",
                operation_kind="propose",
                requires_confirmation=True,
            )
        )
    if summary.get("state_version"):
        actions.append(
            _action(
                "restore_state",
                "Restore a saved state snapshot",
                command="restore-state <version>",
                operation_kind="repair",
                requires_confirmation=True,
            )
        )
    if summary.get("setup_complete"):
        actions.append(
            _action(
                "inspect_context",
                "Inspect shared context",
                command="context",
                operation_kind="inspect",
            )
        )
    actions.append(_action("exit", "Exit", operation_kind="keep_state"))

    # Stable ordering and IDs make scripted tests independent of incidental wording.
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action in actions:
        action_id = str(action.get("id"))
        if action_id not in seen:
            seen.add(action_id)
            unique.append(action)
    return unique


ALIASES = {
    "q": "exit",
    "quit": "exit",
    "cancel": "exit",
    "setup": "complete_setup",
    "review": "review_proposals",
    "approve": "approve_proposal",
    "unknown": "inspect_unknown",
    "conflict": "inspect_conflict",
    "status": "inspect_status",
    "context": "inspect_context",
}


def resolve_choice(choice: str, actions: Sequence[Mapping[str, Any]]) -> str | None:
    """Resolve a stable action ID, a one-based menu number, or a documented alias."""
    raw = str(choice).strip().casefold()
    if not raw:
        return None
    if raw.isdigit():
        index = int(raw) - 1
        if 0 <= index < len(actions):
            return str(actions[index].get("id"))
        return None
    raw = ALIASES.get(raw, raw)
    return raw if any(str(action.get("id")) == raw for action in actions) else None


def guided_state(summary: Mapping[str, Any], *, selection_status: str | None = None) -> str:
    """Map existing blockers to the shared UX vocabulary without making a decision."""
    if selection_status in {"invalid", "blocked"}:
        return "blocked"
    if selection_status == "confirmation_required":
        return "needs_confirmation"
    if not summary.get("setup_complete"):
        return "needs_input"
    if isinstance(summary.get("workspace_error"), Mapping):
        return "blocked"
    if _int(summary.get("pending_proposals")):
        return "needs_confirmation"
    if _int(summary.get("unknown_count")) or _int(summary.get("conflict_count")):
        return "review"
    return "ready"


def render_human(result: Mapping[str, Any]) -> str:
    """Render the guided menu without exposing private document bodies."""
    guided = result.get("guided") if isinstance(result.get("guided"), Mapping) else {}
    summary = guided.get("summary") if isinstance(guided.get("summary"), Mapping) else {}
    actions = guided.get("available_actions") if isinstance(guided.get("available_actions"), list) else []
    lines = ["Guided Career Agent", f"State: {guided.get('state', 'ready')}", "Current state:"]
    lines.append(f"- track: {summary.get('track') or 'not set'}")
    lines.append(f"- setup: {'complete' if summary.get('setup_complete') else 'required'}")
    workspace = summary.get("workspace") if isinstance(summary.get("workspace"), Mapping) else {}
    lines.append(f"- workspace: {workspace.get('path') or 'not resolved'}")
    lines.append(f"- pending proposals: {summary.get('pending_proposals', 0)}")
    lines.append(f"- Unknown: {summary.get('unknown_count', 0)}")
    lines.append(f"- Conflict: {summary.get('conflict_count', 0)}")
    if summary.get("major_blockers"):
        lines.append(f"- blockers: {', '.join(str(item) for item in summary['major_blockers'])}")
    lines.append("Available actions:")
    for index, action in enumerate(actions, start=1):
        suffix = " (confirmation required)" if action.get("requires_confirmation") else ""
        lines.append(f"{index}. {action.get('label', action.get('id'))}{suffix} [{action.get('id')}]")
    selection = result.get("selection") if isinstance(result.get("selection"), Mapping) else {}
    if selection.get("status"):
        lines.append(f"Selection: {selection['status']}")
    if result.get("error"):
        lines.insert(0, f"Problem: {result['error']}")
    if result.get("next_command"):
        lines.append(f"Next command: {result['next_command']}")
    return "\n".join(lines)
