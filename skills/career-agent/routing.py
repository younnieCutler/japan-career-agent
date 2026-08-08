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
    routes = data.get("message_context")
    if (
        not data.get("track")
        or not data.get("stage_alias")
        or not data.get("flow_phase")
        or not isinstance(routes, list)
        or not routes
        or any(
            not isinstance(route, dict)
            or not isinstance(route.get("skill"), str)
            or not isinstance(route.get("reference"), str)
            or not isinstance(route.get("terms"), list)
            or not route["terms"]
            or any(not isinstance(term, str) or not term for term in route["terms"])
            for route in routes
        )
    ):
        raise CareerError(f"invalid routing reference: {ROUTING_REFERENCE}")
    return data


ROUTING = load_routing()

# Short ASCII tokens where a plain substring match false-positives inside unrelated English words
# (e.g. "es" — meant to catch the ES/entry-sheet abbreviation — also matches inside "research",
# "yes", "best"). Everything else, including intentional stems like "graduat", still matches as a
# substring.
_WORD_BOUNDARY_TERMS = {"es", "jd"}

# Alias groups that only say which track the user is on. They are a legitimate stage fallback, but
# they are not a statement about what the user wants to do next, so onboarding must not read them
# as a resolved intent.
_TRACK_ONLY_ALIASES = {"chuto", "shinsotsu"}

# "27卒" / "2027卒" / "2027年卒" / "class of 2027". The lookbehinds keep 既卒 and 第二新卒 out: those
# describe someone who already graduated, and reading a graduation year out of them would invent a
# fact the message never stated.
_GRADUATION_PATTERNS = (
    re.compile(r"(?<!第二新)(?<!既)(?<!\d)(\d{2}|\d{4})\s*年?卒"),
    re.compile(r"(\d{4})\s*(?:년\s*졸업|년도\s*졸업)"),
    re.compile(r"class of\s*(\d{4})", re.I),
    re.compile(r"(\d{4})\s*graduat", re.I),
)


# 第二新卒 is a 中途 hire, not a new graduate, but it contains 新卒 as a substring and every keyword
# lookup here is substring matching. Rewriting it to 中途 before any lookup keeps the lexicon honest
# without adding a negative-term mechanism that every future group would have to know about.
_SECOND_NEW_GRADUATE = re.compile(r"第\s*[二2]\s*新卒")


def normalized_message(message: str) -> str:
    """Lowercased message with expressions that read as their own opposite rewritten."""
    return _SECOND_NEW_GRADUATE.sub("中途", message.lower())


def term_present(term: str, lowered: str) -> bool:
    if term in _WORD_BOUNDARY_TERMS:
        # The boundary is ASCII letters/digits, not `\b`. `\b` treats CJK as word characters, so
        # "このJDと" would count as one word and the term would never match inside a Japanese or
        # Korean sentence, which is exactly where these abbreviations show up.
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lowered) is not None
    return term in lowered


def language_for(message: str) -> str:
    first_chunk = re.split(r"\n\s*\n|\n|(?<=[.!?。！？])\s+", message.strip(), maxsplit=1)[0]
    korean = len(re.findall(r"[가-힣]", first_chunk))
    japanese = len(re.findall(r"[ぁ-ゖァ-ヺ一-龯々]", first_chunk))
    if korean or japanese:
        return "ko" if korean >= japanese else "ja"
    return "en"


def graduation_signal(message: str) -> int | None:
    """The graduation year a message states outright, or None.

    This is a reading of what the user wrote, never a stored fact: the caller may only put it in a
    question for the user to confirm. A year outside 2000-2099 is treated as no signal rather than
    guessed at.
    """
    for pattern in _GRADUATION_PATTERNS:
        match = pattern.search(message)
        if not match:
            continue
        digits = match.group(1)
        year = 2000 + int(digits) if len(digits) == 2 else int(digits)
        if 2000 <= year <= 2099:
            return year
    return None


def infer_track(message: str, requested: str | None = None) -> str | None:
    if requested in TRACKS:
        return requested
    lowered = normalized_message(message)
    if any(term_present(term.lower(), lowered) for term in ROUTING["track"]["shinsotsu"]):
        return "shinsotsu"
    if any(term_present(term.lower(), lowered) for term in ROUTING["track"]["chuto"]):
        return "chuto"
    # "27卒" states a graduation year and nothing else, but only a new graduate describes
    # themselves that way. The lexicon cannot carry it: a bare "卒" substring would swallow
    # 既卒 and 第二新卒 too.
    if graduation_signal(message) is not None:
        return "shinsotsu"
    return None


def matched_stage_alias(message: str, *, skip_track_aliases: bool = False) -> str | None:
    """The first stage alias whose terms appear in the message, in reference order."""
    lowered = normalized_message(message)
    for group in ROUTING["stage_alias"]:
        alias = str(group["alias"])
        if skip_track_aliases and alias in _TRACK_ONLY_ALIASES:
            continue
        if any(term_present(term.lower(), lowered) for term in group["terms"]):
            return alias
    return None


def explicit_stage_alias(message: str) -> str | None:
    """The intent this message states outright, or None when it states none.

    `stage_for()` always returns a stage, falling back to the current or first stage, so it cannot
    answer "did the user actually say what they want?". Onboarding needs that question answered
    before it decides whether to route or ask. Track aliases are excluded: "이직 준비 중" resolves
    the track and says nothing about the next task.
    """
    return matched_stage_alias(message, skip_track_aliases=True)


def stage_for(message: str, track: str, current_stage: str | None = None) -> str:
    alias = matched_stage_alias(message)
    if alias is not None:
        if alias == "chuto":
            track = "chuto"
        if alias == "shinsotsu":
            track = "shinsotsu"
        candidates = CHUTO_STAGES if track == "chuto" else SHINSOTSU_STAGES
        return {
            "self": candidates[0],
            "documents": candidates[1],
            "research": candidates[2],
            "apply": candidates[3],
            "interview": candidates[4 if track == "chuto" else 5],
            "offer": candidates[5 if track == "chuto" else 6],
            "exit": candidates[6],
        }.get(alias, candidates[0])
    candidates = CHUTO_STAGES if track == "chuto" else SHINSOTSU_STAGES
    if current_stage in candidates:
        return current_stage
    return candidates[0]


def skill_context(
    skills_root: Path,
    stage: str,
    message: str | None = None,
    track: str | None = None,
) -> dict[str, Any]:
    route = None
    if message and track == "chuto":
        lowered = message.lower()
        route = next((
            item for item in ROUTING["message_context"]
            if any(term_present(term.lower(), lowered) for term in item["terms"])
        ), None)
    skill_name = route["skill"] if route else SKILL_BY_STAGE.get(stage)
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
    if route:
        reference = route["reference"]
        reference_path = (skill_path.parent / reference).resolve()
        try:
            reference_path.relative_to(skill_path.parent.resolve())
        except ValueError as exc:
            raise CareerError(f"invalid message context reference: {reference}") from exc
        if not reference_path.is_file():
            raise CareerError(f"message context reference not found: {reference_path}")
        references = [reference]
    else:
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
