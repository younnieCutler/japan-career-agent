"""Language, track, stage, and flow-phase routing for the Career Agent."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from models import (
    CHUTO_STAGES,
    REFERENCE_BY_STAGE,
    SHINSOTSU_STAGES,
    SKILL_BY_STAGE,
    TRACKS,
    CareerError,
)
from persistence import read_toml


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
    # Message signal comes first: a new explicit signal must be allowed to move the phase.
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
