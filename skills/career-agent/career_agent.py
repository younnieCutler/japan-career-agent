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
import uuid
from pathlib import Path
from typing import Any, Iterable


TRACKS = {"shinsotsu", "chuto"}
EVENT_STATUSES = {"draft", "confirmed", "superseded"}
SHINSOTSU_STAGES = (
    "自己分析・就活軸",
    "学チカ・自己PR素材",
    "業界研究・企業研究",
    "ES・履歴書",
    "適性検査（SPI3）",
    "書類選考・面接",
    "内々定・内定・入社準備",
)
CHUTO_STAGES = (
    "自己分析・転職軸",
    "職務経歴書・自己PR",
    "業界研究・企業研究",
    "応募・書類選考",
    "面接",
    "内定・条件交渉",
    "退職・入社準備",
)
SKILL_BY_STAGE = {
    "自己分析・就活軸": "jiko-bunseki",
    "自己分析・転職軸": "jiko-bunseki",
    "学チカ・自己PR素材": "job-seeker-agent",
    "職務経歴書・自己PR": "job-seeker-agent",
    "業界研究・企業研究": "kigyou-bunseki",
    "ES・履歴書": "job-seeker-agent",
    "適性検査（SPI3）": "job-seeker-agent",
    "書類選考・面接": "job-seeker-agent",
    "応募・書類選考": "tenshoku-strategy",
    "面接": "job-seeker-agent",
    "内々定・内定・入社準備": "tenshoku-strategy",
    "内定・条件交渉": "tenshoku-strategy",
    "退職・入社準備": "tenshoku-strategy",
}
REFERENCE_BY_STAGE = {
    "自己分析・就活軸": ("references/questions.md",),
    "自己分析・転職軸": ("references/questions.md",),
    "学チカ・自己PR素材": ("references/shinsotsu.md",),
    "職務経歴書・自己PR": ("references/shokumukeireki-saigensei.md",),
    "業界研究・企業研究": ("references/frameworks.md",),
    "ES・履歴書": ("references/shinsotsu.md",),
    "適性検査（SPI3）": ("references/frameworks.md",),
    "書類選考・面接": ("references/mensetsu-rounds.md",),
    "応募・書類選考": ("references/senko-tracking.md",),
    "面接": ("references/mensetsu-rounds.md",),
    "内々定・内定・入社準備": ("references/naitei-taiou.md",),
    "内定・条件交渉": ("references/naitei-taiou.md",),
    "退職・入社準備": ("references/nyusha-teichaku.md",),
}
STAGE_ALIASES = {
    "자기분석": "self",
    "自己分析": "self",
    "자소서": "documents",
    "학チ카": "documents",
    "学チカ": "documents",
    "자기pr": "documents",
    "自己pr": "documents",
    "이력서": "documents",
    "履歴書": "documents",
    "職務経歴書": "documents",
    "es": "documents",
    "企業研究": "research",
    "기업 연구": "research",
    "면접": "interview",
    "面接": "interview",
    "내정": "offer",
    "内定": "offer",
    "퇴직": "exit",
    "입사": "exit",
    "転職": "chuto",
    "중途": "chuto",
    "신졸": "shinsotsu",
    "新卒": "shinsotsu",
}
REQUIRED_EVENT_FIELDS = (
    "id",
    "track",
    "stage",
    "type",
    "occurred_at",
    "title",
    "summary",
    "evidence",
    "source",
    "next_action",
    "deadline",
    "status",
)
NUMERIC_CLAIM = re.compile(r"(?<![A-Za-z])[+-]?\d+(?:[.,]\d+)?\s*(?:%|％|명|人|건|件|배|倍|만|万円|원|円)?")
DATE_VALUE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T[^Z]+Z)?$")


class CareerError(ValueError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today() -> dt.date:
    return dt.date.today()


def as_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        raise CareerError(f"invalid JSON: {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    # ponytail: linear JSONL scan; move to SQLite FTS5 when event volume makes it slow.
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CareerError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
        if isinstance(row, dict):
            rows.append(row)
    return rows


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
    shinsotsu = ("新卒", "신졸", "학チカ", "学チカ", "졸업", "graduat", "spi3", "学生")
    chuto = ("中途", "중途", "転職", "이직", "직장", "職務経歴書", "career change", "mid-career")
    if any(term.lower() in lowered for term in shinsotsu):
        return "shinsotsu"
    if any(term.lower() in lowered for term in chuto):
        return "chuto"
    return None


def stage_for(message: str, track: str) -> str:
    for term, alias in STAGE_ALIASES.items():
        if term.lower() not in message.lower():
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
    return (CHUTO_STAGES if track == "chuto" else SHINSOTSU_STAGES)[0]


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


def validate_event(event: dict[str, Any], *, for_confirmation: bool = False) -> None:
    missing = [field for field in REQUIRED_EVENT_FIELDS if field not in event]
    if missing:
        raise CareerError(f"event missing fields: {', '.join(missing)}")
    if event["track"] not in TRACKS:
        raise CareerError("event.track must be shinsotsu or chuto")
    if event["status"] not in EVENT_STATUSES:
        raise CareerError("event.status must be draft, confirmed, or superseded")
    for field in ("id", "stage", "type", "title", "summary", "source"):
        if not isinstance(event[field], str) or not event[field].strip():
            raise CareerError(f"event.{field} must be a non-empty string")
    if not isinstance(event["evidence"], list):
        raise CareerError("event.evidence must be a list")
    if event["deadline"] is not None and not isinstance(event["deadline"], str):
        raise CareerError("event.deadline must be an ISO date or null")
    if event["deadline"] and not DATE_VALUE.match(event["deadline"]):
        raise CareerError("event.deadline must use YYYY-MM-DD")
    if for_confirmation or event["status"] == "confirmed":
        if not event["evidence"]:
            if NUMERIC_CLAIM.search(event["summary"] + " " + event["title"]):
                raise CareerError("numeric claim is not present in evidence; event cannot be confirmed")
            raise CareerError("confirmed events require evidence; unsupported claims stay drafts")
        claims = NUMERIC_CLAIM.findall(event["summary"] + " " + event["title"])
        evidence_text = as_text(event["evidence"])
        if claims and not all(claim in evidence_text for claim in claims):
            raise CareerError("numeric claim is not present in evidence; event cannot be confirmed")


def make_event(message: str, track: str, stage: str, *, status: str = "draft") -> dict[str, Any]:
    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    event = {
        "id": event_id,
        "track": track,
        "stage": stage,
        "type": "user_report",
        "occurred_at": utc_now(),
        "title": "사용자 입력 기반 경력 이벤트" if language_for(message) == "ko" else "User-reported career event",
        "summary": message.strip(),
        "evidence": [],
        "source": "user_message",
        "next_action": "근거를 확인한 뒤 이벤트 확정" if language_for(message) == "ko" else "Confirm evidence before saving",
        "deadline": None,
        "status": status,
    }
    validate_event(event)
    return event


class CareerHome:
    def __init__(self, path: Path):
        self.path = path.expanduser().resolve()
        self.events = self.path / "events.jsonl"
        self.state = self.path / "state.json"
        self.checkpoints = self.path / "checkpoints.jsonl"
        self.trajectories = self.path / "trajectories.jsonl"
        self.proposals = self.path / "proposals.jsonl"
        self.postings = self.path / "postings.jsonl"
        self.versions = self.path / "versions"
        self.path.mkdir(parents=True, exist_ok=True)

    def load_state(self) -> dict[str, Any]:
        state = read_json(self.state, {})
        if not state:
            return {
                "track": None,
                "stage": None,
                "open_actions": [],
                "deadlines": [],
                "applications": [],
                "last_event_id": None,
                "updated_at": None,
                "version": None,
            }
        return state

    def save_state(self, state: dict[str, Any]) -> str:
        version = f"v-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
        state = dict(state)
        state["version"] = version
        state["updated_at"] = utc_now()
        write_json(self.state, state)
        self.versions.mkdir(parents=True, exist_ok=True)
        write_json(self.versions / f"{version}.json", state)
        append_jsonl(self.checkpoints, {"version": version, "created_at": utc_now(), "state": state})
        return version

    def append_trajectory(self, trajectory: dict[str, Any]) -> None:
        append_jsonl(self.trajectories, trajectory)

    def add_proposal(self, proposal: dict[str, Any]) -> None:
        append_jsonl(self.proposals, proposal)

    def replace_proposal(self, proposal_id: str, **changes: Any) -> dict[str, Any]:
        rows = read_jsonl(self.proposals)
        for row in rows:
            if row.get("id") == proposal_id:
                row.update(changes)
                row["updated_at"] = utc_now()
                self.proposals.write_text("".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in rows), encoding="utf-8")
                return row
        raise CareerError(f"proposal not found: {proposal_id}")


def apply_event_to_state(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    next_state = dict(state)
    next_state["track"] = event["track"]
    next_state["stage"] = event["stage"]
    next_state["last_event_id"] = event["id"]
    actions = list(next_state.get("open_actions", []))
    if event.get("next_action"):
        actions.append({"text": event["next_action"], "event_id": event["id"], "stage": event["stage"]})
    next_state["open_actions"] = actions[-10:]
    if event.get("deadline"):
        deadlines = [item for item in next_state.get("deadlines", []) if item.get("event_id") != event["id"]]
        deadlines.append({"date": event["deadline"], "event_id": event["id"], "title": event["title"], "status": "open"})
        next_state["deadlines"] = sorted(deadlines, key=lambda item: item["date"])
    return next_state


def load_posting_records(source: str | None) -> list[dict[str, Any]]:
    if source:
        path = Path(source).expanduser()
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = sys.stdin.read().strip()
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
    company = str(posting.get("company") or posting.get("company_name") or "").strip().lower()
    role = str(posting.get("role") or posting.get("job_title") or "").strip().lower()
    raw = url or f"{company}|{role}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def normalize_posting(posting: dict[str, Any]) -> dict[str, Any]:
    url = str(posting.get("url") or posting.get("source_url") or "").strip()
    if not url.startswith(("https://", "http://")):
        raise CareerError("discover postings require an original http(s) URL")
    return {
        "company": str(posting.get("company") or posting.get("company_name") or "不明").strip(),
        "role": str(posting.get("role") or posting.get("job_title") or "不明").strip(),
        "graduation_year": posting.get("graduation_year"),
        "target": posting.get("target") or posting.get("audience"),
        "deadline": posting.get("deadline"),
        "original_url": url,
        "checked_at": posting.get("checked_at") or utc_now(),
        "dedupe_key": posting_key(posting),
        "status": "candidate",
        "source": "public_search_input",
    }


def choose_actions(home: CareerHome) -> list[dict[str, Any]]:
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
            actions.append({"text": f"마감 확인: {deadline.get('title', 'deadline')}", "event_id": deadline.get("event_id"), "stage": state.get("stage"), "estimated_minutes": 15, "deadline": deadline["date"], "requires_confirmation": True, "reason": "deadline"})
    for event in reversed(events):
        if event.get("status") == "confirmed" and event.get("next_action"):
            action = {"text": event["next_action"], "event_id": event["id"], "stage": event["stage"], "estimated_minutes": 30, "deadline": event.get("deadline"), "requires_confirmation": True, "reason": "latest confirmed event"}
            if action["event_id"] not in {item.get("event_id") for item in actions}:
                actions.append(action)
    return actions[:3]


def run_chat(home: CareerHome, skills_root: Path, message: str, requested_track: str | None) -> dict[str, Any]:
    state = home.load_state()
    recent_events = read_jsonl(home.events)[-5:]
    track = infer_track(message, requested_track) or state.get("track")
    if not track:
        trajectory = {
            "id": f"traj-{uuid.uuid4().hex[:12]}",
            "created_at": utc_now(),
            "mode": "chat",
            "observe": {"track": state.get("track"), "stage": state.get("stage"), "deadlines": state.get("deadlines", []), "recent_events": recent_events, "message": message},
            "plan": {"goal": "resolve track before routing"},
            "act": {"proposal": None},
            "verify": {"track": "ambiguous", "external_side_effect": False},
            "correct": {"retry_count": 0, "needs_user_confirmation": True},
            "persist": {"trajectory_only": True},
        }
        home.append_trajectory(trajectory)
        return {"mode": "chat", "language": language_for(message), "needs_confirmation": True, "question": "track must be explicit: shinsotsu or chuto", "saved": str(home.trajectories)}
    stage = stage_for(message, track)
    event = make_event(message, track, stage)
    proposal = {
        "id": f"proposal-{uuid.uuid4().hex[:12]}",
        "kind": "event",
        "status": "pending",
        "created_at": utc_now(),
        "event": event,
    }
    home.add_proposal(proposal)
    trajectory = {
        "id": f"traj-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "mode": "chat",
        "observe": {"track": state.get("track"), "stage": state.get("stage"), "deadlines": state.get("deadlines", []), "recent_events": recent_events, "message": message},
        "plan": {"track": track, "stage": stage, "goal": "route and propose a grounded event", "next_action": event["next_action"]},
        "act": {"proposal_id": proposal["id"], "skill": skill_context(skills_root, stage)},
        "verify": {"event_schema": "valid", "external_side_effect": False},
        "correct": {"retry_count": 0, "needs_user_confirmation": True},
        "persist": {"proposal_id": proposal["id"]},
    }
    home.append_trajectory(trajectory)
    return {"mode": "chat", "language": language_for(message), "track": track, "stage": stage, "skill": skill_context(skills_root, stage), "proposal": proposal, "saved": str(home.proposals)}


def run_heartbeat(home: CareerHome) -> dict[str, Any]:
    state = home.load_state()
    actions = choose_actions(home)
    report = {
        "id": f"heartbeat-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "track": state.get("track"),
        "stage": state.get("stage"),
        "actions": actions,
        "limit": 3,
        "requires_confirmation": True,
    }
    home.add_proposal({"id": report["id"], "kind": "heartbeat", "status": "pending", "created_at": report["created_at"], "report": report})
    home.append_trajectory({"id": f"traj-{uuid.uuid4().hex[:12]}", "created_at": utc_now(), "mode": "heartbeat", "observe": state, "plan": {"goal": "select at most three grounded actions"}, "act": report, "verify": {"action_count": len(actions), "max": 3}, "correct": {"retry_count": 0}, "persist": {"proposal_id": report["id"]}})
    return report


def run_discover(home: CareerHome, source: str | None) -> dict[str, Any]:
    incoming = [normalize_posting(item) for item in load_posting_records(source)]
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
    result = {"mode": "discover", "found": len(incoming), "added": len(added), "duplicates": len(incoming) - len(added), "postings": added, "saved": str(home.postings), "auto_apply": False}
    home.add_proposal({"id": f"discover-{uuid.uuid4().hex[:12]}", "kind": "posting_candidates", "status": "pending", "created_at": utc_now(), "result": result})
    home.append_trajectory({"id": f"traj-{uuid.uuid4().hex[:12]}", "created_at": utc_now(), "mode": "discover", "observe": {"source": source, "count": len(incoming)}, "plan": {"goal": "normalize public posting candidates and deduplicate"}, "act": {"added": len(added)}, "verify": {"original_urls_preserved": all(item["original_url"].startswith(("http://", "https://")) for item in added), "auto_apply": False}, "correct": {"retry_count": 0}, "persist": {"postings": str(home.postings)}})
    return result


def approve(home: CareerHome, proposal_id: str, evidence: list[str] | None = None, deadline: str | None = None) -> dict[str, Any]:
    proposal = next((row for row in read_jsonl(home.proposals) if row.get("id") == proposal_id), None)
    if not proposal:
        raise CareerError(f"proposal not found: {proposal_id}")
    if proposal.get("status") != "pending":
        raise CareerError(f"proposal is not pending: {proposal_id}")
    if proposal.get("kind") == "event":
        event = dict(proposal["event"])
        if evidence is not None:
            event["evidence"] = evidence
        if deadline is not None:
            event["deadline"] = deadline
        validate_event(event, for_confirmation=True)
        event["status"] = "confirmed"
        append_jsonl(home.events, event)
        state = apply_event_to_state(home.load_state(), event)
        version = home.save_state(state)
        updated = home.replace_proposal(proposal_id, status="approved", approved_at=utc_now(), version=version)
        return {"approved": True, "event": event, "version": version, "proposal": updated}
    updated = home.replace_proposal(proposal_id, status="approved", approved_at=utc_now())
    return {"approved": True, "proposal": updated, "applied": False, "message": "Only event proposals change the local ledger; skill changes remain offline proposals."}


def rollback(home: CareerHome, version: str) -> dict[str, Any]:
    snapshot = home.versions / f"{version}.json"
    if not snapshot.exists():
        raise CareerError(f"version not found: {version}")
    state = read_json(snapshot, {})
    if not isinstance(state, dict):
        raise CareerError(f"invalid version snapshot: {version}")
    write_json(home.state, state)
    append_jsonl(home.checkpoints, {"version": version, "rolled_back_at": utc_now(), "state": state})
    return {"rolled_back": True, "version": version, "state": state}


def status(home: CareerHome) -> dict[str, Any]:
    state = home.load_state()
    return {"home": str(home.path), "state": state, "event_count": len(read_jsonl(home.events)), "pending_proposals": sum(1 for row in read_jsonl(home.proposals) if row.get("status") == "pending"), "posting_count": len(read_jsonl(home.postings))}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local-first Japan career agent runtime")
    parser.add_argument("--home", default=os.environ.get("CAREER_HOME"), help="career state directory; defaults to ./career-home")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--mode", choices=("chat", "heartbeat", "discover"), required=True)
    run.add_argument("--message")
    run.add_argument("--track", choices=sorted(TRACKS))
    run.add_argument("--source", help="JSON file for discover; stdin is used when omitted")
    subparsers.add_parser("status")
    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("proposal_id")
    approve_parser.add_argument("--evidence", action="append", help="evidence for an event; repeat for multiple sources")
    approve_parser.add_argument("--deadline", help="confirmed event deadline in YYYY-MM-DD")
    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("version")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    home = CareerHome(Path(args.home or (Path.cwd() / "career-home")))
    skills_root = Path(__file__).resolve().parent.parent
    try:
        if args.command == "status":
            result = status(home)
        elif args.command == "approve":
            result = approve(home, args.proposal_id, args.evidence, args.deadline)
        elif args.command == "rollback":
            result = rollback(home, args.version)
        elif args.mode == "chat":
            message = args.message if args.message is not None else sys.stdin.read().strip()
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
