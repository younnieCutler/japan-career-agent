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
from typing import Any, Iterable

_SHARED_ROOT = Path(__file__).resolve().parent.parent.parent / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))
import pipeline_store  # noqa: E402

from models import (  # noqa: E402
    CAREER_CONTEXT_FIELDS,
    CAREER_STATUSES,
    CHUTO_STAGES,
    CONTEXT_KINDS,
    EVENT_STATUSES,
    FACT_CATEGORIES,
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
    normalized_state,
)
from validation import (  # noqa: E402
    DATE_VALUE,
    NUMERIC_CLAIM,
    iso_date,
    validate_career_context,
    validate_event,
)
from routing import (  # noqa: E402
    FLOW_REFERENCE,
    ROUTING,
    ROUTING_REFERENCE,
    _WORD_BOUNDARY_TERMS,
    flow_phase_for,
    flow_phase_ids,
    infer_track,
    language_for,
    load_flow_reference,
    load_routing,
    skill_context,
    stage_for,
    term_present,
)
from proposals import (  # noqa: E402
    approval_action_for,
    list_proposals,
    make_event,
    proposal_summary,
    propose_career_context,
    propose_fact,
    run_chat,
)
from lifecycle import (  # noqa: E402
    approve as _lifecycle_approve,
    count_consecutive_safe_stops,
    record_failed_attempt,
    restore_state,
    state_version_is_persisted,
    vault_lock,
)
from projection import (  # noqa: E402
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

_PROPOSAL_COMPATIBILITY_EXPORTS = (
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
    apply_event_to_state,
    company_slug,
    migrate_pipeline_file,
    pipeline_file,
    upsert_pipeline_entry,
    workspace_path,
)

_ROUTING_COMPATIBILITY_EXPORTS = (
    FLOW_REFERENCE,
    ROUTING,
    ROUTING_REFERENCE,
    _WORD_BOUNDARY_TERMS,
    flow_phase_for,
    flow_phase_ids,
    infer_track,
    language_for,
    load_routing,
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
    CAREER_STATUSES,
    CHUTO_STAGES,
    CONTEXT_KINDS,
    EVENT_STATUSES,
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
    normalized_state,
    validate_career_context,
    validate_event,
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
    actions: list[dict[str, Any]] = []
    for deadline in state.get("deadlines", []):
        if deadline.get("status") != "open":
            continue
        try:
            days = (dt.date.fromisoformat(deadline["date"]) - today()).days
        except (KeyError, ValueError):
            continue
        if days <= 7:
            actions.append({"text": f"마감 확인: {deadline.get('title', 'deadline')}", "event_id": deadline.get("event_id"), "stage": state.get("stage"), "flow_phase": state.get("flow_phase"), "estimated_minutes": 15, "deadline": deadline["date"], "requires_confirmation": True, "reason": "deadline"})
    profile = home.load_profile()
    seen_dates = {item.get("deadline") for item in actions}
    for key, value in profile.items():
        if not isinstance(value, str) or not DATE_VALUE.match(value) or value in seen_dates:
            continue
        try:
            days = (dt.date.fromisoformat(value[:10]) - today()).days
        except ValueError:
            continue
        if 0 <= days <= 7:
            actions.append({"text": f"마감 확인: {key}", "event_id": None, "stage": state.get("stage"), "flow_phase": state.get("flow_phase"), "estimated_minutes": 15, "deadline": value, "requires_confirmation": True, "reason": "profile_deadline"})
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
        pipeline_writer=lambda event: upsert_pipeline_entry(event, path=pipeline_file(workspace), workspace=workspace),
        state_projector=apply_event_to_state,
    )


def status(home: CareerVault) -> dict[str, Any]:
    state = home.load_state()
    profile = home.load_profile()
    return {"vault": str(home.path), "profile": {"track": profile.get("track"), "career_status": profile.get("career_status", "active"), "target_role": profile.get("target_role")}, "state": state, "event_count": len(read_jsonl(home.events)), "pending_proposals": sum(1 for row in read_jsonl(home.proposals) if row.get("status") == "pending"), "posting_count": len(read_jsonl(home.postings))}


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

    init_parser = subparsers.add_parser("init")
    add_vault_argument(init_parser)
    setup_parser = subparsers.add_parser(
        "setup",
        help="one-shot first run: init the vault (default ~/.career-agent-vault) + profile fields + doctor",
    )
    setup_parser.add_argument("--vault", default=os.environ.get("CAREER_VAULT"), help="defaults to CAREER_VAULT, then ~/.career-agent-vault")
    setup_parser.add_argument("--track", choices=sorted(TRACKS))
    setup_parser.add_argument("--target-role")
    setup_parser.add_argument("--graduation-year", type=int)
    setup_parser.add_argument("--language", default=None)
    doctor_parser = subparsers.add_parser("doctor")
    add_vault_argument(doctor_parser)
    add_workspace_argument(doctor_parser)
    doctor_parser.add_argument("--fix", action="store_true", help="migrate the legacy nested data/pipeline.yml shape")
    run = subparsers.add_parser("run")
    add_vault_argument(run)
    run.add_argument("--mode", choices=("chat", "heartbeat", "discover"), required=True)
    run.add_argument("--message")
    run.add_argument("--track", choices=sorted(TRACKS))
    run.add_argument("--source", help="JSON file for discover; stdin is used when omitted")
    add_as_of_argument(run)
    status_parser = subparsers.add_parser("status")
    add_vault_argument(status_parser)
    proposals_parser = subparsers.add_parser(
        "proposals",
        help="list proposal metadata without exposing proposal bodies",
    )
    add_vault_argument(proposals_parser)
    proposals_parser.add_argument("--all", dest="include_all", action="store_true", help="include approved and superseded proposals")
    proposals_parser.add_argument("--limit", type=int, help="return at most N proposals (N must be positive)")
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
    restore_parser = subparsers.add_parser(
        "restore-state",
        help="replace the current state with a saved snapshot; the append-only ledger is kept",
    )
    add_vault_argument(restore_parser)
    restore_parser.add_argument("version")
    index_parser = subparsers.add_parser("index")
    add_vault_argument(index_parser)
    index_parser.add_argument("--include-archives", action="store_true", help="include 06-archives in the index")
    context_parser = subparsers.add_parser("context")
    add_vault_argument(context_parser)
    context_parser.add_argument("--track", choices=sorted(TRACKS), help="override the profile/state track")
    context_parser.add_argument("--stage", help="select verified notes for this exact stage")
    add_as_of_argument(context_parser)
    profile_parser = subparsers.add_parser(
        "personal-profile",
        help="current personal-profile projection; Unknown and Conflict are explicit states",
    )
    add_vault_argument(profile_parser)
    add_as_of_argument(profile_parser)
    timeline_parser = subparsers.add_parser(
        "personal-timeline",
        help="full labelled history for one fact key, including superseded records",
    )
    add_vault_argument(timeline_parser)
    timeline_parser.add_argument("--category", required=True, choices=sorted(FACT_CATEGORIES))
    timeline_parser.add_argument("--key", required=True, help="the logical fact key, e.g. jlpt")
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
    context_proposal_parser = subparsers.add_parser(
        "propose-context",
        help="create an approval-gated proposal from a SELF_ANALYSIS_PROFILE YAML",
    )
    add_vault_argument(context_proposal_parser)
    context_proposal_parser.add_argument("--source", required=True, help="CWD-relative SELF_ANALYSIS_PROFILE YAML")

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
    private_list_parser = subparsers.add_parser(
        "private-list", help="list document metadata; document bodies are never printed",
    )
    add_private_arguments(private_list_parser)
    add_as_of_argument(private_list_parser)
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
            result = setup(vault_path, args.track, args.target_role, args.graduation_year, args.language)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("ok", True) else 2
        # AC-23: the private store is independent of the Vault, so these branch above the Vault
        # requirement. A user checking whether a resume is about to be committed must not first be
        # told to initialize an unrelated Vault.
        if args.command in ("private-doctor", "private-import", "private-list"):
            result = run_private_command(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("ok", True) else 2
        if not args.vault:
            raise CareerError("--vault or CAREER_VAULT is required; the runtime never defaults to the current directory")
        home = CareerVault(Path(args.vault))
        if args.command == "init":
            result = initialize_vault(home.path)
        else:
            home.require_initialized()
            if args.command == "doctor":
                result = doctor(home, fix=args.fix, workspace=args.workspace)
            elif args.command == "status":
                result = status(home)
            elif args.command == "proposals":
                if args.limit is not None and args.limit < 1:
                    raise CareerError("--limit must be a positive integer")
                result = list_proposals(home, include_all=args.include_all, limit=args.limit)
            elif args.command == "approve":
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
                records, unavailable = private_records(home.path)
                if unavailable:
                    # Unlike a read path, this one writes a provenance link. A store we cannot
                    # resolve means we cannot check that the document exists, and an unverifiable
                    # link is the thing `propose_fact` exists to refuse.
                    raise CareerError(unavailable)
                result = propose_fact(
                    home, records,
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
            elif args.mode == "heartbeat":
                result = run_heartbeat(home)
            else:
                result = run_discover(home, args.source)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except CareerError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "safe_stop": True, "retry_count": 0, "external_side_effect": False}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
