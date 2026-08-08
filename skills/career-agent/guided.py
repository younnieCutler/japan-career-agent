"""Pure helpers for the thin guided Career Agent frontend.

The guided layer receives already-computed state from the runtime facade.  It may describe
available transitions and resolve deterministic input, but it never reads or writes the Vault,
validates facts, approves proposals, or mutates the workspace projection.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from localization import action_label, normalize_language, state_label, text


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
    pending_kind: str | None = None,
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

    career_status = profile.get("career_status", state.get("career_status", "active"))
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
        "career_status": career_status,
        # Onboarding is a stage of normal use, not a broken setup, so it is reported on its own
        # instead of being folded into `setup_complete` or `major_blockers`.
        "onboarding": career_status == "onboarding",
        "target_role": profile.get("target_role"),
        "language": normalize_language(profile.get("language")),
        "setup_complete": setup_complete,
        "workspace": {
            "path": workspace.get("path"),
            "exists": workspace_exists,
            "pipeline_exists": workspace.get("pipeline_exists") is True,
            "company_count": pipeline_count,
            "updated": workspace.get("updated"),
        },
        "pending_proposals": _int(pending_proposals),
        "pending_kind": pending_kind,
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


def derive_actions(summary: Mapping[str, Any], *, language: str | None = None) -> list[dict[str, Any]]:
    """Derive only transitions that are valid for the supplied canonical summary."""
    language = normalize_language(language or summary.get("language"))
    actions: list[dict[str, Any]] = []
    workspace_error = isinstance(summary.get("workspace_error"), Mapping)

    if not summary.get("setup_complete"):
        actions.append(
            _action(
                "complete_setup",
                action_label(language, "complete_setup"),
                command="setup",
                operation_kind="repair",
                requires_confirmation=True,
            )
        )
    if workspace_error:
        actions.append(
            _action(
                "inspect_workspace",
                action_label(language, "inspect_workspace"),
                command="status --workspace <path>",
                operation_kind="navigate",
            )
        )
    if _int(summary.get("pending_proposals")):
        actions.append(
            _action(
                "review_proposals",
                action_label(language, "review_proposals"),
                command="proposals",
            )
        )
        if _int(summary.get("pending_proposals")) == 1:
            actions.append(
                _action(
                    "approve_proposal",
                    action_label(language, "approve_proposal", proposal_kind=summary.get("pending_kind")),
                    command="approve <proposal_id>",
                    operation_kind="approve",
                    requires_confirmation=True,
                )
            )
    if _int(summary.get("unknown_count")):
        actions.append(
            _action(
                "inspect_unknown",
                action_label(language, "inspect_unknown"),
                command="personal-profile",
                operation_kind="inspect",
            )
        )
    if _int(summary.get("conflict_count")):
        actions.append(
            _action(
                "inspect_conflict",
                action_label(language, "inspect_conflict"),
                command="personal-profile",
                operation_kind="inspect",
            )
        )
    workspace = summary.get("workspace") if isinstance(summary.get("workspace"), Mapping) else {}
    if _int(workspace.get("company_count")) or _int(summary.get("open_action_count")) or _int(summary.get("deadline_count")):
        actions.append(
            _action(
                "inspect_workspace_state",
                action_label(language, "inspect_workspace_state"),
                command="status",
                operation_kind="inspect",
            )
        )
    if not any(action["id"] in {"inspect_status", "inspect_workspace_state"} for action in actions):
        actions.append(
            _action(
                "inspect_status",
                action_label(language, "inspect_status"),
                command="status",
                operation_kind="inspect",
            )
        )
    if summary.get("setup_complete") and not _int(summary.get("pending_proposals")):
        actions.append(
            _action(
                "start_task",
                action_label(language, "start_task"),
                command="run --mode chat --message <message>",
                operation_kind="propose",
                requires_confirmation=True,
            )
        )
    if summary.get("state_version"):
        actions.append(
            _action(
                "restore_state",
                action_label(language, "restore_state"),
                command="restore-state <version>",
                operation_kind="repair",
                requires_confirmation=True,
            )
        )
    if summary.get("setup_complete"):
        actions.append(
            _action(
                "inspect_context",
                action_label(language, "inspect_context"),
                command="context",
                operation_kind="inspect",
            )
        )
    actions.append(_action("exit", action_label(language, "exit"), operation_kind="keep_state"))

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
    ux = result.get("ux") if isinstance(result.get("ux"), Mapping) else {}
    language = normalize_language(ux.get("language") or summary.get("language"))
    lines = [text(language, "summary.guided_title"), f"{text(language, 'section.state')}: {state_label(language, guided.get('state', 'ready'))}", f"{text(language, 'section.current_state')}:"]
    lines.append(f"- {text(language, 'section.track')}: {summary.get('track') or text(language, 'guided.track_unset')}")
    lines.append(f"- {text(language, 'section.onboarding')}: {text(language, 'guided.onboarding_active' if summary.get('onboarding') else 'guided.onboarding_done')}")
    lines.append(f"- {text(language, 'section.target_role')}: {summary.get('target_role') or text(language, 'guided.target_role_unset')}")
    lines.append(f"- {text(language, 'section.setup')}: {text(language, 'guided.setup_complete' if summary.get('setup_complete') else 'guided.setup_required')}")
    workspace = summary.get("workspace") if isinstance(summary.get("workspace"), Mapping) else {}
    lines.append(f"- {text(language, 'section.workspace')}: {workspace.get('path') or text(language, 'guided.workspace_unresolved')}")
    lines.append(f"- {text(language, 'section.pending')}: {summary.get('pending_proposals', 0)}")
    lines.append(f"- {text(language, 'section.unknown')}: {summary.get('unknown_count', 0)}")
    lines.append(f"- {text(language, 'section.conflict')}: {summary.get('conflict_count', 0)}")
    if ux.get("summary"):
        lines.append(f"{text(language, 'section.summary')}: {ux['summary']}")
    reason = ux.get("reason") if isinstance(ux.get("reason"), Mapping) else {}
    if reason.get("message"):
        lines.append(f"{text(language, 'section.reason')}: {reason['message']}")
    disclosures = ux.get("disclosures") if isinstance(ux.get("disclosures"), list) else []
    if disclosures:
        lines.append(f"{text(language, 'section.context')}:")
        for disclosure in disclosures:
            if isinstance(disclosure, Mapping) and disclosure.get("message"):
                lines.append(f"- {disclosure['message']}")
    if summary.get("major_blockers"):
        blocker_labels = {
            "setup": text(language, "section.setup"),
            "pending_proposals": text(language, "section.pending"),
            "conflict": text(language, "section.conflict"),
            "workspace": text(language, "section.workspace"),
        }
        lines.append(f"- {text(language, 'section.problem')}: {', '.join(blocker_labels.get(str(item), str(item)) for item in summary['major_blockers'])}")
    lines.append(f"{text(language, 'section.available_actions')}:")
    for index, action in enumerate(actions, start=1):
        suffix = text(language, "guided.confirmation_suffix") if action.get("requires_confirmation") else ""
        label = str(action.get("label") or action_label(language, str(action.get("id")), proposal_kind=action.get("proposal_kind")))
        lines.append(f"{index}. {label}{suffix}")
    selection = result.get("selection") if isinstance(result.get("selection"), Mapping) else {}
    if selection.get("status"):
        selection_labels = {
            "menu": text(language, "section.available_actions"),
            "confirmation_required": state_label(language, "needs_confirmation"),
            "completed": state_label(language, "completed"),
            "cancelled": text(language, "action.keep_pending"),
            "invalid": state_label(language, "blocked"),
            "blocked": state_label(language, "blocked"),
        }
        lines.append(f"{text(language, 'section.selection')}: {selection_labels.get(str(selection['status']), str(selection['status']))}")
    if result.get("error") and reason.get("message"):
        lines.insert(0, f"{text(language, 'section.problem')}: {reason['message']}")
    return "\n".join(lines)
