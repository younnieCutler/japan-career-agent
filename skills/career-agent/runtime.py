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
import re
import sys
import unicodedata
import uuid

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

_SHARED_ROOT = Path(__file__).resolve().parent.parent.parent / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))
import pipeline_store  # noqa: E402
import self_analysis_profile  # noqa: E402

from models import (  # noqa: E402
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
)
from validation import DATE_VALUE, NUMERIC_CLAIM, validate_career_context, validate_event  # noqa: E402
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

_PERSISTENCE_COMPATIBILITY_EXPORTS = (
    atomic_write_text,
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
FLOW_REFERENCE = Path(__file__).resolve().parent / "references" / "japan-career-flow.toml"
ROUTING_REFERENCE = Path(__file__).resolve().parent / "references" / "routing.yml"


def load_routing() -> dict[str, Any]:
    """KO/JA/EN keyword lexicon shared by infer_track(), stage_for() and flow_phase_for()."""
    import yaml

    data = yaml.safe_load(ROUTING_REFERENCE.read_text(encoding="utf-8")) or {}
    if not data.get("track") or not data.get("stage_alias") or not data.get("flow_phase"):
        raise CareerError(f"invalid routing reference: {ROUTING_REFERENCE}")
    return data


ROUTING = load_routing()

# Short ASCII tokens where a plain substring match false-positives inside unrelated English words
# (e.g. "es" — meant to catch the ES/entry-sheet abbreviation — also matches inside "research",
# "yes", "best"). Everything else, including intentional stems like "graduat", still matches as a
# substring.
_WORD_BOUNDARY_TERMS = {"es"}


def term_present(term: str, lowered: str) -> bool:
    if term in _WORD_BOUNDARY_TERMS:
        return re.search(rf"\b{re.escape(term)}\b", lowered) is not None
    return term in lowered


def language_for(message: str) -> str:
    first_chunk = re.split(r"\n\s*\n|\n|(?<=[.!?。！？])\s+", message.strip(), maxsplit=1)[0]
    korean = len(re.findall(r"[가-힣]", first_chunk))
    japanese = len(re.findall(r"[ぁ-ゖァ-ヺ一-龯々]", first_chunk))
    if korean or japanese:
        return "ko" if korean >= japanese else "ja"
    return "en"


def infer_track(message: str, requested: str | None = None) -> str | None:
    if requested in TRACKS:
        return requested
    lowered = message.lower()
    if any(term_present(term.lower(), lowered) for term in ROUTING["track"]["shinsotsu"]):
        return "shinsotsu"
    if any(term_present(term.lower(), lowered) for term in ROUTING["track"]["chuto"]):
        return "chuto"
    return None


def stage_for(message: str, track: str, current_stage: str | None = None) -> str:
    lowered = message.lower()
    for group in ROUTING["stage_alias"]:
        alias = group["alias"]
        if not any(term_present(term.lower(), lowered) for term in group["terms"]):
            continue
        if alias == "chuto":
            track = "chuto"
        if alias == "shinsotsu":
            track = "shinsotsu"
        candidates = CHUTO_STAGES if track == "chuto" else SHINSOTSU_STAGES
        return {
            "self": candidates[0],
            "documents": candidates[1],
            "research": candidates[2],
            "interview": candidates[4 if track == "chuto" else 5],
            "offer": candidates[5 if track == "chuto" else 6],
            "exit": candidates[6],
        }.get(alias, candidates[0])
    candidates = CHUTO_STAGES if track == "chuto" else SHINSOTSU_STAGES
    if current_stage in candidates:
        return current_stage
    return candidates[0]


def skill_context(skills_root: Path, stage: str) -> dict[str, Any]:
    skill_name = SKILL_BY_STAGE.get(stage)
    if not skill_name:
        return {}
    skill_path = skills_root / skill_name / "SKILL.md"
    if not skill_path.exists():
        return {"skill": skill_name, "available": False}
    text = skill_path.read_text(encoding="utf-8")
    description = ""
    match = re.search(r"^description:\s*>\s*\n(.*?)(?=^---\s*$)", text, re.M | re.S)
    if match:
        description = " ".join(line.strip() for line in match.group(1).splitlines()).strip()
    references = [
        name for name in REFERENCE_BY_STAGE.get(stage, ())
        if (skill_path.parent / name).exists()
    ]
    return {
        "skill": skill_name,
        "available": True,
        "path": str(skill_path),
        "description": description,
        "references": references,
    }


def load_flow_reference() -> dict[str, Any]:
    reference = read_toml(FLOW_REFERENCE)
    if not reference.get("metadata") or not reference.get("shinsotsu") or not reference.get("chuto"):
        raise CareerError(f"invalid career flow reference: {FLOW_REFERENCE}")
    return reference


def flow_phase_ids(reference: dict[str, Any], track: str) -> set[str]:
    phases = reference.get(track, {}).get("phases", [])
    return {str(phase.get("id")) for phase in phases if isinstance(phase, dict) and phase.get("id")}


def flow_phase_for(message: str, track: str, state: dict[str, Any], profile: dict[str, Any], reference: dict[str, Any]) -> str:
    # Message signal comes first: once a confirmed event sets state.flow_phase, that value stays
    # `in allowed` forever, so checking it before the message would freeze flow_phase at whatever
    # the first confirmed event happened to be — later messages with a clear new signal (e.g. a
    # resignation message arriving after an offer was confirmed) would never move it again. A
    # message with no signal (a generic "what's next?" follow-up) still falls through to the
    # state/profile value below, which is what keeps continuity for non-signaling messages.
    allowed = flow_phase_ids(reference, track)
    lowered = message.lower()
    for signal in ROUTING["flow_phase"][track]:
        if any(term_present(term.lower(), lowered) for term in signal["terms"]) and signal["id"] in allowed:
            return signal["id"]
    for value in (profile.get("flow_phase"), state.get("flow_phase")):
        if value in allowed:
            return str(value)
    if track == "shinsotsu" and state.get("stage") == SHINSOTSU_STAGES[-1] and "offer_onboarding" in allowed:
        return "offer_onboarding"
    return "preparation"


def approval_action_for(message: str) -> str:
    return {
        "ko": "근거를 확인한 뒤 이벤트 확정",
        "ja": "根拠を確認してからイベントを確定する",
        "en": "Confirm evidence before saving",
    }[language_for(message)]


def make_event(message: str, track: str, stage: str, flow_phase: str, *, status: str = "draft") -> dict[str, Any]:
    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    language = language_for(message)
    title = {
        "ko": "사용자 입력 기반 경력 이벤트",
        "ja": "ユーザー入力に基づくキャリアイベント",
        "en": "User-reported career event",
    }[language]
    event = {
        "id": event_id,
        "track": track,
        "stage": stage,
        "flow_phase": flow_phase,
        "type": "user_report",
        "occurred_at": utc_now(),
        "title": title,
        "summary": message.strip(),
        "evidence": [],
        "source": "user_message",
        "next_action": None,
        "deadline": None,
        "status": status,
    }
    validate_event(event)
    return event


_LEGAL_ENTITY_MARKERS = (
    "株式会社", "有限会社", "合同会社", "(株)",
)


def _canonical_company_name(name: str) -> str:
    value = unicodedata.normalize("NFKC", name).strip()
    marker_pattern = "|".join(re.escape(marker) for marker in _LEGAL_ENTITY_MARKERS)
    value = re.sub(rf"^(?:{marker_pattern})\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(rf"\s*(?:{marker_pattern})$", "", value, flags=re.IGNORECASE)
    return value.casefold().strip()


def _legacy_company_slug(name: str) -> str:
    return re.sub(r"[^\w]+", "-", name.strip().lower(), flags=re.UNICODE).strip("-")


def company_slug(name: str) -> str:
    """Canonical join key for pipeline and company-profile projections.

    Existing legacy slugs are preserved by the pipeline writer when an alias already exists;
    this function only defines the key for new entries.
    """
    canonical = _canonical_company_name(name)
    slug = re.sub(r"[^\w]+", "-", canonical, flags=re.UNICODE).strip("-")
    return slug or hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]


def workspace_path(workspace: str | Path | None = None) -> Path:
    """Resolve the job-search workspace explicitly when projecting Vault events.

    The Vault is canonical personal state. The workspace is the CWD-relative projection used by
    domain skills. `CAREER_WORKSPACE`/`--workspace` prevents approving from an unrelated terminal
    directory; the legacy CWD fallback remains for API callers and old scripts.

    Delegates to `pipeline_store.resolve_workspace` (WORK-002) so every entry point in the
    repository shares one precedence implementation instead of re-deriving it.
    """
    return pipeline_store.resolve_workspace(workspace)


def pipeline_file(workspace: str | Path | None = None) -> Path:
    return pipeline_store.resolve_pipeline_path(workspace)


def upsert_pipeline_entry(
    event: dict[str, Any], path: Path | None = None, workspace: str | Path | None = None,
) -> Path | None:
    """Project a confirmed company event onto data/pipeline.yml, the per-company state hub.

    The vault owns the agent flow (track / stage / deadlines / event ledger); pipeline.yml owns
    per-company progress and is what status_bar, calibrate and onboarding read. Only fields this
    runtime actually observes are written — match_score, channel, kyujin_legitimacy and the
    outcome record stay with the domain skills that produce them, and are never overwritten here.
    """
    path = path or pipeline_file(workspace)

    stage = PIPELINE_STAGE.get(event["stage"])
    day = str(event["occurred_at"])[:10]
    fields = {"name": event["company"]}
    if stage is not None:
        fields["stage"] = stage
    if event.get("next_action"):
        fields["next_action"] = event["next_action"]
    if event.get("deadline"):
        fields["deadline"] = event["deadline"]

    # pipeline.yml is a projection, not a second evidence ledger. The canonical event title is
    # intentionally short and evidence/source URLs remain only in events.jsonl.
    hist_entry = {"date": day, "event": event["title"]}
    if event.get("id"):
        hist_entry["event_id"] = event["id"]

    try:
        pipeline_store.upsert_company(
            path,
            company_slug(event["company"]),
            fields,
            history=hist_entry,
            slug_aliases=(_legacy_company_slug(event["company"]),),
        )
    except ImportError:  # pyyaml is in requirements.txt; degrade instead of breaking approve
        return None
    return path


def apply_event_to_state(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    next_state = dict(state)
    if event.get("type") == "career_context":
        # Canonical career values are a confirmed context projection, not a market-stage transition.
        next_state["last_event_id"] = event["id"]
        return next_state
    next_state["track"] = event["track"]
    next_state["stage"] = event["stage"]
    next_state["flow_phase"] = event["flow_phase"]
    next_state["last_event_id"] = event["id"]
    actions = [item for item in next_state.get("open_actions", []) if item.get("event_id") != event["id"]]
    if event.get("next_action"):
        actions.append({"text": event["next_action"], "event_id": event["id"], "stage": event["stage"]})
    next_state["open_actions"] = actions[-10:]
    if event.get("deadline"):
        deadlines = [item for item in next_state.get("deadlines", []) if item.get("event_id") != event["id"]]
        deadlines.append({"date": event["deadline"], "event_id": event["id"], "title": event["title"], "status": "open"})
        next_state["deadlines"] = sorted(deadlines, key=lambda item: item["date"])
    # Per-company progress deliberately does NOT live here — it belongs to data/pipeline.yml,
    # which the domain skills write and status_bar / calibrate read. See upsert_pipeline_entry.
    return next_state


def _merge_pipeline_companies(nested: list[dict[str, Any]], top_level: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for company in [*nested, *top_level]:
        if not isinstance(company, dict) or not str(company.get("slug") or "").strip():
            raise CareerError("legacy pipeline companies must be objects with a slug")
        slug = str(company["slug"])
        if slug not in merged:
            merged[slug] = dict(company)
            order.append(slug)
            continue
        history = merged[slug].get("history")
        merged[slug].update(company)
        if isinstance(history, list) and isinstance(company.get("history"), list):
            merged[slug]["history"] = history + company["history"]
    return [merged[slug] for slug in order]


def migrate_pipeline_file(path: Path) -> bool:
    """Flatten the pre-1.2.0 nested pipeline shape without dropping either company list."""
    data = pipeline_store.load(path)
    nested = data.get("pipeline")
    if nested is None:
        return False
    if not isinstance(nested, dict):
        raise CareerError(f"{path}: legacy pipeline key must contain an object")

    def apply(current: dict[str, Any]) -> dict[str, Any]:
        legacy = current.pop("pipeline", {})
        nested_companies = legacy.get("companies") or []
        top_companies = current.get("companies") or []
        if not isinstance(nested_companies, list) or not isinstance(top_companies, list):
            raise CareerError(f"{path}: legacy pipeline companies must be lists")
        current["companies"] = _merge_pipeline_companies(nested_companies, top_companies)
        nested_updated = legacy.get("updated")
        top_updated = current.get("updated")
        if nested_updated or top_updated:
            current["updated"] = max(str(nested_updated or ""), str(top_updated or ""))
        for key, value in legacy.items():
            if key not in {"companies", "updated"} and key not in current:
                current[key] = value
        return current

    pipeline_store.mutate(path, apply)
    return True


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
            expires = str(metadata.get("expires_on") or "")
            try:
                if expires and dt.date.fromisoformat(expires) < today():
                    warnings.append(f"context note expired: {note['path']}")
            except ValueError:
                errors.append(f"context note expires_on must use YYYY-MM-DD: {note['path']}")
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


def run_chat(home: CareerVault, skills_root: Path, message: str, requested_track: str | None) -> dict[str, Any]:
    state = home.load_state()
    profile = home.load_profile()
    recent_events = read_jsonl(home.events)[-5:]
    track = infer_track(message, requested_track) or state.get("track") or profile.get("track")
    if not track:
        goal = "resolve track before routing"
        retry_count = count_consecutive_safe_stops(home, goal)
        trajectory = {
            "id": f"traj-{uuid.uuid4().hex[:12]}",
            "created_at": utc_now(),
            "mode": "chat",
            "observe": {"track": state.get("track"), "stage": state.get("stage"), "deadlines": state.get("deadlines", []), "recent_events": recent_events, "message": message, "data_trust": UNTRUSTED_DATA_MARKER, "instruction_authority": "none"},
            "plan": {"goal": goal},
            "act": {"proposal": None},
            "verify": {"track": "ambiguous", "external_side_effect": False},
            "correct": {"retry_count": retry_count, "needs_user_confirmation": True},
            "persist": {"trajectory_only": True},
        }
        home.append_trajectory(trajectory)
        question = "track must be explicit: shinsotsu or chuto"
        if retry_count >= 2:
            question += " (asked before — reply with your track, or set it directly in career-profile.toml)"
        return {"mode": "chat", "language": language_for(message), "needs_confirmation": True, "question": question, "saved": str(home.trajectories)}
    if track == "shinsotsu" and not isinstance(profile.get("graduation_year"), int):
        goal = "collect required shinsotsu graduation year before proposing an event"
        retry_count = count_consecutive_safe_stops(home, goal)
        home.append_trajectory(
            {
                "id": f"traj-{uuid.uuid4().hex[:12]}",
                "created_at": utc_now(),
                "mode": "chat",
                "observe": {"track": track, "profile_has_graduation_year": False, "message": message, "data_trust": UNTRUSTED_DATA_MARKER, "instruction_authority": "none"},
                "plan": {"goal": goal},
                "act": {"proposal": None},
                "verify": {"safe_stop": True, "external_side_effect": False},
                "correct": {"retry_count": retry_count, "needs_user_confirmation": True},
                "persist": {"trajectory_only": True},
            }
        )
        question = "profile.graduation_year is required for shinsotsu before an event proposal can be created"
        if retry_count >= 2:
            question += " (asked before — set profile.graduation_year directly in career-profile.toml)"
        return {
            "mode": "chat",
            "language": language_for(message),
            "track": track,
            "needs_confirmation": True,
            "question": question,
            "saved": str(home.trajectories),
        }
    stage = stage_for(message, track, state.get("stage"))
    reference = load_flow_reference()
    flow_phase = flow_phase_for(message, track, state, profile, reference)
    context = select_context(home.path, track, stage)
    event = make_event(message, track, stage, flow_phase)
    approval_action = approval_action_for(message)
    proposal = {
        "id": f"proposal-{uuid.uuid4().hex[:12]}",
        "kind": "event",
        "status": "pending",
        "created_at": utc_now(),
        "next_action": approval_action,
        "event": event,
    }
    trajectory = {
        "id": f"traj-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "mode": "chat",
        "observe": {"track": state.get("track"), "stage": state.get("stage"), "deadlines": state.get("deadlines", []), "recent_events": recent_events, "message": message, "data_trust": UNTRUSTED_DATA_MARKER, "instruction_authority": "none"},
        "plan": {"track": track, "stage": stage, "flow_phase": flow_phase, "goal": "route and propose a grounded event", "next_action": approval_action},
        "act": {"proposal_id": proposal["id"], "skill": skill_context(skills_root, stage), "context_count": len(context)},
        "verify": {"event_schema": "valid", "context_is_metadata_only": True, "external_side_effect": False},
        "correct": {"retry_count": 0, "needs_user_confirmation": True},
        "persist": {"proposal_id": proposal["id"]},
    }
    with vault_lock(home):  # PERSIST-005: proposals.jsonl append is a shared write, not append-only-safe alone
        home.add_proposal(proposal)
        home.append_trajectory(trajectory)
    return {"mode": "chat", "language": language_for(message), "track": track, "stage": stage, "flow_phase": flow_phase, "skill": skill_context(skills_root, stage), "context": context, "context_trust": {"data": UNTRUSTED_DATA_MARKER, "instruction_authority": "none"}, "proposal": proposal, "saved": str(home.proposals)}


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


def run_context(home: CareerVault, requested_track: str | None, requested_stage: str | None) -> dict[str, Any]:
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
        "profile": {key: profile[key] for key in profile_keys if key in profile and profile[key] not in (None, "")},
        "state": state,
        "context": select_context(home.path, track, stage) if stage else [],
        "context_trust": {"data": UNTRUSTED_DATA_MARKER, "instruction_authority": "none"},
        "career_context": career_context,
        "career_context_confirmed": career_context is not None,
        "career_context_event_id": career_event.get("id") if career_event else None,
        "read_only": True,
        "note_bodies_included": False,
    }


def propose_career_context(home: CareerVault, source: str) -> dict[str, Any]:
    """Create an approval-gated proposal from a CWD-relative SELF_ANALYSIS_PROFILE."""
    source_path = Path(source).expanduser().resolve()
    if not source_path.exists():
        raise CareerError(f"career context source not found: {source_path}")
    try:
        import yaml
        raw = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
    except ImportError as exc:
        raise CareerError("PyYAML is required to propose career context") from exc
    except (OSError, yaml.YAMLError) as exc:
        raise CareerError(f"invalid career context YAML: {source_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise CareerError("career context source root must be an object")
    raw_only = sorted(self_analysis_profile.RAW_ONLY_FIELDS.intersection(raw))
    if raw_only:
        raise CareerError(
            "raw checklist submission cannot become canonical career context: "
            + ", ".join(raw_only)
        )
    if "self_analysis_version" in raw:
        try:
            self_analysis_profile.validate_self_analysis_profile(raw)
        except self_analysis_profile.ProfileValidationError as exc:
            raise CareerError(str(exc)) from exc
    payload = validate_career_context(raw)
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    with vault_lock(home):
        proposals = read_jsonl(home.proposals)
        for row in proposals:
            if row.get("kind") != "career_context" or row.get("profile_digest") != digest:
                continue
            if row.get("status") in {"pending", "approved"}:
                return {
                    "mode": "propose-context",
                    "deduplicated": True,
                    "proposal": row,
                    "source": str(source_path),
                }
        for row in proposals:
            if row.get("kind") == "career_context" and row.get("status") == "pending":
                row["status"] = "superseded"
                row["updated_at"] = utc_now()
        track = home.load_state().get("track") or home.load_profile().get("track")
        if track not in TRACKS:
            raise CareerError("career context proposal requires profile.track or state.track")
        state = home.load_state()
        stage = state.get("stage") or ("自己分析・就活軸" if track == "shinsotsu" else "自己分析・転職軸")
        flow_phase = state.get("flow_phase") or "self_analysis"
        event = {
            "id": f"evt-{uuid.uuid4().hex[:12]}",
            "track": track,
            "stage": stage,
            "flow_phase": flow_phase,
            "type": "career_context",
            "occurred_at": utc_now(),
            "title": "User-confirmed career context",
            "summary": "User-confirmed canonical career values",
            "evidence": [f"SELF_ANALYSIS_PROFILE sha256:{digest}"],
            "source": "jiko-bunseki",
            "next_action": "",
            "deadline": None,
            "status": "draft",
            "career_context": payload,
            "profile_digest": digest,
        }
        validate_event(event)
        proposal = {
            "id": f"proposal-{uuid.uuid4().hex[:12]}",
            "kind": "career_context",
            "status": "pending",
            "created_at": utc_now(),
            "profile_digest": digest,
            "event": event,
        }
        write_jsonl(home.proposals, [*proposals, proposal])
    return {"mode": "propose-context", "deduplicated": False, "proposal": proposal, "source": str(source_path)}


@contextmanager
def vault_lock(home: CareerVault):
    """Serialize read-modify-write sections against other processes on the same Vault.

    A single local machine can still run two CLI invocations at once (two terminals, or a
    human and Claude both acting). Without this, two concurrent `approve` calls on the same
    proposal could both pass the "is it still pending" check before either writes, producing
    a duplicate confirmed event.
    """
    home.ensure_runtime()
    lock_path = home.runtime / "lock"
    with open(lock_path, "a+") as handle:
        if fcntl is not None:
            fcntl.flock(handle, fcntl.LOCK_EX)
        elif msvcrt is not None:
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)
            elif msvcrt is not None:
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def count_consecutive_safe_stops(home: CareerVault, goal: str) -> int:
    count = 0
    for trajectory in reversed(read_jsonl(home.trajectories)):
        if trajectory.get("mode") == "chat" and trajectory.get("plan", {}).get("goal") == goal:
            count += 1
        else:
            break
    return count


def record_failed_attempt(home: CareerVault, mode: str, observe: dict[str, Any], error: Exception, *, retry_count: int = 0) -> None:
    home.append_trajectory({
        "id": f"traj-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "mode": mode,
        "observe": observe,
        "plan": {"goal": "attempt failed"},
        "act": {"attempted": True},
        "verify": {"passed": False, "error": str(error)},
        "correct": {"action": "safe_stop", "escalated_to_user": True, "retry_count": retry_count},
        "persist": {"trajectory_only": True},
    })


def state_version_is_persisted(home: CareerVault, state: dict[str, Any]) -> bool:
    version = state.get("version")
    if not isinstance(version, str) or not version:
        return False
    if not (home.versions / f"{version}.json").is_file():
        return False
    return any(
        row.get("version") == version
        for row in read_jsonl(home.checkpoints)
        if isinstance(row, dict)
    )


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
    with vault_lock(home):
        proposal = next((row for row in read_jsonl(home.proposals) if row.get("id") == proposal_id), None)
        if not proposal:
            raise CareerError(f"proposal not found: {proposal_id}")
        if proposal.get("status") != "pending":
            raise CareerError(f"proposal is not pending: {proposal_id}")
        if proposal.get("kind") in {"event", "career_context"}:
            event = dict(proposal["event"])
            if evidence is not None:
                event["evidence"] = evidence
            if deadline is not None:
                event["deadline"] = deadline
            if company is not None:
                event["company"] = company
            if compensation is not None:
                event["compensation"] = compensation
            if currency is not None:
                event["currency"] = currency
            # The proposal's next_action is an approval instruction, not a confirmed career
            # action. Only an explicit post-approval action survives into the ledger/state.
            event["next_action"] = next_action.strip() if next_action and next_action.strip() else None
            try:
                validate_event(event, for_confirmation=True)
            except CareerError as exc:
                record_failed_attempt(home, "approve", {"proposal_id": proposal_id, "event": event}, exc)
                if str(exc).startswith("confirmed events require evidence"):
                    raise CareerError(
                        "confirmed events require evidence.\n"
                        f"Retry with: approve {proposal_id} --evidence \"<source or confirmation>\"\n"
                        "Unsupported claims remain drafts."
                    ) from exc
                if str(exc).startswith("numeric claim is not present in evidence"):
                    raise CareerError(
                        "numeric claim is not present in evidence.\n"
                        f'Retry with: approve {proposal_id} --evidence "<source or confirmation containing the exact numeric claim>"'
                    ) from exc
                raise
            event["status"] = "confirmed"
            # External write (data/pipeline.yml) first; if this fails, vault state & ledger remain clean
            pipeline = upsert_pipeline_entry(event, workspace=workspace) if event.get("company") else None

            # Vault event ledger append (idempotent guard)
            existing_events = read_jsonl(home.events)
            if not any(e.get("id") == event.get("id") for e in existing_events):
                append_jsonl(home.events, event)

            state = home.load_state()
            projected_state = apply_event_to_state(state, event)
            if projected_state == state and state_version_is_persisted(home, state):
                # A previous attempt reached the state/checkpoint commit but failed while
                # marking the proposal approved. Reuse that commit on retry instead of
                # manufacturing a second version for the same event.
                version = state["version"]
            else:
                version = home.save_state(projected_state)
            resolved_at = utc_now()
            resolution = {
                "status": "approved",
                "resolved_at": resolved_at,
                "approved_event_id": event["id"],
                "state_version": version,
            }
            updated = home.replace_proposal(
                proposal_id,
                status="approved",
                approved_at=resolved_at,
                version=version,
                approved_event_id=event["id"],
                resolution=resolution,
            )
            result = {"approved": True, "event": event, "version": version, "proposal": updated}
            if pipeline:
                result["pipeline"] = str(pipeline)
            return result
        updated = home.replace_proposal(proposal_id, status="approved", approved_at=utc_now())
        return {"approved": True, "proposal": updated, "applied": False, "message": "Only event proposals change the local ledger; skill changes remain offline proposals."}


def restore_state(home: CareerVault, version: str) -> dict[str, Any]:
    """Replace the current state with a saved snapshot. This is NOT a rollback.

    The event ledger is append-only by design, so nothing here rewinds it: `events.jsonl`,
    `proposals.jsonl` and `data/pipeline.yml` all keep everything recorded after the snapshot.
    Consequences to expect, which is why the command is not called `rollback`:

    - `choose_actions()` reads the ledger, not the state, so an event recorded after the
      snapshot still surfaces in heartbeat as the latest confirmed event.
    - `run_chat()` keeps those events in its recent-event window.
    - The proposals behind them stay `approved` and cannot be approved a second time.
    - A company's `stage` in `data/pipeline.yml` stays where the later event put it.

    Use this to recover a state file that got into a bad shape, not to undo an approval.
    """
    snapshot = home.versions / f"{version}.json"
    if not snapshot.exists():
        raise CareerError(f"version not found: {version}")
    state = read_json(snapshot, {})
    if not isinstance(state, dict):
        raise CareerError(f"invalid version snapshot: {version}")
    with vault_lock(home):  # PERSIST-005: must not race a concurrent approve()'s save_state
        home.write_state(state)
        append_jsonl(home.checkpoints, {"version": version, "restored_at": utc_now(), "state": state})
    return {"restored": True, "version": version, "state": state,
            "ledger_retained": True,
            "note": "State only. events.jsonl, proposals.jsonl and data/pipeline.yml are unchanged."}


def status(home: CareerVault) -> dict[str, Any]:
    state = home.load_state()
    profile = home.load_profile()
    return {"vault": str(home.path), "profile": {"track": profile.get("track"), "career_status": profile.get("career_status", "active"), "target_role": profile.get("target_role")}, "state": state, "event_count": len(read_jsonl(home.events)), "pending_proposals": sum(1 for row in read_jsonl(home.proposals) if row.get("status") == "pending"), "posting_count": len(read_jsonl(home.postings))}


def proposal_summary(proposal: dict[str, Any]) -> dict[str, Any]:
    """Expose proposal metadata without leaking event/report bodies."""
    event = proposal.get("event") if isinstance(proposal.get("event"), dict) else {}
    report = proposal.get("report") if isinstance(proposal.get("report"), dict) else {}
    return {
        "id": proposal.get("id"),
        "kind": proposal.get("kind"),
        "status": proposal.get("status"),
        "created_at": proposal.get("created_at"),
        "title": event.get("title") or report.get("title") or proposal.get("title"),
        "stage": event.get("stage") or report.get("stage") or proposal.get("stage"),
        "company": event.get("company") or proposal.get("company"),
    }


def list_proposals(home: CareerVault, *, include_all: bool = False, limit: int | None = None) -> dict[str, Any]:
    rows = read_jsonl(home.proposals)
    if not include_all:
        rows = [row for row in rows if row.get("status") == "pending"]
    rows = [row for _, row in sorted(enumerate(rows), key=lambda item: (str(item[1].get("created_at") or ""), item[0]), reverse=True)]
    if limit is not None:
        rows = rows[:limit]
    return {"mode": "proposals", "count": len(rows), "proposals": [proposal_summary(row) for row in rows]}


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
    context_proposal_parser = subparsers.add_parser(
        "propose-context",
        help="create an approval-gated proposal from a SELF_ANALYSIS_PROFILE YAML",
    )
    add_vault_argument(context_proposal_parser)
    context_proposal_parser.add_argument("--source", required=True, help="CWD-relative SELF_ANALYSIS_PROFILE YAML")
    return parser


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
                result = run_context(home, args.track, args.stage)
            elif args.command == "propose-context":
                result = propose_career_context(home, args.source)
            elif args.mode == "chat":
                message = args.message if args.message is not None else read_stdin_utf8().strip()
                if not message:
                    raise CareerError("chat requires --message or stdin")
                result = run_chat(home, skills_root, message, args.track)
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
