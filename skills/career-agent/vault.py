"""Vault metadata and state boundary for the Career Agent.

Vault bodies are indexed only for metadata. Confirmed context selection never
returns note bodies, and all canonical state writes go through
``persistence``. This module intentionally has no dependency on ``runtime``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid
from pathlib import Path
from typing import Any

from models import (
    CONTEXT_KINDS,
    TRUSTED_SOURCE_TYPES,
    UNTRUSTED_DATA_MARKER,
    VAULT_DIRECTORIES,
    CareerError,
    default_state,
    normalized_state,
)
from persistence import (
    append_jsonl,
    atomic_write_text,
    read_json,
    read_jsonl,
    read_toml,
    write_json,
    write_jsonl,
    write_toml,
)
from validation import iso_date


HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]+)?\]\]")
IGNORED_VAULT_DIRS = {".git", ".obsidian", ".career-agent", "career-home", "__pycache__"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today() -> dt.date:
    return dt.date.today()


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


def metadata_values(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    if isinstance(value, str) and value.strip():
        return {value.strip()}
    return set()


def context_eligible(note: dict[str, Any], track: str, stage: str, as_of: str) -> bool:
    """Eligibility for one explicit date. Never consults a clock (AC-21).

    `as_of` is a required parameter: the caller injects the day once, at the CLI boundary, so the
    same vault and the same date always produce the same selection. Reading `today()` here is why
    this path could not be tested for reproducibility.
    """
    if note.get("kind") not in CONTEXT_KINDS or note.get("agent_read") is not True:
        return False
    if note.get("status") != "verified" or note.get("source_type") not in TRUSTED_SOURCE_TYPES:
        return False
    day = dt.date.fromisoformat(iso_date(as_of, "as_of") or "")
    try:
        expires = iso_date(note.get("expires_on"), "expires_on")
    except CareerError:
        # AC-22: a malformed expiry makes the note INELIGIBLE, never permanently non-expiring.
        # Swallowing the parse error here meant one typo kept a stale note in context forever,
        # while `doctor` reported the very same value as a hard error. Two paths, one value, two
        # answers -- and the lenient one was on the side that feeds the model.
        return False
    if expires and dt.date.fromisoformat(expires) < day:
        return False
    if track not in metadata_values(note.get("agent_scope")) | {"both"}:
        return False
    stages = metadata_values(note.get("agent_stage"))
    return not stages or stage in stages or "all" in stages


def select_context(vault: Path, track: str, stage: str, as_of: str) -> list[dict[str, Any]]:
    """Return metadata only; note bodies are deliberately never persisted or returned."""
    eligible = [note for note in index_vault_notes(vault) if context_eligible(note, track, stage, as_of)]
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


def profile_template() -> str:
    # A brand new vault starts in `onboarding`, so the first chat turns ask for track, graduation
    # year, and the task the user actually wants before routing. Only new vaults are affected: an
    # existing profile already holds its own value and is never rewritten by this template.
    return """# Fill the values before running chat. Do not put raw resumes or transcripts here.\n# track = \"shinsotsu\"  # shinsotsu or chuto; stays unset while only career maintenance is used\n# graduation_year = 2027  # required for shinsotsu (university or graduate school)\n# target_role = \"LLMOps Engineer\"\ncareer_status = \"onboarding\"  # active, confirmed, or onboarding\n# Career readiness and job-search intent are separate. Both fields below are the user's own\n# declaration: only `set-employment-status` and `set-job-search` write them, and nothing infers\n# them from a JD review, a recruiter message, or a recorded work event.\nemployment_status = \"unknown\"  # employed, unemployed, student, other, or unknown\njob_search = \"off\"  # off or on\nlanguage = \"ko\"\n"""


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
