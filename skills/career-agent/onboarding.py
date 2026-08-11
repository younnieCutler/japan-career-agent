#!/usr/bin/env python3
"""First run and the user-intent axes.

This module owns the two fields nothing else may infer: `job_search` and `employment_status`.
They are set by an explicit command or by `setup`, never derived from a message, a stage, or
the presence of evidence.
"""

from __future__ import annotations

import sys

from pathlib import Path
from typing import Any, Mapping

from diagnostics import doctor
from lifecycle import vault_lock
from models import CareerError, PROFILE_AXES, TRACKS
from persistence import write_toml
from projection import clamp_career_mode
from vault import CareerVault, initialize_vault


DEFAULT_VAULT_PATH = Path.home() / ".career-agent-vault"


def _invocation() -> str:
    """The command name to put in front of a suggested next step.

    A clone is run as `python skills/career-agent/career_agent.py`; an installed wheel is run as
    `japan-career-agent`. Printing the clone form to someone who installed with uvx or npx names a
    file they do not have, which turns a next step into a dead end.
    """
    program = Path(sys.argv[0]).name if sys.argv and sys.argv[0] else ""
    if not program or program.endswith(".py"):
        return "python skills/career-agent/career_agent.py"
    return program


def set_profile_axis(home: CareerVault, field: str, value: str) -> dict[str, Any]:
    """The only write path for a user-intent axis.

    `job_search` and `employment_status` change for real -- employed to unemployed, a search
    started and then stopped -- so they cannot live behind first-run `setup` alone. They also must
    never move on their own: routing, an approved event, a JD review, and a match run all read
    them and none may write them. A dedicated command is what makes that structural instead of a
    rule somebody has to remember, and it keeps the reason a value changed visible.
    """
    allowed = PROFILE_AXES[field]
    normalized = str(value or "").strip().lower()
    if normalized not in allowed:
        raise CareerError(
            f"{field} must be one of: {', '.join(sorted(allowed))}",
            code="INVALID_INPUT",
        )
    # PERSIST-005: this reads the profile, writes it, then reads and may rewrite canonical state.
    # A concurrent approve doing its own read-modify-write would otherwise interleave and one of
    # the two would silently lose its change.
    with vault_lock(home):
        return _set_profile_axis_locked(home, field, normalized)


def _set_profile_axis_locked(home: CareerVault, field: str, normalized: str) -> dict[str, Any]:
    profile = home.load_profile()
    previous = profile.get(field)
    profile[field] = normalized
    write_toml(home.profile, profile)
    result = {
        "mode": field,
        "vault": str(home.path),
        field: normalized,
        "previous": previous,
        "changed": previous != normalized,
        "ok": True,
    }
    # Turning search off must not leave `active_search` standing in the projected state until the
    # next event happens to correct it. Nothing else is touched: the pipeline, its companies, and
    # the event ledger are the record of what already happened and stay exactly as they were.
    if field == "job_search":
        state = home.load_state()
        clamped = clamp_career_mode(state, normalized)
        if clamped != state:
            result["state_version"] = home.save_state(clamped)
            result["career_mode"] = clamped["career_mode"]
    return result


def setup(
    vault_path: Path,
    track: str | None = None,
    target_role: str | None = None,
    graduation_year: int | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """One-shot first run: init the vault if needed, fill the profile fields given, then doctor.

    Replaces the earlier manual sequence (find the runtime, export CAREER_AGENT_RUNTIME, init,
    hand-edit career-profile.toml, doctor) with a single call. Still refuses to guess a project
    directory — vault_path must be explicit or DEFAULT_VAULT_PATH, never Path.cwd().
    """
    home = CareerVault(vault_path)
    already_initialized = home.initialized()
    init_result = None if already_initialized else initialize_vault(home.path)
    profile = home.load_profile()
    if track:
        profile["track"] = track
    if target_role:
        profile["target_role"] = target_role
    if graduation_year:
        profile["graduation_year"] = graduation_year
    if language:
        profile["language"] = language
    elif "language" not in profile:
        profile["language"] = "ko"
    write_toml(home.profile, profile)
    diagnosis = doctor(home)
    needs_input: list[str] = []
    if profile.get("track") not in TRACKS:
        needs_input.append("track")
    elif profile.get("track") == "shinsotsu" and not isinstance(profile.get("graduation_year"), int):
        needs_input.append("graduation_year")
    if needs_input:
        quoted_vault = '"' + str(home.path).replace('"', '\\"') + '"'
        program = _invocation()
        if needs_input == ["graduation_year"]:
            next_command = (
                f"{program} setup "
                f"--vault {quoted_vault} --track shinsotsu --graduation-year <YYYY>"
            )
        else:
            next_command = (
                f"{program} setup "
                f"--vault {quoted_vault} --track <shinsotsu|chuto>"
            )
    elif not diagnosis["ok"]:
        next_command = "fill the remaining profile fields doctor flagged, then run setup again"
    else:
        next_command = "run --mode chat"
    return {
        "mode": "setup",
        "vault": str(home.path),
        "created": not already_initialized,
        "init": init_result,
        "profile": profile,
        "doctor": diagnosis,
        "ok": not needs_input and diagnosis["ok"],
        "needs_input": needs_input,
        "next": next_command,
    }


def complete_onboarding(home: CareerVault, result: Mapping[str, Any]) -> None:
    """Move `career_status` from `onboarding` to `active` once a turn reached a real domain task.

    `active` is a lifecycle statement ("the user picked a valid workflow"), not a claim that
    anything was verified: the proposal it came from is still a `draft` awaiting approval, and it
    stays `active` whether or not that approval ever happens. Approval governs career facts; this
    governs which questions the runtime still needs to ask.

    Nothing else in the profile is touched, and re-running it is a no-op, so a failure here costs a
    repeated onboarding question at worst and never a lost fact.
    """
    if not result.get("onboarding_completed"):
        return
    profile = home.load_profile()
    if str(profile.get("career_status") or "") != "onboarding":
        return
    profile["career_status"] = "active"
    write_toml(home.profile, profile)
