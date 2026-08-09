#!/usr/bin/env python3
"""Small, local-first career agent runtime.

The runtime deliberately stops at proposals for anything that could affect a
user or an installed skill. It stores facts as JSONL and keeps the current
state as a replaceable snapshot.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import uuid

from pathlib import Path
from typing import Any, Iterable, Mapping

_SHARED_ROOT = Path(__file__).resolve().parent.parent.parent / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))
import pipeline_store  # noqa: E402

from models import (  # noqa: E402
    CAREER_CONTEXT_FIELDS,
    CAREER_MODES,
    CAREER_STATUSES,
    CHUTO_STAGES,
    CONTEXT_KINDS,
    EMPLOYMENT_STATUSES,
    EVENT_STATUSES,
    EXTERNAL_USE_STATES,
    FACT_CATEGORIES,
    PROJECT_EVENT_TYPE,
    PROJECT_STATUSES,
    JOB_SEARCH_STATES,
    WORK_EVENT_TYPE,
    PIPELINE_STAGE,
    REFERENCE_BY_STAGE,
    REQUIRED_CONTEXT_METADATA,
    REQUIRED_EVENT_FIELDS,
    SHINSOTSU_STAGES,
    SKILL_BY_STAGE,
    TRACKS,
    TRUSTED_SOURCE_TYPES,
    UNTRUSTED_DATA_MARKER,
    VAULT_DIRECTORIES,
    CareerError,
    as_text,
    default_state,
    employment_status_of,
    job_search_of,
    normalized_state,
)
from validation import (  # noqa: E402
    DATE_VALUE,
    NUMERIC_CLAIM,
    iso_date,
    validate_career_context,
    validate_event,
    validate_work_event,
)
from routing import (  # noqa: E402
    FLOW_REFERENCE,
    ROUTING,
    ROUTING_REFERENCE,
    _WORD_BOUNDARY_TERMS,
    active_search_intent,
    explicit_stage_alias,
    flow_phase_for,
    maintenance_intent,
    opportunity_review_intent,
    review_closed_intent,
    transition_intent,
    flow_phase_ids,
    graduation_signal,
    infer_track,
    language_for,
    load_flow_reference,
    load_routing,
    matched_stage_alias,
    skill_context,
    stage_for,
    term_present,
)
from proposals import (  # noqa: E402
    make_project_event,
    stated_career_mode,
    approval_action_for,
    list_proposals,
    make_event,
    proposal_summary,
    propose_career_context,
    propose_fact,
    review_proposal,
    run_chat,
)
from lifecycle import (  # noqa: E402
    review_work_event,
    approve as _lifecycle_approve,
    count_consecutive_safe_stops,
    record_failed_attempt,
    read_approval_transaction,
    recover_pending,
    restore_state,
    state_version_is_persisted,
    vault_lock,
)
from projection import (  # noqa: E402
    clamp_career_mode,
    next_career_mode,
    project_timeline,
    projects_from_events,
    work_event_date,
    work_event_project_ids,
    _legacy_company_slug,
    apply_event_to_state,
    company_slug,
    migrate_pipeline_file,
    pipeline_file,
    upsert_pipeline_entry,
    workspace_path,
)
from persistence import (  # noqa: E402
    append_jsonl,
    atomic_write_text,
    read_json,
    read_jsonl,
    read_toml,
    toml_value,
    write_json,
    write_jsonl,
    write_toml,
)
from personal_timeline import (  # noqa: E402
    candidate_profile_values,
    document_states,
    historical_comparison,
    project,
    select_personal_context,
    timeline,
)
from private_store import (  # noqa: E402
    DOCUMENT_TYPES,
    PRIVATE_ENV,
    PrivateHome,
    documents as private_documents,
    import_document,
    initialize_private_home,
    private_doctor,
    resolve_private_home,
)
from vault import (  # noqa: E402
    HEADING,
    IGNORED_VAULT_DIRS,
    WIKILINK,
    CareerVault,
    context_eligible,
    index_vault_notes,
    initialize_vault,
    metadata_values,
    note_kind,
    parse_frontmatter,
    policy_template,
    profile_template,
    select_context,
    today,
    utc_now,
)
from ux import attach as project_ux, error_payload, render_human  # noqa: E402
from localization import normalize_language, text  # noqa: E402
from guided import (  # noqa: E402
    build_summary,
    derive_actions,
    guided_state,
    render_human as render_guided_human,
    resolve_choice,
)

_PROPOSAL_COMPATIBILITY_EXPORTS = (
    make_project_event,
    stated_career_mode,
    approval_action_for,
    list_proposals,
    make_event,
    proposal_summary,
    propose_career_context,
    propose_fact,
    run_chat,
)

_LIFECYCLE_COMPATIBILITY_EXPORTS = (
    count_consecutive_safe_stops,
    record_failed_attempt,
    state_version_is_persisted,
)

_PROJECTION_COMPATIBILITY_EXPORTS = (
    _legacy_company_slug,
    project_timeline,
    projects_from_events,
    work_event_date,
    work_event_project_ids,
    apply_event_to_state,
    clamp_career_mode,
    company_slug,
    migrate_pipeline_file,
    next_career_mode,
    pipeline_file,
    upsert_pipeline_entry,
    workspace_path,
)

_ROUTING_COMPATIBILITY_EXPORTS = (
    FLOW_REFERENCE,
    ROUTING,
    ROUTING_REFERENCE,
    _WORD_BOUNDARY_TERMS,
    active_search_intent,
    explicit_stage_alias,
    flow_phase_for,
    maintenance_intent,
    opportunity_review_intent,
    review_closed_intent,
    transition_intent,
    flow_phase_ids,
    graduation_signal,
    infer_track,
    language_for,
    load_routing,
    matched_stage_alias,
    skill_context,
    stage_for,
    term_present,
)

_PERSISTENCE_COMPATIBILITY_EXPORTS = (
    atomic_write_text,
    read_json,
    read_toml,
    toml_value,
    write_json,
)

_VAULT_COMPATIBILITY_EXPORTS = (
    HEADING,
    IGNORED_VAULT_DIRS,
    WIKILINK,
    context_eligible,
    metadata_values,
    note_kind,
    parse_frontmatter,
    policy_template,
    profile_template,
)

# Keep the historical ``runtime`` import surface while the owner modules are extracted in later
# PRs. The tuple is intentionally unused at runtime; it makes the compatibility contract explicit.
_MODEL_COMPATIBILITY_EXPORTS = (
    CAREER_CONTEXT_FIELDS,
    CAREER_MODES,
    CAREER_STATUSES,
    CHUTO_STAGES,
    CONTEXT_KINDS,
    EMPLOYMENT_STATUSES,
    EVENT_STATUSES,
    EXTERNAL_USE_STATES,
    JOB_SEARCH_STATES,
    PROJECT_EVENT_TYPE,
    PROJECT_STATUSES,
    WORK_EVENT_TYPE,
    PIPELINE_STAGE,
    REFERENCE_BY_STAGE,
    REQUIRED_CONTEXT_METADATA,
    REQUIRED_EVENT_FIELDS,
    SHINSOTSU_STAGES,
    SKILL_BY_STAGE,
    TRACKS,
    TRUSTED_SOURCE_TYPES,
    UNTRUSTED_DATA_MARKER,
    VAULT_DIRECTORIES,
    CareerError,
    as_text,
    default_state,
    employment_status_of,
    job_search_of,
    normalized_state,
    validate_career_context,
    validate_event,
    validate_work_event,
    DATE_VALUE,
    NUMERIC_CLAIM,
)


## Core vocabulary is owned by models.py; imported above for compatibility.
## Routing references are owned by routing.py and imported above for compatibility.


# Short ASCII tokens where a plain substring match false-positives inside unrelated English words
# (e.g. "es" — meant to catch the ES/entry-sheet abbreviation — also matches inside "research",
# "yes", "best"). Everything else, including intentional stems like "graduat", still matches as a
# substring.
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
    return {
        "mode": "doctor",
        "vault": str(vault.path),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "migrations": migrations,
        "safe_stop": bool(errors),
    }


DEFAULT_VAULT_PATH = Path.home() / ".career-agent-vault"


# The user-intent axes and their allowed values. Each one has exactly one write path -- the
# matching `set-*` command below -- so no amount of career data can move them.
PROFILE_AXES = {
    "job_search": JOB_SEARCH_STATES,
    "employment_status": EMPLOYMENT_STATUSES,
}


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
        if needs_input == ["graduation_year"]:
            next_command = (
                "python skills/career-agent/career_agent.py setup "
                f"--vault {quoted_vault} --track shinsotsu --graduation-year <YYYY>"
            )
        else:
            next_command = (
                "python skills/career-agent/career_agent.py setup "
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


def decode_utf8(payload: bytes, *, source: str) -> str:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CareerError(f"{source} must be valid UTF-8") from exc


def read_stdin_utf8() -> str:
    stream = getattr(sys.stdin, "buffer", None)
    raw = stream.read() if stream is not None else sys.stdin.read()
    if isinstance(raw, bytes):
        return decode_utf8(raw, source="stdin")
    return raw


def load_posting_records(source: str | None) -> list[dict[str, Any]]:
    if source:
        path = Path(source).expanduser()
        data = json.loads(decode_utf8(path.read_bytes(), source=str(path)))
    else:
        raw = read_stdin_utf8().strip()
        if not raw:
            return []
        data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get("postings", [data])
    if not isinstance(data, list):
        raise CareerError("discover input must be a JSON object or array")
    return [item for item in data if isinstance(item, dict)]


def posting_key(posting: dict[str, Any]) -> str:
    url = str(posting.get("url") or posting.get("source_url") or "").strip()
    source_ref = str(posting.get("source_ref") or "").strip()
    company = str(posting.get("company") or posting.get("company_name") or "").strip().lower()
    role = str(posting.get("role") or posting.get("job_title") or "").strip().lower()
    raw = url or source_ref or f"{company}|{role}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def normalize_posting(posting: dict[str, Any]) -> dict[str, Any]:
    url = str(posting.get("url") or posting.get("source_url") or "").strip()
    provenance = posting.get("provenance") or "observed"
    if provenance not in {"observed", "job_posting", "synthetic", "unknown"}:
        raise CareerError("posting provenance must be observed, job_posting, synthetic, or unknown")
    source_ref = str(posting.get("source_ref") or url).strip()
    if provenance == "synthetic":
        if url:
            raise CareerError("synthetic postings must omit url; use source_ref synthetic://...")
        if not source_ref.startswith("synthetic://"):
            raise CareerError("synthetic postings require a synthetic:// source_ref")
    elif not url.startswith(("https://", "http://")):
        raise CareerError("public postings require an original http(s) URL")
    return {
        "company": str(posting.get("company") or posting.get("company_name") or "不明").strip(),
        "role": str(posting.get("role") or posting.get("job_title") or "不明").strip(),
        "graduation_year": posting.get("graduation_year"),
        "target": posting.get("target") or posting.get("audience"),
        "deadline": posting.get("deadline"),
        "original_url": url or None,
        "checked_at": posting.get("checked_at") or utc_now(),
        "dedupe_key": posting_key(posting),
        "status": "candidate",
        "source": "synthetic_fixture" if provenance == "synthetic" else "public_search_input",
        "source_ref": source_ref,
        "provenance": provenance,
    }


def choose_actions(home: CareerVault) -> list[dict[str, Any]]:
    events = read_jsonl(home.events)
    state = home.load_state()
    profile = home.load_profile()
    profile_language = normalize_language(profile.get("language"))
    actions: list[dict[str, Any]] = []
    for deadline in state.get("deadlines", []):
        if deadline.get("status") != "open":
            continue
        try:
            days = (dt.date.fromisoformat(deadline["date"]) - today()).days
        except (KeyError, ValueError):
            continue
        if days <= 7:
            actions.append({"text": text(profile_language, "heartbeat.deadline_action", key=deadline.get("title", "deadline")), "event_id": deadline.get("event_id"), "stage": state.get("stage"), "flow_phase": state.get("flow_phase"), "estimated_minutes": 15, "deadline": deadline["date"], "requires_confirmation": True, "reason": "deadline"})
    seen_dates = {item.get("deadline") for item in actions}
    for key, value in profile.items():
        if not isinstance(value, str) or not DATE_VALUE.match(value) or value in seen_dates:
            continue
        try:
            days = (dt.date.fromisoformat(value[:10]) - today()).days
        except ValueError:
            continue
        if 0 <= days <= 7:
            actions.append({"text": text(profile_language, "heartbeat.deadline_action", key=key), "event_id": None, "stage": state.get("stage"), "flow_phase": state.get("flow_phase"), "estimated_minutes": 15, "deadline": value, "requires_confirmation": True, "reason": "profile_deadline"})
    for event in reversed(events):
        if event.get("status") == "confirmed" and event.get("next_action"):
            action = {"text": event["next_action"], "event_id": event["id"], "stage": event["stage"], "flow_phase": event.get("flow_phase"), "estimated_minutes": 30, "deadline": event.get("deadline"), "requires_confirmation": True, "reason": "latest confirmed event"}
            if action["event_id"] not in {item.get("event_id") for item in actions}:
                actions.append(action)
    return actions[:3]


def run_heartbeat(home: CareerVault) -> dict[str, Any]:
    state = home.load_state()
    actions = choose_actions(home)
    report = {
        "id": f"heartbeat-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "track": state.get("track"),
        "stage": state.get("stage"),
        "flow_phase": state.get("flow_phase"),
        "actions": actions,
        "limit": 3,
        "requires_confirmation": True,
    }
    with vault_lock(home):  # PERSIST-005
        home.add_proposal({"id": report["id"], "kind": "heartbeat", "status": "pending", "created_at": report["created_at"], "report": report})
        home.append_trajectory({"id": f"traj-{uuid.uuid4().hex[:12]}", "created_at": utc_now(), "mode": "heartbeat", "observe": state, "plan": {"goal": "select at most three grounded actions"}, "act": report, "verify": {"action_count": len(actions), "max": 3}, "correct": {"retry_count": 0}, "persist": {"proposal_id": report["id"]}})
    return report


def run_discover(home: CareerVault, source: str | None) -> dict[str, Any]:
    incoming_raw = load_posting_records(source)
    incoming = []
    invalid: list[str] = []
    for item in incoming_raw:
        try:
            incoming.append(normalize_posting(item))
        except CareerError as exc:
            invalid.append(str(exc))
    if incoming_raw and not incoming:
        # every item in the batch was corrupted - nothing to self-correct, escalate as before.
        raise CareerError("discover postings require an original http(s) URL or a synthetic:// source_ref")
    with vault_lock(home):  # PERSIST-005: dedupe-then-append must not race a concurrent discover
        existing = read_jsonl(home.postings)
        known = {item.get("dedupe_key") for item in existing}
        added = []
        for item in incoming:
            if item["dedupe_key"] in known:
                continue
            known.add(item["dedupe_key"])
            added.append(item)
        for item in added:
            append_jsonl(home.postings, item)
        result = {"mode": "discover", "found": len(incoming), "added": len(added), "duplicates": len(incoming) - len(added), "dropped": len(invalid), "postings": added, "saved": str(home.postings), "auto_apply": False}
        home.add_proposal({"id": f"discover-{uuid.uuid4().hex[:12]}", "kind": "posting_candidates", "status": "pending", "created_at": utc_now(), "result": result})
        home.append_trajectory({"id": f"traj-{uuid.uuid4().hex[:12]}", "created_at": utc_now(), "mode": "discover", "observe": {"source": source, "count": len(incoming_raw)}, "plan": {"goal": "normalize public posting candidates and deduplicate"}, "act": {"added": len(added)}, "verify": {"original_urls_preserved": True, "invalid_count": len(invalid)}, "correct": {"action": "dropped_invalid_postings" if invalid else "none", "dropped": len(invalid), "retry_count": 0}, "persist": {"postings": str(home.postings)}})
    return result


def run_index(home: CareerVault, *, include_archives: bool = False) -> dict[str, Any]:
    notes = index_vault_notes(home.path, include_archives=include_archives)
    with vault_lock(home):  # PERSIST-005: full-rewrite writer, same lock as every other canonical write
        write_jsonl(home.vault_index, notes)
    result = {
        "mode": "index",
        "vault": str(home.path),
        "indexed": len(notes),
        "saved": str(home.vault_index),
        "read_only_source": True,
        "archives_included": include_archives,
    }
    home.append_trajectory(
        {
            "id": f"traj-{uuid.uuid4().hex[:12]}",
            "created_at": utc_now(),
            "mode": "vault_index",
            "observe": {"vault": str(home.path)},
            "plan": {"goal": "index selected note metadata without importing note bodies"},
            "act": {"indexed": len(notes)},
            "verify": {"source_unchanged": True, "note_bodies_persisted": False},
            "correct": {"retry_count": 0},
            "persist": {"index": str(home.vault_index)},
        }
    )
    return result


def latest_career_context(home: CareerVault) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    latest: dict[str, Any] | None = None
    for event in read_jsonl(home.events):
        if event.get("status") != "confirmed" or event.get("type") != "career_context":
            continue
        validate_event(event)
        validate_career_context(event.get("career_context"))
        latest = event
    if latest is None:
        return None, None
    return latest["career_context"], latest


def private_records(vault: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Document records for a Vault, or an explained absence.

    A private store is optional (section 25), so its absence or misconfiguration is a state to
    report, not a corruption to stop on. It must not vanish quietly either, hence the reason
    travelling in the payload rather than being swallowed.
    """
    try:
        store = PrivateHome(resolve_private_home(None, vault))
    except CareerError as exc:
        return [], str(exc).splitlines()[0]
    if not store.initialized():
        return [], None
    return private_documents(store), None


def run_context(
    home: CareerVault, requested_track: str | None, requested_stage: str | None, as_of: str,
) -> dict[str, Any]:
    """Shared, metadata-only context for other career skills and agent frontends."""
    profile = home.load_profile()
    state = home.load_state()
    track = requested_track or state.get("track") or profile.get("track")
    if track not in TRACKS:
        raise CareerError("shared context requires profile.track or --track")
    stage = requested_stage or state.get("stage")
    if stage is not None and stage not in SHINSOTSU_STAGES + CHUTO_STAGES:
        raise CareerError("shared context stage is not recognized")
    career_context, career_event = latest_career_context(home)
    profile_keys = ("track", "career_status", "target_role", "start_date", "graduation_year", "language", "flow_phase")
    return {
        "mode": "context",
        "vault": str(home.path),
        "as_of": as_of,
        "profile": {key: profile[key] for key in profile_keys if key in profile and profile[key] not in (None, "")},
        "state": state,
        "context": select_context(home.path, track, stage, as_of) if stage else [],
        "context_trust": {"data": UNTRUSTED_DATA_MARKER, "instruction_authority": "none"},
        "career_context": career_context,
        "career_context_confirmed": career_context is not None,
        "career_context_event_id": career_event.get("id") if career_event else None,
        # Section 12.1. Current, stage-relevant, capped, and confirmed-only -- never the whole
        # `project()` output, which returns every category and key. Documents are not here at all:
        # neither the relevance map nor the cap applies to them, so `private-list` and
        # `personal-context --historical` are the explicit paths.
        # A corrupt fact row raises rather than degrading this block, matching what
        # `latest_career_context` above already does for a corrupt career_context row: corrupt
        # canonical data stops the command. That is a different case from a private root that is
        # merely absent or misconfigured, which `private_records` reports and continues past.
        "personal_context": select_personal_context(read_jsonl(home.events), stage, as_of),
        "read_only": True,
        "note_bodies_included": False,
    }


def _pipeline_writer_for(home: CareerVault, workspace: str | Path | None = None):
    def pipeline_writer(event: dict[str, Any]) -> Path | None:
        transaction = read_approval_transaction(home)
        transaction_workspace = transaction.get("workspace") if transaction else None
        target_workspace = transaction_workspace or workspace
        return upsert_pipeline_entry(
            event,
            path=pipeline_file(target_workspace),
            workspace=target_workspace,
        )

    return pipeline_writer


def work_events(
    home: CareerVault, *, confirmed_only: bool = False, as_of: str | None = None,
) -> dict[str, Any]:
    """Read work events out of the ledger. This is the contract downstream skills use.

    Matching a JD against career evidence needs the evidence, and the alternative to a query is
    every skill parsing `events.jsonl` for itself -- which is how "only confirmed evidence counts"
    stops being one rule and becomes several that drift. Reading is all this does: nothing here
    writes, and the caller receives a copy.

    `as_of` filters by `occurred_at`, inclusive. Note what that is and is not: `occurred_at` is
    when the note was *captured*, not when the work happened. Someone writing up a project from
    last June today gets an event dated today, so this bounds the ledger reproducibly but is not
    yet a recency signal about the work itself. A `work_date` on the payload is the fix and is not
    in this change.

    The boundary is a UTC date because `occurred_at` is a UTC instant; a local calendar boundary
    would compare two different things and silently drop an event recorded minutes ago.
    """
    rows = [row for row in read_jsonl(home.events) if row.get("type") == WORK_EVENT_TYPE]
    if confirmed_only:
        # Confirmed means confirmed: a draft is a proposal the user has not verified, and a
        # superseded row is history that a later record replaced. Neither may be quoted as current
        # evidence in a document that goes to someone else.
        rows = [row for row in rows if row.get("status") == "confirmed"]
    if as_of:
        # `occurred_at` is stored in UTC, as everywhere else on the ledger.
        boundary = iso_date(as_of, "--as-of")
        rows = [row for row in rows if str(row.get("occurred_at") or "")[:10] <= boundary]
    return {
        "mode": "work-events",
        "vault": str(home.path),
        "as_of": as_of,
        "confirmed_only": confirmed_only,
        "count": len(rows),
        "work_events": rows,
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "ok": True,
    }


def add_project(
    home: CareerVault, title: str, *, project_id: str | None = None, **fields: Any,
) -> dict[str, Any]:
    """Propose a project, or an update to one that already exists.

    Goes through the same proposal the rest of the ledger uses, so the confirmation the UX already
    asks for ("연결할까요?") is the approval, not an extra step on top of it.
    """
    known = projects_from_events(read_jsonl(home.events))
    if project_id is not None and project_id not in known:
        raise CareerError(f"unknown project id: {project_id}", code="PROJECT_NOT_FOUND")
    event = make_project_event(title, project_id, fields=fields)
    proposal = {
        "id": f"proposal-{uuid.uuid4().hex[:12]}",
        "kind": "event",
        "status": "pending",
        "created_at": utc_now(),
        "next_action": f"approve {event['project']['id']} after checking the title and role",
        "event": event,
    }
    with vault_lock(home):
        home.add_proposal(proposal)
    return {
        "mode": "add-project",
        "vault": str(home.path),
        "project": event["project"],
        "proposal": {"id": proposal["id"], "status": proposal["status"]},
        "updates_existing": project_id is not None,
        "ok": True,
    }


def list_projects(home: CareerVault, *, status: str | None = None) -> dict[str, Any]:
    """Every confirmed project with how much evidence hangs on it."""
    events = read_jsonl(home.events)
    projects = projects_from_events(events)
    counts: dict[str, int] = {}
    for event in events:
        if event.get("type") != WORK_EVENT_TYPE or event.get("status") != "confirmed":
            continue
        for project_id in work_event_project_ids(event):
            counts[project_id] = counts.get(project_id, 0) + 1
    rows = [
        {**record, "confirmed_work_events": counts.get(project_id, 0)}
        for project_id, record in projects.items()
        if status is None or record.get("status") == status
    ]
    rows.sort(key=lambda row: (row.get("status") != "active", str(row.get("title") or "")))
    return {
        "mode": "projects",
        "vault": str(home.path),
        "count": len(rows),
        "projects": rows,
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "ok": True,
    }


def show_project_timeline(home: CareerVault, project_id: str) -> dict[str, Any]:
    """One project's confirmed work events in time order, as references to the ledger."""
    events = read_jsonl(home.events)
    projects = projects_from_events(events)
    if project_id not in projects:
        raise CareerError(f"unknown project id: {project_id}", code="PROJECT_NOT_FOUND")
    entries = project_timeline(events, project_id)
    return {
        "mode": "project-timeline",
        "vault": str(home.path),
        "project": projects[project_id],
        "count": len(entries),
        "timeline": entries,
        # Every row points at a ledger event. Nothing here is a second copy of the history.
        "entries_are_references": True,
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "ok": True,
    }


def link_work_event(
    home: CareerVault,
    proposal_id: str,
    *,
    primary: str | None = None,
    related: list[str] | None = None,
    clear: bool = False,
) -> dict[str, Any]:
    """Point a pending work event at projects, or at none.

    A link is a reference. One canonical work event is pointed at by every project it belongs to,
    so a note spanning three projects is stored once and appears in three timelines -- copying it
    per project would create three facts where the user lived one.

    `clear` records "no project / general work", which is a real answer. Capture is never blocked
    on choosing a project.
    """
    known = set(projects_from_events(read_jsonl(home.events)))
    unknown = sorted({item for item in [primary, *(related or [])] if item and item not in known})
    if unknown:
        raise CareerError(f"unknown project id: {', '.join(unknown)}", code="PROJECT_NOT_FOUND")
    if clear:
        patch: dict[str, Any] = {"primary_project_id": None, "related_project_ids": []}
    else:
        patch = {}
        if primary is not None:
            patch["primary_project_id"] = primary
        if related is not None:
            patch["related_project_ids"] = [item for item in related if item != primary]
    result = review_work_event(home, proposal_id, patch)
    result["mode"] = "link-work-event"
    return result


def weekly_review(home: CareerVault, *, since: str | None = None, as_of: str | None = None) -> dict[str, Any]:
    """This period's work evidence, grouped by project, with what is worth asking about.

    Not a retrospective form. It shows what already accumulated and names the gaps that actually
    change how the record reads later, in the order they matter: what the user personally did,
    what came of it, where a number came from, what changed for the team, what they learned.

    A record with gaps is a good record. These are questions worth asking, never fields to force.
    """
    boundary = iso_date(as_of, "--as-of") or utc_now()[:10]
    start = iso_date(since, "--since") or (
        dt.date.fromisoformat(boundary) - dt.timedelta(days=7)
    ).isoformat()
    events = read_jsonl(home.events)
    projects = projects_from_events(events)
    # Windowed on capture time, not on when the work happened. The point of this view is "what did
    # I write down and not finish structuring", so a note captured today about last June belongs
    # here — it is exactly the one still needing a contribution and a result. `work_date` is shown
    # per row and is what recency uses downstream.
    recent = [
        event
        for event in events
        if event.get("type") == WORK_EVENT_TYPE
        and start <= str(event.get("occurred_at") or "")[:10] <= boundary
    ]
    groups: dict[str, dict[str, Any]] = {}
    for event in recent:
        payload = event.get("work_event") or {}
        ids = work_event_project_ids(event) or [""]
        gaps = [name for name, ask in (
            ("individual_contribution", not payload.get("individual_contribution")),
            ("result", not payload.get("individual_contribution") and not payload.get("team_result")),
            ("metrics_evidence", bool(payload.get("metrics")) and not event.get("evidence")),
            ("improvements", not payload.get("improvements")),
            ("learning", not payload.get("learning")),
        ) if ask]
        for project_id in ids:
            group = groups.setdefault(
                project_id,
                {
                    "project_id": project_id or None,
                    "title": projects.get(project_id, {}).get("title") if project_id else None,
                    "events": [],
                },
            )
            group["events"].append({
                "event_id": event["id"],
                "captured_on": str(event.get("occurred_at") or "")[:10],
                "work_date": payload.get("work_date"),
                "title": event.get("title"),
                "status": event.get("status"),
                "gaps": gaps,
            })
    ordered = sorted(groups.values(), key=lambda g: (g["project_id"] is None, str(g["title"] or "")))
    return {
        "mode": "weekly-review",
        "vault": str(home.path),
        "since": start,
        "as_of": boundary,
        "event_count": len(recent),
        "groups": ordered,
        # Ranked by what changes how the record reads later, not by field order. Ask at most a few.
        "ask_first": ["individual_contribution", "result", "metrics_evidence", "improvements", "learning"],
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "ok": True,
    }


def _state_projector_for(home: CareerVault):
    """Bind the user's declared job-search intent to the state projector.

    The profile is the only place that answer lives, and the projector must not go read it: that
    would make a pure (state, event) function depend on a file. Reading it once here keeps the
    single write path for `job_search` intact while still letting the projector refuse to promote
    anyone into `active_search` they never asked for.
    """
    job_search = job_search_of(home.load_profile())

    def state_projector(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        return apply_event_to_state(state, event, job_search=job_search)

    return state_projector


def approve(
    home: CareerVault,
    proposal_id: str,
    evidence: list[str] | None = None,
    deadline: str | None = None,
    company: str | None = None,
    compensation: float | None = None,
    currency: str | None = None,
    workspace: str | Path | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    """Compatibility facade injecting the runtime-owned projection callbacks."""
    return _lifecycle_approve(
        home,
        proposal_id,
        evidence=evidence,
        deadline=deadline,
        company=company,
        compensation=compensation,
        currency=currency,
        workspace=workspace,
        next_action=next_action,
        pipeline_writer=_pipeline_writer_for(home, workspace),
        state_projector=_state_projector_for(home),
    )


def recover_approval(home: CareerVault, workspace: str | Path | None = None) -> dict[str, Any] | None:
    """Replay an interrupted approval using the workspace recorded in its journal."""
    return recover_pending(
        home,
        pipeline_writer=_pipeline_writer_for(home, workspace),
        state_projector=_state_projector_for(home),
    )


def _requires_approval_recovery(args: argparse.Namespace) -> bool:
    """Only gate commands that can write; read-only inspection must remain available."""
    if args.command in {
        "setup", "guided", "approve", "restore-state", "index",
        "propose-fact", "propose-context",
        "set-job-search", "set-employment-status", "review-work-event",
        "add-project", "link-work-event",
    }:
        return True
    if args.command == "doctor":
        return bool(args.fix)
    return args.command == "run"


def workspace_summary(workspace: str | Path | None = None) -> dict[str, Any]:
    """Read a safe workspace projection without creating a missing workspace or pipeline."""
    resolved = workspace_path(workspace)
    explicit = workspace is not None
    if explicit and not resolved.is_dir():
        raise CareerError(
            f"workspace not found: {resolved}",
            code="WORKSPACE_NOT_FOUND",
            details={"workspace": str(resolved)},
        )
    pipeline = pipeline_file(workspace)
    data = pipeline_store.load(pipeline)
    companies = data.get("companies") if isinstance(data, dict) else []
    if not isinstance(companies, list):
        companies = []
    return {
        "path": str(resolved),
        "exists": resolved.is_dir(),
        "pipeline": str(pipeline),
        "pipeline_exists": pipeline.is_file(),
        "company_count": len(companies),
        "updated": data.get("updated") if isinstance(data, dict) else None,
    }


def status(home: CareerVault, workspace: str | Path | None = None) -> dict[str, Any]:
    state = home.load_state()
    profile = home.load_profile()
    pending_rows = [row for row in read_jsonl(home.proposals) if row.get("status") == "pending"]
    pending_kind = (
        str(pending_rows[0].get("kind") or "") or None
        if len(pending_rows) == 1
        else None
    )
    return {
        "vault": str(home.path),
        "profile": {
            "track": profile.get("track"),
            "career_status": profile.get("career_status", "active"),
            "target_role": profile.get("target_role"),
            # The two user-declared axes, always shown. Reading them here says what the user
            # declared; it never changes it, and `career_mode` in `state` below is projected
            # separately so a disagreement between the two stays visible instead of averaged away.
            "employment_status": employment_status_of(profile),
            "job_search": job_search_of(profile),
        },
        "state": state,
        "work_event_count": len(work_events(home, confirmed_only=True)["work_events"]),
        "event_count": len(read_jsonl(home.events)),
        "pending_proposals": len(pending_rows),
        "pending_kind": pending_kind,
        "posting_count": len(read_jsonl(home.postings)),
        "workspace": workspace_summary(workspace),
    }


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local-first Japan career agent runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_vault_argument(command: argparse.ArgumentParser) -> None:
        command.add_argument("--vault", default=os.environ.get("CAREER_VAULT"), help="initialized Career Vault; falls back to CAREER_VAULT")

    def add_workspace_argument(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--workspace", default=os.environ.get("CAREER_WORKSPACE"),
            help="job-search workspace containing data/pipeline.yml; defaults to the current directory",
        )

    def add_as_of_argument(command: argparse.ArgumentParser) -> None:
        # AC-21: the ONLY place a wall clock touches the temporal path. Everything downstream takes
        # `as_of` as a required parameter, so the same history and the same date always project the
        # same way, and a test can change the date without changing the system clock.
        command.add_argument(
            "--as-of", default=today().isoformat(), metavar="YYYY-MM-DD",
            help="project as of this date instead of today; the projection never reads the clock",
        )

    def add_output_format(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--format",
            dest="output_format",
            choices=("json", "human"),
            default="json",
            help="output format; JSON remains the default machine-readable contract",
        )

    init_parser = subparsers.add_parser("init")
    add_vault_argument(init_parser)
    add_output_format(init_parser)
    setup_parser = subparsers.add_parser(
        "setup",
        help="one-shot first run: init the vault (default ~/.career-agent-vault) + profile fields + doctor",
    )
    setup_parser.add_argument("--vault", default=os.environ.get("CAREER_VAULT"), help="defaults to CAREER_VAULT, then ~/.career-agent-vault")
    setup_parser.add_argument("--track", choices=sorted(TRACKS))
    setup_parser.add_argument("--target-role")
    setup_parser.add_argument("--graduation-year", type=int)
    setup_parser.add_argument("--language", default=None)
    add_output_format(setup_parser)
    for command, field in (("set-job-search", "job_search"), ("set-employment-status", "employment_status")):
        axis_parser = subparsers.add_parser(
            command,
            help=f"set profile.{field}; this is the only command that may change it",
        )
        add_vault_argument(axis_parser)
        axis_parser.add_argument("value", choices=sorted(PROFILE_AXES[field]))
        add_output_format(axis_parser)
    guided_parser = subparsers.add_parser(
        "guided",
        help="show a canonical-state guided menu; writes require an explicit choice and confirmation",
    )
    add_vault_argument(guided_parser)
    add_workspace_argument(guided_parser)
    add_as_of_argument(guided_parser)
    guided_parser.add_argument(
        "--choice",
        action="append",
        default=[],
        help="deterministic action ID or one-based menu number; repeat for scripted confirmation",
    )
    guided_parser.add_argument(
        "--confirm",
        action="store_true",
        help="confirm a write-capable guided action after reviewing its summary",
    )
    guided_parser.add_argument("--message", help="user-described task for the start_task action")
    guided_parser.add_argument("--proposal-id", help="pending proposal to approve when more than one is available")
    guided_parser.add_argument("--evidence", action="append", help="evidence for approval; repeat for multiple sources")
    guided_parser.add_argument("--deadline", help="confirmed event deadline in YYYY-MM-DD")
    guided_parser.add_argument("--company", help="company name for an approved event")
    guided_parser.add_argument("--compensation", type=float, help="compensation amount for an approved event")
    guided_parser.add_argument("--currency", help="currency for --compensation, e.g. JPY")
    guided_parser.add_argument("--next-action", help="actual action that remains after approval")
    guided_parser.add_argument("--version", help="saved state version for the restore_state action")
    guided_parser.add_argument("--track", choices=sorted(TRACKS), help="track for guided setup")
    guided_parser.add_argument("--target-role", help="target role for guided setup")
    guided_parser.add_argument("--graduation-year", type=int, help="graduation year for guided shinsotsu setup")
    guided_parser.add_argument("--language", default=None, help="profile language for guided setup")
    add_output_format(guided_parser)
    doctor_parser = subparsers.add_parser("doctor")
    add_vault_argument(doctor_parser)
    add_workspace_argument(doctor_parser)
    doctor_parser.add_argument("--fix", action="store_true", help="migrate the legacy nested data/pipeline.yml shape")
    add_output_format(doctor_parser)
    run = subparsers.add_parser("run")
    add_vault_argument(run)
    run.add_argument("--mode", choices=("chat", "heartbeat", "discover"), required=True)
    run.add_argument("--message")
    run.add_argument("--track", choices=sorted(TRACKS))
    run.add_argument("--source", help="JSON file for discover; stdin is used when omitted")
    add_as_of_argument(run)
    add_output_format(run)
    work_events_parser = subparsers.add_parser(
        "work-events",
        help="read work events from the ledger; the query downstream skills use for evidence",
    )
    add_vault_argument(work_events_parser)
    work_events_parser.add_argument(
        "--confirmed",
        dest="confirmed_only",
        action="store_true",
        help="only user-confirmed events; drafts are proposals, not evidence",
    )
    # This boundary is UTC, not the local date `add_as_of_argument` uses. `occurred_at` is stored
    # in UTC, and comparing its day against a local calendar day drops an event the user just
    # recorded: west of UTC an evening capture lands on tomorrow's UTC day, which a local `today`
    # boundary then filters out. The fact projection keeps the local default because it compares
    # against plain `YYYY-MM-DD` fact dates that carry no timezone at all.
    work_events_parser.add_argument(
        "--as-of", default=utc_now()[:10], metavar="YYYY-MM-DD",
        help="include events captured on or before this UTC date; defaults to today in UTC. This "
             "is capture time, not when the work happened",
    )
    add_output_format(work_events_parser)
    add_project_parser = subparsers.add_parser(
        "add-project", help="propose a project, or an update to one that already exists",
    )
    add_vault_argument(add_project_parser)
    add_project_parser.add_argument("title")
    add_project_parser.add_argument("--project-id", help="update this project instead of adding one")
    add_project_parser.add_argument("--role")
    add_project_parser.add_argument("--scope")
    add_project_parser.add_argument("--summary")
    add_project_parser.add_argument("--status", choices=sorted(PROJECT_STATUSES))
    add_project_parser.add_argument("--from", dest="period_from", metavar="YYYY-MM[-DD]")
    add_project_parser.add_argument("--to", dest="period_to", metavar="YYYY-MM[-DD]")
    add_output_format(add_project_parser)
    weekly_parser = subparsers.add_parser(
        "weekly-review", help="this period's work evidence grouped by project, with the gaps worth asking about",
    )
    add_vault_argument(weekly_parser)
    weekly_parser.add_argument("--since", metavar="YYYY-MM-DD", help="defaults to seven days before --as-of")
    weekly_parser.add_argument("--as-of", metavar="YYYY-MM-DD", help="defaults to today in UTC")
    add_output_format(weekly_parser)
    projects_parser = subparsers.add_parser(
        "projects", help="list confirmed projects and how much evidence hangs on each",
    )
    add_vault_argument(projects_parser)
    projects_parser.add_argument("--status", choices=sorted(PROJECT_STATUSES))
    add_output_format(projects_parser)
    timeline_parser = subparsers.add_parser(
        "project-timeline", help="one project's confirmed work events, as ledger references",
    )
    add_vault_argument(timeline_parser)
    timeline_parser.add_argument("project_id")
    add_output_format(timeline_parser)
    link_parser = subparsers.add_parser(
        "link-work-event", help="point a pending work event at projects, or at none",
    )
    add_vault_argument(link_parser)
    link_parser.add_argument("proposal_id")
    link_parser.add_argument("--project", dest="primary", help="the project this work mainly belongs to")
    link_parser.add_argument(
        "--related", action="append", default=None,
        help="another project this work also belongs to; repeat for several",
    )
    link_parser.add_argument(
        "--none", dest="clear", action="store_true",
        help="record general work that belongs to no project",
    )
    add_output_format(link_parser)
    review_parser = subparsers.add_parser(
        "review-work-event",
        help="fill the structured fields of a pending work event before it is confirmed",
    )
    add_vault_argument(review_parser)
    review_parser.add_argument("proposal_id")
    review_parser.add_argument(
        "--json", dest="work_event_json", required=True,
        help="work_event fields as a JSON object; '-' reads stdin",
    )
    review_parser.add_argument(
        "--replace", action="store_true",
        help="replace the payload instead of merging, e.g. to clear a field back to Unknown",
    )
    add_output_format(review_parser)
    status_parser = subparsers.add_parser("status")
    add_vault_argument(status_parser)
    add_workspace_argument(status_parser)
    add_output_format(status_parser)
    proposals_parser = subparsers.add_parser(
        "proposals",
        help="list proposal metadata without exposing proposal bodies",
    )
    add_vault_argument(proposals_parser)
    proposals_parser.add_argument("--all", dest="include_all", action="store_true", help="include approved and superseded proposals")
    proposals_parser.add_argument("--limit", type=int, help="return at most N proposals (N must be positive)")
    proposals_parser.add_argument("--id", dest="proposal_id", help="review one proposal body explicitly")
    add_output_format(proposals_parser)
    approve_parser = subparsers.add_parser("approve")
    add_vault_argument(approve_parser)
    add_workspace_argument(approve_parser)
    approve_parser.add_argument("proposal_id")
    approve_parser.add_argument("--evidence", action="append", help="evidence for an event; repeat for multiple sources")
    approve_parser.add_argument("--deadline", help="confirmed event deadline in YYYY-MM-DD")
    approve_parser.add_argument("--company", help="company name for an offer/application event")
    approve_parser.add_argument("--compensation", type=float, help="compensation amount for an offer/application event")
    approve_parser.add_argument("--currency", help="currency for --compensation, e.g. JPY")
    approve_parser.add_argument("--next-action", help="actual action that remains after approval")
    add_output_format(approve_parser)
    restore_parser = subparsers.add_parser(
        "restore-state",
        help="replace the current state with a saved snapshot; the append-only ledger is kept",
    )
    add_vault_argument(restore_parser)
    restore_parser.add_argument("version")
    add_output_format(restore_parser)
    index_parser = subparsers.add_parser("index")
    add_vault_argument(index_parser)
    index_parser.add_argument("--include-archives", action="store_true", help="include 06-archives in the index")
    add_output_format(index_parser)
    context_parser = subparsers.add_parser("context")
    add_vault_argument(context_parser)
    context_parser.add_argument("--track", choices=sorted(TRACKS), help="override the profile/state track")
    context_parser.add_argument("--stage", help="select verified notes for this exact stage")
    add_as_of_argument(context_parser)
    add_output_format(context_parser)
    profile_parser = subparsers.add_parser(
        "personal-profile",
        help="current personal-profile projection; Unknown and Conflict are explicit states",
    )
    add_vault_argument(profile_parser)
    add_as_of_argument(profile_parser)
    add_output_format(profile_parser)
    timeline_parser = subparsers.add_parser(
        "personal-timeline",
        help="full labelled history for one fact key, including superseded records",
    )
    add_vault_argument(timeline_parser)
    timeline_parser.add_argument("--category", required=True, choices=sorted(FACT_CATEGORIES))
    timeline_parser.add_argument("--key", required=True, help="the logical fact key, e.g. jlpt")
    add_output_format(timeline_parser)
    personal_context_parser = subparsers.add_parser(
        "personal-context",
        help="stage-relevant personal context; --historical is the opt-in labelled comparison",
    )
    add_vault_argument(personal_context_parser)
    add_as_of_argument(personal_context_parser)
    personal_context_parser.add_argument("--stage", help="select facts relevant to this exact stage")
    personal_mode = personal_context_parser.add_mutually_exclusive_group()
    personal_mode.add_argument(
        "--historical", action="store_true",
        help="section 12.2: retrieve the requested superseded documents, every role labelled",
    )
    personal_mode.add_argument(
        "--candidate-profile", action="store_true",
        help="emit confirmed facts in CANDIDATE_PROFILE terms for the job-seeker skill to quote",
    )
    personal_context_parser.add_argument(
        "--type", dest="document_type", choices=sorted(DOCUMENT_TYPES),
        help="with --historical: restrict the comparison to this document type",
    )
    personal_context_parser.add_argument(
        "--company", help="with --historical: restrict the comparison to this company",
    )
    personal_context_parser.add_argument(
        "--document-id", action="append", dest="document_ids", metavar="ID",
        help="with --historical: compare these exact versions (repeatable; see private-list)",
    )
    personal_context_parser.add_argument(
        "--all-documents", action="store_true",
        help="with --historical: sweep every document instead of naming what is being compared",
    )
    add_output_format(personal_context_parser)
    fact_proposal_parser = subparsers.add_parser(
        "propose-fact",
        help="propose a personal fact backed by an imported document; approve confirms it",
    )
    # The private root comes from the Vault or CAREER_PRIVATE_HOME, as every other read of it does.
    add_vault_argument(fact_proposal_parser)
    fact_proposal_parser.add_argument("--document-id", required=True, help="see private-list")
    fact_proposal_parser.add_argument("--category", required=True, choices=sorted(FACT_CATEGORIES))
    fact_proposal_parser.add_argument("--key", required=True, help="the logical fact key, e.g. jlpt")
    fact_proposal_parser.add_argument(
        "--value", required=True, help="the value you are stating; this tool does not read the file",
    )
    fact_proposal_parser.add_argument("--effective-from", help="YYYY-MM-DD; when it became true")
    fact_proposal_parser.add_argument("--expires-on", help="YYYY-MM-DD; when it stops being valid")
    fact_proposal_parser.add_argument(
        "--supersedes", help="the confirmed fact id this one replaces (see personal-timeline)",
    )
    add_output_format(fact_proposal_parser)
    context_proposal_parser = subparsers.add_parser(
        "propose-context",
        help="create an approval-gated proposal from a SELF_ANALYSIS_PROFILE YAML",
    )
    add_vault_argument(context_proposal_parser)
    context_proposal_parser.add_argument("--source", required=True, help="CWD-relative SELF_ANALYSIS_PROFILE YAML")
    add_output_format(context_proposal_parser)

    def add_private_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("--private-home", help=f"private root; falls back to {PRIVATE_ENV}")
        command.add_argument("--vault", default=os.environ.get("CAREER_VAULT"), help="only used to derive <vault>/private")

    private_doctor_parser = subparsers.add_parser(
        "private-doctor",
        help="diagnose the private career-document store; never requires an initialized Vault",
    )
    add_private_arguments(private_doctor_parser)
    private_doctor_parser.add_argument(
        "--scan-root", action="append", default=None, metavar="DIR",
        help="directory to scan for stray personal documents; repeatable, defaults to the "
             "current working directory",
    )
    add_output_format(private_doctor_parser)
    private_import_parser = subparsers.add_parser(
        "private-import",
        help="copy a document into the private store; the original file is preserved",
    )
    add_private_arguments(private_import_parser)
    private_import_parser.add_argument("source")
    private_import_parser.add_argument("--type", dest="document_type", required=True, choices=DOCUMENT_TYPES)
    private_import_parser.add_argument("--effective-from", help="YYYY-MM-DD when the document became applicable")
    private_import_parser.add_argument("--company", help="company for a company-scoped ES/application document")
    private_import_parser.add_argument("--purpose", default="general")
    private_import_parser.add_argument("--language", default="ja")
    add_output_format(private_import_parser)
    private_list_parser = subparsers.add_parser(
        "private-list", help="list document metadata; document bodies are never printed",
    )
    add_private_arguments(private_list_parser)
    add_as_of_argument(private_list_parser)
    add_output_format(private_list_parser)
    return parser


def run_private_command(args: argparse.Namespace) -> dict[str, Any]:
    """Private-store commands resolve their own root and never touch the Vault contract."""
    if args.command == "private-doctor":
        # The CLI boundary supplies the default scan root (section 13.1); the store itself never
        # invents one, so a caller always knows exactly what was walked.
        return private_doctor(args.private_home, args.vault, args.scan_root or [Path.cwd()])
    home = PrivateHome(resolve_private_home(args.private_home, args.vault))
    if args.command == "private-list":
        initialize_private_home(home)
        return {
            "private_home": str(home.path),
            "as_of": args.as_of,
            # Metadata only: raw document bodies never leave the private store (section 28.1).
            # `status` is derived here for the requested date, never read from the registry, which
            # records observation alone.
            "documents": document_states(private_documents(home), args.as_of),
        }
    return import_document(
        home, args.source, args.document_type,
        effective_from=args.effective_from, company=args.company,
        purpose=args.purpose, language=args.language,
    )


def _output_language(args: argparse.Namespace, result: Mapping[str, Any] | None = None, home: CareerVault | None = None) -> str:
    """Choose human-output language without changing the machine contract."""
    if args.command == "run" and args.mode == "chat":
        message = args.message or ""
        return normalize_language((result or {}).get("language") or language_for(message))
    if args.command == "guided" and args.message:
        return language_for(args.message)
    if args.command == "setup" and args.language:
        return normalize_language(args.language)
    if result and isinstance(result.get("profile"), dict) and result["profile"].get("language"):
        return normalize_language(result["profile"].get("language"))
    if home is not None:
        try:
            return normalize_language(home.load_profile().get("language"))
        except (CareerError, OSError, ValueError):
            pass
    return normalize_language(None)


def main(argv: Iterable[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    skills_root = Path(__file__).resolve().parent.parent
    try:
        if args.command == "setup":
            vault_path = Path(args.vault).expanduser() if args.vault else DEFAULT_VAULT_PATH
            setup_home = CareerVault(vault_path)
            if setup_home.initialized():
                recover_approval(setup_home)
            result = setup(vault_path, args.track, args.target_role, args.graduation_year, args.language)
            result = project_ux(args.command, result, args=vars(args), language=_output_language(args, result))
            if args.output_format == "human":
                print(render_human(result))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("ok", True) else 2
        if args.command == "guided":
            vault_path = Path(args.vault).expanduser() if args.vault else DEFAULT_VAULT_PATH
            guided_home = CareerVault(vault_path)
            if guided_home.initialized():
                recover_approval(guided_home, workspace=args.workspace)
            result = run_guided(
                guided_home,
                workspace=args.workspace,
                as_of=args.as_of,
                choices=args.choice,
                interactive=args.output_format == "human" and sys.stdin.isatty(),
                confirm=args.confirm,
                message=args.message,
                proposal_id=args.proposal_id,
                evidence=args.evidence,
                deadline=args.deadline,
                company=args.company,
                compensation=args.compensation,
                currency=args.currency,
                next_action=args.next_action,
                version=args.version,
                track=args.track,
                target_role=args.target_role,
                graduation_year=args.graduation_year,
                language=args.language,
            )
            result = project_ux(args.command, result, args=vars(args), language=_output_language(args, result, guided_home))
            if args.output_format == "human":
                print(render_guided_human(result))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("ok", True) else 2
        # AC-23: the private store is independent of the Vault, so these branch above the Vault
        # requirement. A user checking whether a resume is about to be committed must not first be
        # told to initialize an unrelated Vault.
        if args.command in ("private-doctor", "private-import", "private-list"):
            result = run_private_command(args)
            result = project_ux(args.command, result, args=vars(args), language=_output_language(args, result))
            if args.output_format == "human":
                print(render_human(result))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("ok", True) else 2
        if not args.vault:
            raise CareerError("--vault or CAREER_VAULT is required; the runtime never defaults to the current directory")
        home = CareerVault(Path(args.vault))
        if args.command == "init":
            result = initialize_vault(home.path)
        else:
            home.require_initialized()
            if _requires_approval_recovery(args):
                recover_approval(home, workspace=getattr(args, "workspace", None))
            if args.command == "set-job-search":
                result = set_profile_axis(home, "job_search", args.value)
            elif args.command == "set-employment-status":
                result = set_profile_axis(home, "employment_status", args.value)
            elif args.command == "doctor":
                result = doctor(home, fix=args.fix, workspace=args.workspace)
            elif args.command == "add-project":
                period = {"from": args.period_from, "to": args.period_to}
                result = add_project(
                    home, args.title, project_id=args.project_id,
                    role=args.role, scope=args.scope, summary=args.summary, status=args.status,
                    period=period if any(period.values()) else None,
                )
            elif args.command == "weekly-review":
                result = weekly_review(home, since=args.since, as_of=args.as_of)
            elif args.command == "projects":
                result = list_projects(home, status=args.status)
            elif args.command == "project-timeline":
                result = show_project_timeline(home, args.project_id)
            elif args.command == "link-work-event":
                if args.clear and (args.primary or args.related):
                    raise CareerError(
                        "--none records no project; it cannot be combined with --project or --related",
                        code="INVALID_INPUT",
                    )
                result = link_work_event(
                    home, args.proposal_id,
                    primary=args.primary, related=args.related, clear=args.clear,
                )
            elif args.command == "review-work-event":
                raw = sys.stdin.read() if args.work_event_json == "-" else args.work_event_json
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise CareerError(f"--json must be valid JSON: {exc}", code="INVALID_INPUT") from exc
                result = review_work_event(home, args.proposal_id, payload, replace=args.replace)
            elif args.command == "work-events":
                result = work_events(
                    home, confirmed_only=args.confirmed_only, as_of=args.as_of,
                )
            elif args.command == "status":
                result = status(home, workspace=args.workspace)
            elif args.command == "proposals":
                if args.limit is not None and args.limit < 1:
                    raise CareerError("--limit must be a positive integer")
                result = review_proposal(home, args.proposal_id) if args.proposal_id else list_proposals(home, include_all=args.include_all, limit=args.limit)
            elif args.command == "approve":
                if args.workspace is not None:
                    workspace_summary(args.workspace)
                result = approve(
                    home, args.proposal_id, args.evidence, args.deadline, args.company,
                    args.compensation, args.currency, args.workspace, args.next_action,
                )
            elif args.command == "restore-state":
                result = restore_state(home, args.version)
            elif args.command == "index":
                result = run_index(home, include_archives=args.include_archives)
            elif args.command == "context":
                result = run_context(home, args.track, args.stage, args.as_of)
            elif args.command == "personal-profile":
                result = project(read_jsonl(home.events), args.as_of)
            elif args.command == "personal-timeline":
                result = {
                    # Section 12.2: historical values are explicitly labelled, never presented as
                    # current facts. The caller asked for history, so it is told which is which.
                    "context_mode": "historical",
                    "category": args.category,
                    "key": args.key,
                    "history": timeline(read_jsonl(home.events), args.category, args.key),
                }
            elif args.command == "personal-context":
                document_arguments = (
                    args.document_type, args.company, args.document_ids, args.all_documents,
                )
                if not args.historical and any(document_arguments):
                    # Accepting an argument and then ignoring it teaches the caller that a filter
                    # was applied when none was. Say so instead.
                    raise CareerError(
                        "--type, --company, --document-id and --all-documents apply to --historical"
                    )
                if args.stage and (args.historical or args.candidate_profile):
                    raise CareerError(
                        "--stage selects facts for the default mode and does not apply here"
                    )
                events = read_jsonl(home.events)
                if args.candidate_profile:
                    result = candidate_profile_values(events, args.as_of)
                elif args.historical:
                    records, unavailable = private_records(home.path)
                    result = historical_comparison(
                        records, args.as_of,
                        document_type=args.document_type, company=args.company,
                        document_ids=tuple(args.document_ids or ()),
                        all_documents=args.all_documents,
                    )
                    if unavailable:
                        result["documents_unavailable"] = unavailable
                else:
                    # Stage validation lives in the selector, not here: it is a public boundary
                    # symbol and a caller that skips argparse must fail closed too.
                    result = select_personal_context(events, args.stage, args.as_of)
            elif args.command == "propose-fact":
                # No degradation here, unlike the read paths: this writes a provenance link, and a
                # store we cannot resolve is a link we cannot verify.
                store = PrivateHome(resolve_private_home(None, home.path))
                result = propose_fact(
                    home, store,
                    document_id=args.document_id, category=args.category, key=args.key,
                    value=args.value, effective_from=args.effective_from,
                    expires_on=args.expires_on, supersedes=args.supersedes,
                )
            elif args.command == "propose-context":
                result = propose_career_context(home, args.source)
            elif args.mode == "chat":
                message = args.message if args.message is not None else read_stdin_utf8().strip()
                if not message:
                    raise CareerError("chat requires --message or stdin")
                result = run_chat(home, skills_root, message, args.track, args.as_of)
                complete_onboarding(home, result)
            elif args.mode == "heartbeat":
                result = run_heartbeat(home)
            else:
                result = run_discover(home, args.source)
        result = project_ux(args.command, result, args=vars(args), language=_output_language(args, result, home))
        if args.output_format == "human":
            print(render_human(result))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except CareerError as exc:
        result = error_payload(exc, language=_output_language(args, locals().get("result"), locals().get("home")))
        if getattr(args, "output_format", "json") == "human":
            print(render_human(result), file=sys.stderr)
        else:
            print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
