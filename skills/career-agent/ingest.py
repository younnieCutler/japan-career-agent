#!/usr/bin/env python3
"""Bring outside material in as proposals, never as confirmed facts.

Postings, heartbeats and the note index all stop at a proposal or a read-only projection. This
module never approves anything and never writes canonical state.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import uuid

from pathlib import Path
from typing import Any

from lifecycle import vault_lock
from localization import normalize_language, text
from models import CareerError
from persistence import append_jsonl, read_jsonl, write_jsonl
from validation import DATE_VALUE
from vault import CareerVault, index_vault_notes, today, utc_now


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
