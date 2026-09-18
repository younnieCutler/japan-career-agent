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
    SKILL_EXECUTION,
    TRACKS,
    CareerError,
    canonical_stage,
)
from persistence import read_toml


FLOW_REFERENCE = Path(__file__).resolve().parent / "references" / "japan-career-flow.toml"
ROUTING_REFERENCE = Path(__file__).resolve().parent / "references" / "routing.yml"

# Specific message-context routes also own a lifecycle position. This keeps a target-specific
# document from being reported as base-document preparation and keeps a mock interview inside the
# active selection stage. Routes not listed here keep normal stage-alias behavior.
_MESSAGE_CONTEXT_STAGE = {
    "targeted_application_document": "応募・書類選考",
    "jd_evidence_match": "企業研究・JD分析",
    "interview_practice": "面接・選考",
    "aptitude_test": "応募・書類選考",
}


def _phrase_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(term, str) and term.strip() for term in value
    )


def load_routing() -> dict[str, Any]:
    """KO/JA/EN keyword lexicon shared by infer_track(), stage_for() and flow_phase_for()."""
    import yaml

    data = yaml.safe_load(ROUTING_REFERENCE.read_text(encoding="utf-8")) or {}
    routes = data.get("message_context")
    if (
        not data.get("track")
        or not data.get("stage_alias")
        or not data.get("flow_phase")
        or not _phrase_list(data.get("tanaoroshi"))
        or not _phrase_list(data.get("maintenance"))
        or not _phrase_list(data.get("opportunity_review"))
        or not _phrase_list(data.get("transition"))
        or not _phrase_list(data.get("review_closed"))
        or not isinstance(data.get("active_search"), dict)
        or not _phrase_list(data.get("active_search", {}).get("terms"))
        or not _phrase_list(data.get("active_search", {}).get("negation"))
        or not _phrase_list(data.get("message_context_exclusion"))
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

_WORD_BOUNDARY_TERMS = {"es", "jd"}
_CLAUSE_BOUNDARY = re.compile(r"[。．.!?！？、,;；\n]+")
_TRACK_ONLY_ALIASES = {"chuto", "shinsotsu"}
_WEAK_RESEARCH_TERMS = {
    "求人",
    "공고",
    "구인",
    "jd",
    "job description",
    "job posting",
    "job ad",
}
_GRADUATION_PATTERNS = (
    re.compile(r"(?<!第二新)(?<!既)(?<!\d)(\d{2}|\d{4})\s*年?卒"),
    re.compile(r"(\d{4})\s*(?:년\s*졸업|년도\s*졸업)"),
    re.compile(r"class of\s*(\d{4})", re.I),
    re.compile(r"(\d{4})\s*graduat", re.I),
)
_SECOND_NEW_GRADUATE = re.compile(r"第\s*[二2]\s*新卒")
_KOREAN_CAREER_DOCUMENT = re.compile(r"경력기술서")


def normalized_message(message: str) -> str:
    """Lowercased message with bounded vocabulary aliases normalized."""
    lowered = message.lower()
    lowered = _SECOND_NEW_GRADUATE.sub("中途", lowered)
    # 경력기술서 is the ordinary Korean label for the same artifact as 職務経歴書. Normalizing the
    # noun keeps track and stage routing consistent without making a broad fragment such as 경력 a
    # routing term.
    return _KOREAN_CAREER_DOCUMENT.sub("職務経歴書", lowered)


def term_present(term: str, lowered: str) -> bool:
    if term in _WORD_BOUNDARY_TERMS:
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
    """The graduation year a message states outright, or None."""
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
    if graduation_signal(message) is not None:
        return "shinsotsu"
    return None


def _open_clauses(message: str) -> tuple[str, ...]:
    """Return clauses that are not explicitly closing their own topic out."""
    lowered = normalized_message(message)
    clauses: list[str] = []
    for clause in _CLAUSE_BOUNDARY.split(lowered):
        if not clause.strip():
            continue
        if any(
            term_present(marker.lower(), clause)
            for marker in ROUTING["message_context_exclusion"]
        ):
            continue
        clauses.append(clause)
    return tuple(clauses)


def _any_term(message: str, terms: list[str]) -> bool:
    lowered = normalized_message(message)
    return any(term_present(term.lower(), lowered) for term in terms)


def _matched_message_context(message: str) -> dict[str, Any] | None:
    clauses = _open_clauses(message)
    return next(
        (
            item
            for item in ROUTING["message_context"]
            if any(
                term_present(term.lower(), clause)
                for clause in clauses
                for term in item["terms"]
            )
        ),
        None,
    )


def tanaoroshi_intent(message: str) -> bool:
    return _any_term(message, ROUTING["tanaoroshi"])


def maintenance_intent(message: str) -> bool:
    return _any_term(message, ROUTING["maintenance"])


def opportunity_review_intent(message: str) -> bool:
    return _any_term(message, ROUTING["opportunity_review"])


def transition_intent(message: str) -> bool:
    return _any_term(message, ROUTING["transition"])


def review_closed_intent(message: str) -> bool:
    return _any_term(message, ROUTING["review_closed"])


def active_search_intent(message: str) -> bool:
    if _any_term(message, ROUTING["active_search"]["negation"]):
        return False
    return _any_term(message, ROUTING["active_search"]["terms"])


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
    """The explicit stage intent stated in the message, if any."""
    return matched_stage_alias(message, skip_track_aliases=True)


def _stage_alias_terms(alias: str) -> tuple[str, ...]:
    for group in ROUTING["stage_alias"]:
        if str(group["alias"]) == alias:
            return tuple(str(term) for term in group["terms"])
    return ()


def _apply_overrides_weak_research(message: str) -> bool:
    """Treat a posting noun as context, not research intent, when the user explicitly applies."""
    lowered = normalized_message(message)
    apply_terms = _stage_alias_terms("apply")
    if not any(term_present(term.lower(), lowered) for term in apply_terms):
        return False
    matched_research = [
        term
        for term in _stage_alias_terms("research")
        if term_present(term.lower(), lowered)
    ]
    return bool(matched_research) and all(
        term.casefold() in _WEAK_RESEARCH_TERMS for term in matched_research
    )


def _canonical_current_stage(stage: str | None, track: str) -> str | None:
    return canonical_stage(stage, track)


def stage_for(message: str, track: str, current_stage: str | None = None) -> str:
    if track == "chuto":
        route = _matched_message_context(message)
        if route and route.get("id") in _MESSAGE_CONTEXT_STAGE:
            return _MESSAGE_CONTEXT_STAGE[str(route["id"])]

    alias = matched_stage_alias(message)
    if alias == "research" and _apply_overrides_weak_research(message):
        alias = "apply"
    if alias is not None:
        if alias == "chuto":
            track = "chuto"
        if alias == "shinsotsu":
            track = "shinsotsu"
        if track == "chuto":
            stage_by_alias = {
                "self": "自己分析・転職軸",
                "documents": "応募基盤・職務経歴書",
                "discover": "求人探索・候補整理",
                "research": "企業研究・JD分析",
                "apply": "応募・書類選考",
                "interview": "面接・選考",
                "offer": "内定・条件交渉",
                "exit": "退職・引き継ぎ",
                "onboarding": "入社準備・オンボーディング",
                "chuto": "自己分析・転職軸",
            }
        else:
            stage_by_alias = {
                "self": SHINSOTSU_STAGES[0],
                "documents": SHINSOTSU_STAGES[1],
                "discover": SHINSOTSU_STAGES[2],
                "research": SHINSOTSU_STAGES[2],
                "apply": SHINSOTSU_STAGES[3],
                "interview": SHINSOTSU_STAGES[5],
                "offer": SHINSOTSU_STAGES[6],
                "exit": SHINSOTSU_STAGES[6],
                "onboarding": SHINSOTSU_STAGES[6],
                "shinsotsu": SHINSOTSU_STAGES[0],
            }
        return stage_by_alias.get(alias, stage_by_alias["self"])

    candidates = CHUTO_STAGES if track == "chuto" else SHINSOTSU_STAGES
    canonical_current = _canonical_current_stage(current_stage, track)
    if canonical_current in candidates:
        return str(canonical_current)
    return candidates[0]


def skill_context(
    skills_root: Path,
    stage: str | None,
    message: str | None = None,
    track: str | None = None,
    skill_override: str | None = None,
) -> dict[str, Any]:
    resolved_stage = _canonical_current_stage(stage, track or "")
    route = None
    if message and track == "chuto" and not skill_override:
        route = _matched_message_context(message)
    skill_name = skill_override or (route["skill"] if route else SKILL_BY_STAGE.get(resolved_stage))
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
            name
            for name in REFERENCE_BY_STAGE.get(resolved_stage, ())
            if (skill_path.parent / name).exists()
        ]
    return {
        "skill": skill_name,
        "available": True,
        "path": str(skill_path),
        "description": description,
        "references": references,
    }


def select_skill(
    skills_root: Path,
    stage: str | None,
    message: str | None = None,
    track: str | None = None,
    skill_override: str | None = None,
) -> dict[str, Any]:
    """The Skill this turn would use, without claiming that selection means execution."""
    context = skill_context(skills_root, stage, message, track, skill_override)
    if not context:
        return context
    skill_name = context["skill"]
    if skill_name not in SKILL_EXECUTION:
        raise CareerError(f"skill '{skill_name}' has no entry in models.SKILL_EXECUTION")
    execution = SKILL_EXECUTION[skill_name]
    selection = {
        **context,
        "status": "selected",
        "invocation": None,
        "execution": execution,
    }
    if context.get("available"):
        entrypoint_hint = " --entrypoint HOST" if execution in ("host_required", "hybrid") else ""
        selection["invoke_with"] = f"skill-open --skill {skill_name}{entrypoint_hint}"
    return selection


def load_flow_reference() -> dict[str, Any]:
    reference = read_toml(FLOW_REFERENCE)
    if not reference.get("metadata") or not reference.get("shinsotsu") or not reference.get("chuto"):
        raise CareerError(f"invalid career flow reference: {FLOW_REFERENCE}")
    chuto_labels = tuple(
        str(phase.get("label"))
        for phase in reference.get("chuto", {}).get("phases", [])
        if isinstance(phase, dict) and phase.get("label")
    )
    if chuto_labels != CHUTO_STAGES:
        raise CareerError("career flow reference chuto labels drift from models.CHUTO_STAGES")
    return reference


def flow_phase_ids(reference: dict[str, Any], track: str) -> set[str]:
    phases = reference.get(track, {}).get("phases", [])
    return {str(phase.get("id")) for phase in phases if isinstance(phase, dict) and phase.get("id")}


def flow_phase_for(
    message: str,
    track: str,
    state: dict[str, Any],
    profile: dict[str, Any],
    reference: dict[str, Any],
) -> str:
    allowed = flow_phase_ids(reference, track)
    if track == "chuto":
        route = _matched_message_context(message)
        route_phase = {
            "targeted_application_document": "application_selection",
            "jd_evidence_match": "opportunity_analysis",
            "interview_practice": "interview",
            "aptitude_test": "application_selection",
        }.get(str(route.get("id"))) if route else None
        if route_phase in allowed:
            return str(route_phase)

    lowered = normalized_message(message)
    for signal in ROUTING["flow_phase"][track]:
        if any(term_present(term.lower(), lowered) for term in signal["terms"]) and signal["id"] in allowed:
            return signal["id"]
    for value in (profile.get("flow_phase"), state.get("flow_phase")):
        if value in allowed:
            return str(value)
    if track == "shinsotsu" and state.get("stage") == SHINSOTSU_STAGES[-1] and "offer_onboarding" in allowed:
        return "offer_onboarding"
    return "preparation"
