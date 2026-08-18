#!/usr/bin/env python3
"""Read the Vault and report what is inconsistent, without deciding what it means.

`doctor` never proposes, approves, or repairs career facts. `--fix` is limited to structural
repair the user cannot reasonably do by hand -- a missing directory, a stale pipeline path --
and every other finding is reported for the user to act on.
"""

from __future__ import annotations

import datetime as dt
import sys

from pathlib import Path
from typing import Any

_SHARED_ROOT = Path(__file__).resolve().parent.parent.parent / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))
import pipeline_store  # noqa: E402

from models import (  # noqa: E402
    CAREER_MODES,
    CAREER_STATUSES,
    CareerError,
    CONTEXT_KINDS,
    job_search_of,
    PROFILE_AXES,
    REQUIRED_CONTEXT_METADATA,
    TRACKS,
    VAULT_DIRECTORIES,
)
from projection import migrate_pipeline_file, pipeline_file  # noqa: E402
from routing import load_flow_reference  # noqa: E402
from skill_invocations import open_invocations  # noqa: E402
from validation import iso_date  # noqa: E402
from vault import CareerVault, index_vault_notes, today  # noqa: E402


def doctor(
    vault: CareerVault, fix: bool = False, workspace: str | Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    migrations: list[str] = []
    for directory in VAULT_DIRECTORIES:
        if not (vault.path / directory).is_dir():
            errors.append(f"missing directory: {directory}")
    for required in (vault.profile, vault.policy, vault.state_toml):
        if not required.exists():
            errors.append(f"missing required file: {required.relative_to(vault.path)}")
    if not errors:
        profile = vault.load_profile()
        track = profile.get("track")
        if track not in TRACKS:
            warnings.append("profile.track must be shinsotsu or chuto before chat can route")
        if profile.get("career_status", "active") not in CAREER_STATUSES:
            errors.append("profile.career_status must be active, confirmed, or onboarding")
        # A hand-edited value that is not in the vocabulary is an error, not a silent fallback:
        # `job_search_of()` would read it as `off`, and a user who typed `yes` deserves to be told
        # rather than quietly treated as not searching.
        for field, allowed in PROFILE_AXES.items():
            declared = profile.get(field)
            if declared is not None and declared not in allowed:
                errors.append(f"profile.{field} must be one of: {', '.join(sorted(allowed))}")
        career_mode = vault.load_state().get("career_mode")
        if career_mode is not None and career_mode not in CAREER_MODES:
            errors.append(f"state.career_mode must be one of: {', '.join(sorted(CAREER_MODES))}")
        if career_mode == "active_search" and job_search_of(profile) == "off":
            errors.append(
                "state.career_mode is active_search while profile.job_search is off; "
                "run set-job-search on to declare the search, or set-job-search off to clear it"
            )
        if track == "shinsotsu" and not isinstance(profile.get("graduation_year"), int):
            warnings.append("profile.graduation_year is required for shinsotsu")
        if not str(profile.get("target_role") or "").strip():
            warnings.append("profile.target_role is recommended for grounded company and document work")
        reference = load_flow_reference()
        due = str(reference.get("metadata", {}).get("review_due") or "")
        try:
            if due and dt.date.fromisoformat(due) <= today():
                warnings.append(f"career flow reference review is due: {due}")
        except ValueError:
            errors.append("career flow reference review_due must use YYYY-MM-DD")
        for note in index_vault_notes(vault.path, include_archives=True):
            if note["kind"] not in CONTEXT_KINDS:
                continue
            metadata = note
            if not all(key in metadata and metadata[key] not in (None, "", []) for key in REQUIRED_CONTEXT_METADATA):
                warnings.append(f"context note missing required metadata: {note['path']}")
            # AC-22: the same value must not be an error here and a silent pass in eligibility.
            # `iso_date` is now the single parser both paths call.
            try:
                expires = iso_date(metadata.get("expires_on"), "expires_on")
            except CareerError:
                errors.append(f"context note expires_on must be a real calendar date: {note['path']}")
                warnings.append(f"context note is ineligible until expires_on is fixed: {note['path']}")
                continue
            if expires and dt.date.fromisoformat(expires) < today():
                warnings.append(f"context note expired: {note['path']}")
    pipeline_path = pipeline_file(workspace)
    if pipeline_path.is_file():
        pipeline_data = pipeline_store.load(pipeline_path)
        if fix and "pipeline" in pipeline_data:
            try:
                if migrate_pipeline_file(pipeline_path):
                    migrations.append(f"migrated legacy pipeline shape: {pipeline_path}")
                    pipeline_data = pipeline_store.load(pipeline_path)
            except (CareerError, ImportError) as exc:
                errors.append(str(exc))
        if "pipeline" in pipeline_data:
            warnings.append(
                f"{pipeline_path} has a legacy nested 'pipeline' key — canonical shape is a flat "
                "top-level companies:/updated:, per _shared/schemas.yml"
            )
        if "companies" in pipeline_data and not isinstance(pipeline_data["companies"], list):
            errors.append(f"{pipeline_path}: companies must be a list")
    # A finding, not a failure: an open invocation means a Skill was opened and never reported,
    # which `doctor` can only detect, never prevent. It stays a warning, not an error, so this
    # never moves `ok` or the exit code.
    for invocation in open_invocations(vault):
        warnings.append(
            f"skill invocation {invocation['invocation_id']} for '{invocation['skill']}' "
            f"opened at {invocation['created_at']} and was never reported"
        )
    return {
        "mode": "doctor",
        "vault": str(vault.path),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "migrations": migrations,
        "safe_stop": bool(errors),
    }
