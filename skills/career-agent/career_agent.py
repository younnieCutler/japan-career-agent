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
import tempfile
import tomllib
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
UNTRUSTED_DATA_MARKER = "untrusted_career_data"
CAREER_CONTEXT_FIELDS = ("career_anchors", "career_theme", "energy_map", "career_values")
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
# Agent stage → the 0–7 Japan market stage map (AGENTS.md § Market Stage Map), which is what
# data/pipeline.yml stores per company. The chuto tuple maps 1:1; the shinsotsu tuple is a
# 就活 flow, so ES・履歴書 is document prep (1) and 適性検査 is part of the screening gate (3).
PIPELINE_STAGE = {
    "自己分析・就活軸": 0,
    "自己分析・転職軸": 0,
    "学チカ・自己PR素材": 1,
    "職務経歴書・自己PR": 1,
    "ES・履歴書": 1,
    "業界研究・企業研究": 2,
    "応募・書類選考": 3,
    "適性検査（SPI3）": 3,
    "面接": 4,
    "書類選考・面接": 4,
    "内定・条件交渉": 5,
    "内々定・内定・入社準備": 5,
    "退職・入社準備": 6,
}
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
NUMERIC_CLAIM = re.compile(r"(?<![A-Za-z])[+-]?\d+(?:[.,]\d+)?\s*(?:%|％|명|人|건|件|배|倍|만|万円|원|円)")
DATE_VALUE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T[^Z]+Z)?$")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]+)?\]\]")
IGNORED_VAULT_DIRS = {".git", ".obsidian", ".career-agent", "career-home", "__pycache__"}
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


def atomic_write_text(path: Path, payload: str) -> None:
    """Write a complete sibling temp file, then replace the destination atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


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


def validate_career_context(value: Any) -> dict[str, Any]:
    """Validate the small, user-confirmed context payload shared across skills."""
    if not isinstance(value, dict):
        raise CareerError("career context must be an object")

    anchors = value.get("career_anchors")
    if anchors is not None:
        if not isinstance(anchors, dict):
            raise CareerError("career context career_anchors must be an object or null")
        if not isinstance(anchors.get("primary"), str) or not anchors["primary"].strip():
            raise CareerError("career context career_anchors.primary must be a non-empty string")
        secondary = anchors.get("secondary")
        if not isinstance(secondary, list) or not all(isinstance(entry, str) and entry.strip() for entry in secondary):
            raise CareerError("career context career_anchors.secondary must be a list of non-empty strings")
        if not isinstance(anchors.get("will_not_give_up"), str) or not anchors["will_not_give_up"].strip():
            raise CareerError("career context career_anchors.will_not_give_up must be a non-empty string")

    theme = value.get("career_theme")
    if theme is not None and (not isinstance(theme, str) or not theme.strip()):
        raise CareerError("career context career_theme must be a non-empty string or null")

    energy_map = value.get("energy_map")
    if energy_map is not None:
        if not isinstance(energy_map, dict):
            raise CareerError("career context energy_map must be an object or null")
        for field in ("energizes", "drains"):
            item = energy_map.get(field)
            if not isinstance(item, list) or not all(isinstance(entry, str) and entry.strip() for entry in item):
                raise CareerError(f"career context energy_map.{field} must be a list of non-empty strings")
        if energy_map.get("misfit_flag") is not None and not isinstance(energy_map["misfit_flag"], str):
            raise CareerError("career context energy_map.misfit_flag must be a string or null")

    values = value.get("career_values")
    if values is not None:
        if not isinstance(values, dict):
            raise CareerError("career context career_values must be an object or null")
        if string_list_from(values, "must_have") is None or string_list_from(values, "avoid") is None:
            raise CareerError("career context career_values requires must_have and avoid lists")

    if not any(value.get(field) is not None for field in CAREER_CONTEXT_FIELDS):
        raise CareerError("career context must contain at least one non-null field")
    return {field: value.get(field) for field in CAREER_CONTEXT_FIELDS}


def string_list_from(value: dict[str, Any], field: str) -> list[str] | None:
    item = value.get(field)
    if not isinstance(item, list) or not all(isinstance(entry, str) and entry.strip() for entry in item):
        return None
    return item


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    atomic_write_text(path, payload)


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
    atomic_write_text(path, "\n".join(lines) + "\n")


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
    expires = str(note.get("expires_on") or "")
    try:
        if expires and dt.date.fromisoformat(expires) < today():
            return False
    except ValueError:
        pass
    if track not in metadata_values(note.get("agent_scope")) | {"both"}:
        return False
    stages = metadata_values(note.get("agent_stage"))
    return not stages or stage in stages or "all" in stages


def select_context(vault: Path, track: str, stage: str) -> list[dict[str, Any]]:
    """Return metadata only; note bodies are deliberately never persisted or returned."""
    eligible = [note for note in index_vault_notes(vault) if context_eligible(note, track, stage)]
    eligible.sort(key=lambda note: note["date"] or "", reverse=True)
    selected = [
        {
            "path": note["path"],
            "kind": note["kind"],
            "title": note["title"],
            "description": note["description"],
            "headings": note["headings"],
            "source_type": note["source_type"],
            "selected_for": {"track": track, "stage": stage},
            "data_trust": UNTRUSTED_DATA_MARKER,
            "instruction_authority": "none",
        }
        for note in eligible
    ]
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
    if "company" in event and event["company"] is not None:
        if not isinstance(event["company"], str) or not event["company"].strip():
            raise CareerError("event.company must be a non-empty string")
    if "compensation" in event and event["compensation"] is not None:
        if isinstance(event["compensation"], bool) or not isinstance(event["compensation"], (int, float)) or event["compensation"] < 0:
            raise CareerError("event.compensation must be a number >= 0")
    if "currency" in event and event["currency"] is not None:
        if not isinstance(event["currency"], str) or not event["currency"].strip():
            raise CareerError("event.currency must be a non-empty string")
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
        # TOML is the human-editable source of truth; JSON is a replaceable cache/snapshot.
        write_toml(self.state_toml, normalized)
        write_json(self.state, normalized)

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
            atomic_write_text(target, content)  # PERSIST-001: canonical writer, no bare write_text
            created.append(str(target.relative_to(vault.path)))
    if not vault.state_toml.exists():
        write_toml(vault.state_toml, default_state())
        created.append(str(vault.state_toml.relative_to(vault.path)))
    return {"initialized": True, "vault": str(vault.path), "created": created, "next": "Fill 00-control/career-profile.toml, then run doctor --vault <path>."}


def company_slug(name: str) -> str:
    """Join key for data/pipeline.yml and data/company_profiles/{slug}.yml."""
    slug = re.sub(r"[^\w]+", "-", name.strip().lower(), flags=re.UNICODE).strip("-")
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
    text = (event.get("summary") or event["title"]).strip()
    fields = {"name": event["company"]}
    if stage is not None:
        fields["stage"] = stage
    if event.get("next_action"):
        fields["next_action"] = event["next_action"]
    if event.get("deadline"):
        fields["deadline"] = event["deadline"]

    hist_entry = {"date": day, "event": text[:120]}
    if event.get("id"):
        hist_entry["event_id"] = event["id"]

    try:
        pipeline_store.upsert_company(
            path,
            company_slug(event["company"]),
            fields,
            history=hist_entry,
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
    proposal = {
        "id": f"proposal-{uuid.uuid4().hex[:12]}",
        "kind": "event",
        "status": "pending",
        "created_at": utc_now(),
        "event": event,
    }
    trajectory = {
        "id": f"traj-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "mode": "chat",
        "observe": {"track": state.get("track"), "stage": state.get("stage"), "deadlines": state.get("deadlines", []), "recent_events": recent_events, "message": message, "data_trust": UNTRUSTED_DATA_MARKER, "instruction_authority": "none"},
        "plan": {"track": track, "stage": stage, "flow_phase": flow_phase, "goal": "route and propose a grounded event", "next_action": event["next_action"]},
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
        raise CareerError("discover postings require an original http(s) URL")
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
            updated = home.replace_proposal(proposal_id, status="approved", approved_at=utc_now(), version=version)
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
                result = approve(home, args.proposal_id, args.evidence, args.deadline, args.company, args.compensation, args.currency, args.workspace)
            elif args.command == "restore-state":
                result = restore_state(home, args.version)
            elif args.command == "index":
                result = run_index(home, include_archives=args.include_archives)
            elif args.command == "context":
                result = run_context(home, args.track, args.stage)
            elif args.command == "propose-context":
                result = propose_career_context(home, args.source)
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
