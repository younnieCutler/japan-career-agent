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
import tomllib
import uuid
from pathlib import Path
from typing import Any, Iterable


TRACKS = {"shinsotsu", "chuto"}
EVENT_STATUSES = {"draft", "confirmed", "superseded"}
CAREER_STATUSES = {"active", "confirmed", "onboarding"}
VAULT_DIRECTORIES = (
    "00-control",
    "01-capture",
    "02-state",
    "03-active",
    "04-evidence",
    "05-playbooks",
    "06-reference",
    "07-archive",
)
CONTEXT_KINDS = {"active", "evidence", "playbook", "reference"}
TRUSTED_SOURCE_TYPES = {"official", "personal_evidence", "curated_practice"}
REQUIRED_CONTEXT_METADATA = {"agent_read", "agent_scope", "status", "source_type", "reviewed_on"}
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
    "応募・書類選考": "matching-simulator",
    "面接": "job-seeker-agent",
    "内々定・内定・入社準備": "job-seeker-agent",
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
    "가쿠치카": "documents",
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
    "flow_phase",
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
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]+)?\]\]")
IGNORED_VAULT_DIRS = {".git", ".obsidian", ".career-agent", "career-home", "__pycache__"}
FLOW_REFERENCE = Path(__file__).resolve().parent / "references" / "japan-career-flow.toml"


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


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def read_toml(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            value = tomllib.load(stream)
    except FileNotFoundError:
        return {} if default is None else default
    except tomllib.TOMLDecodeError as exc:
        raise CareerError(f"invalid TOML: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CareerError(f"TOML root must be a table: {path}")
    return value


def toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list) and all(not isinstance(item, dict) for item in value):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    raise CareerError(f"unsupported TOML value: {type(value).__name__}")


def write_toml(path: Path, values: dict[str, Any]) -> None:
    """Write the small, flat TOML subset used by the vault contract."""
    lines: list[str] = []
    tables: list[tuple[str, dict[str, Any]]] = []
    table_arrays: list[tuple[str, list[dict[str, Any]]]] = []
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, dict):
            tables.append((key, value))
        elif isinstance(value, list) and all(isinstance(item, dict) for item in value):
            if value:
                table_arrays.append((key, value))
            else:
                lines.append(f"{key} = []")
        else:
            lines.append(f"{key} = {toml_value(value)}")
    for key, table in tables:
        lines.extend(("", f"[{key}]"))
        lines.extend(f"{name} = {toml_value(item)}" for name, item in table.items() if item is not None)
    for key, rows in table_arrays:
        for row in rows:
            lines.extend(("", f"[[{key}]]"))
            lines.extend(f"{name} = {toml_value(item)}" for name, item in row.items() if item is not None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    metadata: dict[str, Any] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, raw_value = line.partition(":")
        if not separator or not key.strip():
            continue
        value = raw_value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = value[1:-1].split(",") if value[1:-1].strip() else []
            metadata[key.strip()] = [item.strip().strip("'\"") for item in items]
        elif value.lower() in {"true", "false"}:
            metadata[key.strip()] = value.lower() == "true"
        else:
            metadata[key.strip()] = value.strip("'\"")
    return metadata


def note_kind(relative_path: Path) -> str:
    if not relative_path.parts:
        return "active"
    root = relative_path.parts[0]
    if root in {"07-archive", "06-archives"}:
        return "archive"
    if root in {"01-capture", "01-inbox"}:
        return "capture"
    if root in {"06-reference", "05-resources"}:
        return "reference"
    if root == "05-playbooks":
        return "playbook"
    if root == "04-evidence":
        return "evidence"
    if root == "03-active":
        return "active"
    if relative_path.parts[:3] == ("04-areas", "Career", "career-agent"):
        return "agent"
    return "active"


def index_vault_notes(vault: Path, *, include_archives: bool = False) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for path in sorted(vault.rglob("*.md")):
        relative_path = path.relative_to(vault)
        if path.name == "AGENTS.md":
            continue
        if any(part in IGNORED_VAULT_DIRS or part.startswith(".") for part in relative_path.parts[:-1]):
            continue
        if not relative_path.parts or relative_path.parts[0] not in VAULT_DIRECTORIES:
            continue
        if relative_path.parts and relative_path.parts[0] in {"00-control", "02-state"}:
            continue
        kind = note_kind(relative_path)
        if kind == "capture" or (not include_archives and kind == "archive"):
            continue
        text = path.read_text(encoding="utf-8")
        metadata = parse_frontmatter(text)
        notes.append(
            {
                "path": relative_path.as_posix(),
                "kind": kind,
                "title": metadata.get("title") or path.stem,
                "date": metadata.get("date"),
                "tags": metadata.get("tags", []),
                "description": metadata.get("description"),
                "source": metadata.get("source"),
                "agent_read": metadata.get("agent_read", False),
                "agent_scope": metadata.get("agent_scope"),
                "agent_stage": metadata.get("agent_stage"),
                "status": metadata.get("status"),
                "source_type": metadata.get("source_type"),
                "reviewed_on": metadata.get("reviewed_on"),
                "expires_on": metadata.get("expires_on"),
                "headings": sorted(set(HEADING.findall(text))),
                "wikilinks": sorted(set(link.strip() for link in WIKILINK.findall(text))),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    return notes


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


def load_flow_reference() -> dict[str, Any]:
    reference = read_toml(FLOW_REFERENCE)
    if not reference.get("metadata") or not reference.get("shinsotsu") or not reference.get("chuto"):
        raise CareerError(f"invalid career flow reference: {FLOW_REFERENCE}")
    return reference


def flow_phase_ids(reference: dict[str, Any], track: str) -> set[str]:
    phases = reference.get(track, {}).get("phases", [])
    return {str(phase.get("id")) for phase in phases if isinstance(phase, dict) and phase.get("id")}


def flow_phase_for(message: str, track: str, state: dict[str, Any], profile: dict[str, Any], reference: dict[str, Any]) -> str:
    allowed = flow_phase_ids(reference, track)
    for value in (profile.get("flow_phase"), state.get("flow_phase")):
        if value in allowed:
            return str(value)
    lowered = message.lower()
    if track == "shinsotsu":
        signals = (
            (("여름", "summer", "夏", "インターン"), "summer_entry"),
            (("가을", "겨울", "autumn", "winter", "秋", "冬", "早期選考"), "autumn_winter_early"),
            (("본선", "공식", "official", "本選考"), "official_selection"),
            (("내정", "입사", "内々定", "内定", "入社"), "offer_onboarding"),
        )
    else:
        signals = (
            (("職務経歴書", "경력기술서", "이력서", "resume"), "documents"),
            (("지원", "応募", "서류", "書類"), "application"),
            (("면접", "面接"), "interview"),
            (("오퍼", "연봉", "内定", "オファー", "条件"), "offer"),
            (("퇴직", "입사", "退職", "入社"), "exit_onboarding"),
        )
    for terms, phase in signals:
        if any(term.lower() in lowered for term in terms) and phase in allowed:
            return phase
    if track == "shinsotsu" and state.get("stage") == SHINSOTSU_STAGES[-1] and "offer_onboarding" in allowed:
        return "offer_onboarding"
    return "preparation"


def metadata_values(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    if isinstance(value, str) and value.strip():
        return {value.strip()}
    return set()


def context_eligible(note: dict[str, Any], track: str, stage: str) -> bool:
    if note.get("kind") not in CONTEXT_KINDS or note.get("agent_read") is not True:
        return False
    if note.get("status") != "verified" or note.get("source_type") not in TRUSTED_SOURCE_TYPES:
        return False
    if track not in metadata_values(note.get("agent_scope")) | {"both"}:
        return False
    stages = metadata_values(note.get("agent_stage"))
    return not stages or stage in stages or "all" in stages


def select_context(vault: Path, track: str, stage: str) -> list[dict[str, Any]]:
    """Return metadata only; note bodies are deliberately never persisted or returned."""
    selected: list[dict[str, Any]] = []
    for note in index_vault_notes(vault):
        if not context_eligible(note, track, stage):
            continue
        selected.append(
            {
                "path": note["path"],
                "kind": note["kind"],
                "title": note["title"],
                "description": note["description"],
                "headings": note["headings"],
                "source_type": note["source_type"],
                "selected_for": {"track": track, "stage": stage},
            }
        )
    return selected[:5]


def validate_event(event: dict[str, Any], *, for_confirmation: bool = False) -> None:
    missing = [field for field in REQUIRED_EVENT_FIELDS if field not in event]
    if missing:
        raise CareerError(f"event missing fields: {', '.join(missing)}")
    if event["track"] not in TRACKS:
        raise CareerError("event.track must be shinsotsu or chuto")
    if event["status"] not in EVENT_STATUSES:
        raise CareerError("event.status must be draft, confirmed, or superseded")
    for field in ("id", "stage", "flow_phase", "type", "title", "summary", "source"):
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


def make_event(message: str, track: str, stage: str, flow_phase: str, *, status: str = "draft") -> dict[str, Any]:
    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    language = language_for(message)
    title = {
        "ko": "사용자 입력 기반 경력 이벤트",
        "ja": "ユーザー入力に基づくキャリアイベント",
        "en": "User-reported career event",
    }[language]
    next_action = {
        "ko": "근거를 확인한 뒤 이벤트 확정",
        "ja": "根拠を確認してからイベントを確定する",
        "en": "Confirm evidence before saving",
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
        "next_action": next_action,
        "deadline": None,
        "status": status,
    }
    validate_event(event)
    return event


def default_state() -> dict[str, Any]:
    return {
        "track": None,
        "stage": None,
        "flow_phase": None,
        "career_status": "active",
        "open_actions": [],
        "deadlines": [],
        "applications": [],
        "last_event_id": None,
        "updated_at": None,
        "version": None,
    }


def normalized_state(value: dict[str, Any]) -> dict[str, Any]:
    state = default_state()
    state.update({key: item for key, item in value.items() if key in state})
    for key in ("track", "stage", "flow_phase", "last_event_id", "updated_at", "version"):
        if state.get(key) == "":
            state[key] = None
    return state


def profile_template() -> str:
    return """# Fill the values before running chat. Do not put raw resumes or transcripts here.\n# track = \"shinsotsu\"  # shinsotsu or chuto\n# graduation_year = 2027  # required for shinsotsu (university or graduate school)\n# target_role = \"LLMOps Engineer\"\ncareer_status = \"active\"  # active, confirmed, or onboarding\nlanguage = \"ko\"\n"""


def policy_template() -> str:
    return """# Career Agent Policy\n\n- The agent reads `00-control` and `02-state` as operating state.\n- It selects at most five verified notes from `03-active`, `04-evidence`, `05-playbooks`, and `06-reference`.\n- `01-capture` and `07-archive` are never automatic context.\n- User approval and evidence are required before an event becomes confirmed.\n- The agent never applies, logs in, sends messages, bypasses CAPTCHA, or edits installed skills.\n"""


class CareerVault:
    def __init__(self, path: Path):
        self.path = path.expanduser().resolve()
        self.control = self.path / "00-control"
        self.state_dir = self.path / "02-state"
        self.runtime = self.path / ".career-agent"
        self.profile = self.control / "career-profile.toml"
        self.policy = self.control / "agent-policy.md"
        self.state_toml = self.state_dir / "career-state.toml"
        self.events = self.state_dir / "events.jsonl"
        self.checkpoints = self.state_dir / "checkpoints.jsonl"
        self.trajectories = self.state_dir / "trajectories.jsonl"
        self.proposals = self.state_dir / "proposals.jsonl"
        self.postings = self.state_dir / "postings.jsonl"
        self.state = self.runtime / "state.json"
        self.vault_index = self.runtime / "vault-index.jsonl"
        self.versions = self.runtime / "versions"

    def initialized(self) -> bool:
        return self.profile.exists() and self.policy.exists() and self.state_toml.exists()

    def require_initialized(self) -> None:
        if not self.initialized():
            raise CareerError(f"career vault is not initialized: {self.path}; run init --vault {self.path}")

    def ensure_runtime(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.runtime.mkdir(parents=True, exist_ok=True)

    def load_profile(self) -> dict[str, Any]:
        return read_toml(self.profile)

    def load_state(self) -> dict[str, Any]:
        # TOML is the human-editable source of truth; JSON is only a cache and snapshot format.
        state = read_toml(self.state_toml)
        if state:
            return normalized_state(state)
        return normalized_state(read_json(self.state, {}))

    def write_state(self, state: dict[str, Any]) -> None:
        self.ensure_runtime()
        normalized = normalized_state(state)
        write_json(self.state, normalized)
        write_toml(self.state_toml, normalized)

    def save_state(self, state: dict[str, Any]) -> str:
        version = f"v-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
        state = normalized_state(state)
        state["version"] = version
        state["updated_at"] = utc_now()
        self.write_state(state)
        self.versions.mkdir(parents=True, exist_ok=True)
        write_json(self.versions / f"{version}.json", state)
        append_jsonl(self.checkpoints, {"version": version, "created_at": utc_now(), "state": state})
        return version

    def append_trajectory(self, trajectory: dict[str, Any]) -> None:
        self.ensure_runtime()
        append_jsonl(self.trajectories, trajectory)

    def add_proposal(self, proposal: dict[str, Any]) -> None:
        self.ensure_runtime()
        append_jsonl(self.proposals, proposal)

    def replace_proposal(self, proposal_id: str, **changes: Any) -> dict[str, Any]:
        rows = read_jsonl(self.proposals)
        for row in rows:
            if row.get("id") == proposal_id:
                row.update(changes)
                row["updated_at"] = utc_now()
                write_jsonl(self.proposals, rows)
                return row
        raise CareerError(f"proposal not found: {proposal_id}")


def initialize_vault(path: Path) -> dict[str, Any]:
    vault = CareerVault(path)
    created: list[str] = []
    for directory in VAULT_DIRECTORIES:
        target = vault.path / directory
        if not target.exists():
            target.mkdir(parents=True)
            created.append(str(target.relative_to(vault.path)))
    vault.runtime.mkdir(parents=True, exist_ok=True)
    templates = {
        vault.profile: profile_template(),
        vault.policy: policy_template(),
    }
    for target, content in templates.items():
        if not target.exists():
            target.write_text(content, encoding="utf-8")
            created.append(str(target.relative_to(vault.path)))
    if not vault.state_toml.exists():
        write_toml(vault.state_toml, default_state())
        created.append(str(vault.state_toml.relative_to(vault.path)))
    return {"initialized": True, "vault": str(vault.path), "created": created, "next": "Fill 00-control/career-profile.toml, then run doctor --vault <path>."}


def apply_event_to_state(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    next_state = dict(state)
    next_state["track"] = event["track"]
    next_state["stage"] = event["stage"]
    next_state["flow_phase"] = event["flow_phase"]
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


def doctor(vault: CareerVault) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
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
    return {
        "mode": "doctor",
        "vault": str(vault.path),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "safe_stop": bool(errors),
    }


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
    if track == "shinsotsu" and not isinstance(profile.get("graduation_year"), int):
        home.append_trajectory(
            {
                "id": f"traj-{uuid.uuid4().hex[:12]}",
                "created_at": utc_now(),
                "mode": "chat",
                "observe": {"track": track, "profile_has_graduation_year": False, "message": message},
                "plan": {"goal": "collect required shinsotsu graduation year before proposing an event"},
                "act": {"proposal": None},
                "verify": {"safe_stop": True, "external_side_effect": False},
                "correct": {"retry_count": 0, "needs_user_confirmation": True},
                "persist": {"trajectory_only": True},
            }
        )
        return {
            "mode": "chat",
            "language": language_for(message),
            "track": track,
            "needs_confirmation": True,
            "question": "profile.graduation_year is required for shinsotsu before an event proposal can be created",
            "saved": str(home.trajectories),
        }
    stage = stage_for(message, track)
    reference = load_flow_reference()
    flow_phase = flow_phase_for(message, track, state, profile, reference)
    context = select_context(home.path, track, stage)
    event = make_event(message, track, stage, flow_phase)
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
        "plan": {"track": track, "stage": stage, "flow_phase": flow_phase, "goal": "route and propose a grounded event", "next_action": event["next_action"]},
        "act": {"proposal_id": proposal["id"], "skill": skill_context(skills_root, stage), "context_count": len(context)},
        "verify": {"event_schema": "valid", "context_is_metadata_only": True, "external_side_effect": False},
        "correct": {"retry_count": 0, "needs_user_confirmation": True},
        "persist": {"proposal_id": proposal["id"]},
    }
    home.append_trajectory(trajectory)
    return {"mode": "chat", "language": language_for(message), "track": track, "stage": stage, "flow_phase": flow_phase, "skill": skill_context(skills_root, stage), "context": context, "proposal": proposal, "saved": str(home.proposals)}


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
    home.add_proposal({"id": report["id"], "kind": "heartbeat", "status": "pending", "created_at": report["created_at"], "report": report})
    home.append_trajectory({"id": f"traj-{uuid.uuid4().hex[:12]}", "created_at": utc_now(), "mode": "heartbeat", "observe": state, "plan": {"goal": "select at most three grounded actions"}, "act": report, "verify": {"action_count": len(actions), "max": 3}, "correct": {"retry_count": 0}, "persist": {"proposal_id": report["id"]}})
    return report


def run_discover(home: CareerVault, source: str | None) -> dict[str, Any]:
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


def run_index(home: CareerVault, *, include_archives: bool = False) -> dict[str, Any]:
    notes = index_vault_notes(home.path, include_archives=include_archives)
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
    profile_keys = ("track", "career_status", "target_role", "start_date", "graduation_year", "language", "flow_phase")
    return {
        "mode": "context",
        "vault": str(home.path),
        "profile": {key: profile[key] for key in profile_keys if key in profile and profile[key] not in (None, "")},
        "state": state,
        "context": select_context(home.path, track, stage) if stage else [],
        "read_only": True,
        "note_bodies_included": False,
    }


def approve(home: CareerVault, proposal_id: str, evidence: list[str] | None = None, deadline: str | None = None) -> dict[str, Any]:
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


def rollback(home: CareerVault, version: str) -> dict[str, Any]:
    snapshot = home.versions / f"{version}.json"
    if not snapshot.exists():
        raise CareerError(f"version not found: {version}")
    state = read_json(snapshot, {})
    if not isinstance(state, dict):
        raise CareerError(f"invalid version snapshot: {version}")
    home.write_state(state)
    append_jsonl(home.checkpoints, {"version": version, "rolled_back_at": utc_now(), "state": state})
    return {"rolled_back": True, "version": version, "state": state}


def status(home: CareerVault) -> dict[str, Any]:
    state = home.load_state()
    profile = home.load_profile()
    return {"vault": str(home.path), "profile": {"track": profile.get("track"), "career_status": profile.get("career_status", "active"), "target_role": profile.get("target_role")}, "state": state, "event_count": len(read_jsonl(home.events)), "pending_proposals": sum(1 for row in read_jsonl(home.proposals) if row.get("status") == "pending"), "posting_count": len(read_jsonl(home.postings))}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local-first Japan career agent runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_vault_argument(command: argparse.ArgumentParser) -> None:
        command.add_argument("--vault", default=os.environ.get("CAREER_VAULT"), help="initialized Career Vault; falls back to CAREER_VAULT")

    init_parser = subparsers.add_parser("init")
    add_vault_argument(init_parser)
    doctor_parser = subparsers.add_parser("doctor")
    add_vault_argument(doctor_parser)
    run = subparsers.add_parser("run")
    add_vault_argument(run)
    run.add_argument("--mode", choices=("chat", "heartbeat", "discover"), required=True)
    run.add_argument("--message")
    run.add_argument("--track", choices=sorted(TRACKS))
    run.add_argument("--source", help="JSON file for discover; stdin is used when omitted")
    status_parser = subparsers.add_parser("status")
    add_vault_argument(status_parser)
    approve_parser = subparsers.add_parser("approve")
    add_vault_argument(approve_parser)
    approve_parser.add_argument("proposal_id")
    approve_parser.add_argument("--evidence", action="append", help="evidence for an event; repeat for multiple sources")
    approve_parser.add_argument("--deadline", help="confirmed event deadline in YYYY-MM-DD")
    rollback_parser = subparsers.add_parser("rollback")
    add_vault_argument(rollback_parser)
    rollback_parser.add_argument("version")
    index_parser = subparsers.add_parser("index")
    add_vault_argument(index_parser)
    index_parser.add_argument("--include-archives", action="store_true", help="include 06-archives in the index")
    context_parser = subparsers.add_parser("context")
    add_vault_argument(context_parser)
    context_parser.add_argument("--track", choices=sorted(TRACKS), help="override the profile/state track")
    context_parser.add_argument("--stage", help="select verified notes for this exact stage")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    skills_root = Path(__file__).resolve().parent.parent
    try:
        if not args.vault:
            raise CareerError("--vault or CAREER_VAULT is required; the runtime never defaults to the current directory")
        home = CareerVault(Path(args.vault))
        if args.command == "init":
            result = initialize_vault(home.path)
        else:
            home.require_initialized()
            if args.command == "doctor":
                result = doctor(home)
            elif args.command == "status":
                result = status(home)
            elif args.command == "approve":
                result = approve(home, args.proposal_id, args.evidence, args.deadline)
            elif args.command == "rollback":
                result = rollback(home, args.version)
            elif args.command == "index":
                result = run_index(home, include_archives=args.include_archives)
            elif args.command == "context":
                result = run_context(home, args.track, args.stage)
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
