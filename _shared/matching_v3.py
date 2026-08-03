#!/usr/bin/env python3
"""Evidence-based matching diagnosis — model_version: evidence_based_v3.

Replaces the single-number match score with independent axes that are never summed:

    Decision Status  (proceed | review | conflict)
    1. Eligibility
    2. Required Skill & Experience
    3. MHLW Portable Skill composition distance
    4. Career Values & Conditions
    5. Candidate Interest            (recorded, never scored)
    6. Employer Signals              (observed events only)
    7. Evidence / Missing Information / Confidence

Three rules the code enforces, not the prose:

  P2  Missing information stays `unknown`. Nothing here substitutes a mean, a 50, or a
      pass for an absent fact, and `unknown` never enters a coverage denominator.
  P3  `candidate_interest` is copied to the output and read by nothing else. `evaluate()`
      computes every objective axis before it is even looked at.
  P4  Every element carries provenance; no weight in this file was invented to combine
      axes, because no axis is combined with another.

Retired heuristic calculations are NOT here. They live in `_shared/legacy_experimental.py`
under `model_version: legacy_v1` and are off by default.

CLI (deterministic; same input -> same output):
    python3 _shared/matching_v3.py input.json
    cat input.json | python3 _shared/matching_v3.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

# `mhlw_reference` is a sibling; make it importable however this module was loaded.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

MODEL_VERSION = "evidence_based_v3"
RULES_VERSION = "v3.0"

# MHLW 持ち味 allocation: 9 elements, each an integer >= 1, summing to exactly 29.
ALLOCATION_KEYS = (
    "current_state_assessment",   # 現状の把握
    "task_setting",               # 課題の設定
    "planning",                   # 計画の立案
    "task_execution",             # 課題の遂行
    "situational_response",       # 状況への対応
    "internal_coordination",      # 社内対応
    "external_coordination",      # 社外対応
    "manager_response",           # 上司対応
    "subordinate_management",     # 部下マネジメント
)
ALLOCATION_TOTAL = 29
ALLOCATION_MIN = 1

DECISION_PROCEED = "proceed"
DECISION_REVIEW = "review"
DECISION_CONFLICT = "conflict"

SOURCE_TYPES = {
    # Canonical source labels.
    "official_framework", "job_posting", "company_public_source", "user", "observed",
    "derived", "heuristic", "unknown",
    # Read-only aliases accepted for existing payloads.
    "official", "recruiter", "third_party", "inferred",
}
PROVENANCE_TYPES = {
    "official_framework", "job_posting", "company_public_source", "user", "observed",
    "derived", "heuristic", "unknown",
}
CONFIDENCE_LEVELS = {"high", "medium", "low", "unknown"}
INTEREST_EVIDENCE_SOURCES = {"self_report", "event_experience", "interview_experience"}
EMPLOYER_SIGNAL_TYPES = {"scout", "message", "interview_invite", "pass_notice", "rejection"}

# Distance is reported to this many decimals. Rounding is applied once, at output, so the
# ranking itself is computed on full precision.
_DP = 6


class ValidationError(ValueError):
    """Input violates a rule the diagnosis cannot silently repair."""


# ─────────────────────────────────────────────────────────────
# FR-3. MHLW Portable Skill — allocation validation & composition distance
# ─────────────────────────────────────────────────────────────

def validate_allocation(allocation: Any, *, label: str = "portable_skill_allocation") -> dict[str, int]:
    """Validate a 29-point allocation over the 9 MHLW elements.

    `level: 1..5` is deliberately not accepted here. It is position-level information and
    is stored beside the allocation, never mixed into the distance vector (PRD §7.3.1).
    """
    if not isinstance(allocation, dict):
        raise ValidationError(f"{label}: expected a mapping of the 9 MHLW elements")

    unknown_keys = sorted(set(allocation) - set(ALLOCATION_KEYS))
    if unknown_keys:
        raise ValidationError(f"{label}: unknown element(s) {unknown_keys}")
    missing = [key for key in ALLOCATION_KEYS if key not in allocation]
    if missing:
        raise ValidationError(f"{label}: missing element(s) {missing}")

    values: dict[str, int] = {}
    for key in ALLOCATION_KEYS:
        value = allocation[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(f"{label}.{key}: must be an integer, got {value!r}")
        if value < ALLOCATION_MIN:
            raise ValidationError(f"{label}.{key}: must be >= {ALLOCATION_MIN}, got {value}")
        values[key] = value

    total = sum(values.values())
    if total != ALLOCATION_TOTAL:
        raise ValidationError(f"{label}: 9 elements must sum to exactly {ALLOCATION_TOTAL}, got {total}")
    return values


def composition(allocation: dict[str, int]) -> dict[str, float]:
    """Normalise an allocation to proportions summing to 1 (PRD §7.3.3)."""
    total = sum(allocation[key] for key in ALLOCATION_KEYS)
    if total <= 0:
        raise ValidationError("allocation total must be positive")
    return {key: allocation[key] / total for key in ALLOCATION_KEYS}


def composition_distance(a: dict[str, int], b: dict[str, int]) -> float:
    """Euclidean distance between two composition profiles.

    MHLW (job tag) specifies the 9-element 29-point allocation framework and 114 standard
    profiles (https://shigoto.mhlw.go.jp/User/VocationalAbilityDiagnosticTool/Step1). This implementation
    computes Euclidean distance on the normalized composition vectors as its deterministic distance metric.

    Not a fit score. There is no 0–100 conversion here and none may be added (PRD §7.3.3).
    """
    p, q = composition(a), composition(b)
    return math.sqrt(sum((p[key] - q[key]) ** 2 for key in ALLOCATION_KEYS))


def rank_role_profiles(allocation: dict[str, int], profiles: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
    """All reference profiles ordered by composition distance, nearest first.

    Ties break on `id` so the ordering is stable across runs (NFR-2).
    """
    scored = [
        {"id": profile["id"], "label": profile["label"],
         "distance": composition_distance(allocation, profile["allocation"])}
        for profile in profiles
    ]
    scored.sort(key=lambda item: (item["distance"], item["id"]))
    for position, item in enumerate(scored, start=1):
        item["rank"] = position
        item["distance"] = round(item["distance"], _DP)
    return scored[:top_n]


def _composition_delta(candidate: dict[str, int], reference: dict[str, int]) -> dict[str, float]:
    p, q = composition(candidate), composition(reference)
    return {key: round(p[key] - q[key], _DP) for key in ALLOCATION_KEYS}


def portable_skill_result(payload: dict[str, Any] | None, reference: dict[str, Any] | None = None) -> dict[str, Any]:
    """FR-3 result block.

    status:
      insufficient_data — no 29-point allocation recorded for the candidate
      unmapped          — allocation present, but no evidenced MHLW role mapping
      unavailable       — mapping exists but the reference dataset is not installed
      available         — distance and rank computed against the reference dataset
    """
    from mhlw_reference import load as load_reference

    base = {
        "status": "insufficient_data",
        "note": "distance between composition profiles; not a 0-100 fit score",
        "distance": None,
        "rank": None,
        "compared_profiles": None,
        "nearest_profiles": [],
        "composition_delta": None,
        "level": None,
        "level_note": "position level, recorded separately; excluded from the distance vector",
        "allocation": None,
        "composition": None,
        "mapping": None,
        "dataset": None,
        "reason": None,
    }

    payload = payload or {}
    allocation_raw = payload.get("allocation")
    if allocation_raw is None:
        base["reason"] = (
            "no MHLW 29-point allocation recorded. A 1-5 portable-skill rating is NOT "
            "convertible to an allocation; ask the user to distribute 29 points across the 9 elements."
        )
        return base

    allocation = validate_allocation(allocation_raw)
    base["allocation"] = allocation
    base["composition"] = {key: round(value, _DP) for key, value in composition(allocation).items()}
    level = payload.get("level")
    if level is not None:
        if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 5:
            raise ValidationError("portable_skill.level: must be an integer 1-5 or null")
        base["level"] = level
    base["assessed_at"] = payload.get("assessed_at")

    mapping = payload.get("mhlw_mapping") or {}
    mapped_id = mapping.get("mapped_role_profile_id")
    if not mapped_id:
        base["status"] = "unmapped"
        base["reason"] = (
            "no evidenced MHLW role-profile mapping for this posting. Per PRD §7.3.2 a JD "
            "distance is not generated without a recorded mapping basis."
        )
        base["mapping"] = mapping or None
        return base

    if not mapping.get("evidence") or mapping.get("method") in (None, ""):
        base["status"] = "unmapped"
        base["reason"] = "mhlw_mapping requires both `method` and `evidence`; distance not generated."
        base["mapping"] = mapping
        return base

    base["mapping"] = {
        "mapped_role_profile_id": mapped_id,
        "method": mapping.get("method"),
        "confidence": mapping.get("confidence") or "unknown",
        "evidence": mapping.get("evidence"),
        "official_values": mapping.get("method") != "heuristic_mapping",
    }
    if mapping.get("method") == "heuristic_mapping":
        base["mapping"]["warning"] = (
            "heuristic_mapping: composition derived by this project, NOT official MHLW values."
        )

    data = reference if reference is not None else load_reference()
    base["dataset"] = {
        "status": data["status"],
        "dataset_version": data.get("dataset_version"),
        "source": data.get("source"),
        "licence": data.get("licence"),
        "expected_path": data.get("expected_path"),
        "expected_count_mismatch": data.get("expected_count_mismatch"),
    }
    if data["status"] != "available":
        base["status"] = "unavailable"
        base["reason"] = data.get("reason")
        return base

    target = next((profile for profile in data["profiles"] if profile["id"] == mapped_id), None)
    if target is None:
        base["status"] = "unavailable"
        base["reason"] = f"mapped_role_profile_id {mapped_id!r} is not in reference dataset {data['dataset_version']}"
        return base

    ranked = rank_role_profiles(allocation, data["profiles"], top_n=len(data["profiles"]))
    mapped_entry = next(item for item in ranked if item["id"] == mapped_id)
    base["status"] = "available"
    base["distance"] = mapped_entry["distance"]
    base["rank"] = mapped_entry["rank"]
    base["compared_profiles"] = data["profile_count"]
    base["nearest_profiles"] = ranked[:5]
    base["composition_delta"] = _composition_delta(allocation, target["allocation"])
    return base


# ─────────────────────────────────────────────────────────────
# FR-1. Eligibility (tri-state)
# ─────────────────────────────────────────────────────────────

def eligibility_results(items: Any) -> list[dict[str, Any]]:
    """`conflict` only when BOTH sides are evidenced and actually disagree (PRD FR-1)."""
    if items is None:
        return []
    if not isinstance(items, list):
        raise ValidationError("eligibility: expected a list")
    results = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not item.get("requirement"):
            raise ValidationError(f"eligibility[{index}]: `requirement` is required")
        candidate_evidence = item.get("candidate_evidence")
        job_evidence = item.get("job_evidence")
        meets = item.get("meets")
        if meets is not None and not isinstance(meets, bool):
            raise ValidationError(f"eligibility[{index}].meets: must be true, false, or null")

        if candidate_evidence is None or job_evidence is None or meets is None:
            status, source = "unknown", "unknown"
        else:
            status = "matched" if meets else "conflict"
            source = item.get("source") or "observed"
        results.append({
            "requirement": item["requirement"],
            "status": status,
            "candidate_evidence": candidate_evidence,
            "job_evidence": job_evidence,
            "source": source,
            **_evidence_meta(item),
        })
    return results


# ─────────────────────────────────────────────────────────────
# FR-2. Skill & Experience Gap
# ─────────────────────────────────────────────────────────────

def _bucket(items: Any, field: str) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {"matched": [], "missing": [], "unknown": []}
    if items is None:
        return buckets
    if not isinstance(items, list):
        raise ValidationError(f"{field}: expected a list")
    for index, item in enumerate(items):
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict) or not item.get("name"):
            raise ValidationError(f"{field}[{index}]: `name` is required")
        status = item.get("status", "unknown")
        if status not in buckets:
            raise ValidationError(f"{field}[{index}].status: must be matched | missing | unknown")
        entry = {"name": item["name"], **_evidence_meta(item)}
        if item.get("mapping_basis"):
            entry["mapping_basis"] = item["mapping_basis"]  # FR-2: synonym / hierarchy mapping must show its basis
        if item.get("evidence"):
            entry["evidence"] = item["evidence"]
        buckets[status].append(entry)
    return buckets


def skill_results(payload: Any) -> dict[str, Any]:
    payload = payload or {}
    required = _bucket(payload.get("required"), "skills.required")
    preferred = _bucket(payload.get("preferred"), "skills.preferred")
    experience = _bucket(payload.get("experience"), "skills.experience")

    confirmed = len(required["matched"]) + len(required["missing"])
    if confirmed == 0:
        coverage: float | None = None
        coverage_status = "insufficient_data"
    else:
        coverage = round(len(required["matched"]) / confirmed, 4)
        coverage_status = "available"

    return {
        "required_skills": required,
        "preferred_skills": preferred,
        "experience": {
            "matched": experience["matched"],
            "gaps": experience["missing"],
            "unknown": experience["unknown"],
        },
        "required_coverage": coverage,
        "required_coverage_status": coverage_status,
        "required_coverage_basis": {
            "confirmed_matched": len(required["matched"]),
            "confirmed_missing": len(required["missing"]),
            "unknown_excluded": len(required["unknown"]),
        },
        "required_coverage_note": (
            "share of the CONFIRMED required skills that are met. Unknowns are excluded from "
            "the denominator and counted separately. This is not an outcome estimate."
        ),
    }


# ─────────────────────────────────────────────────────────────
# FR-4. Career Values & Conditions
# ─────────────────────────────────────────────────────────────

_VALUE_KINDS = {"must_have", "preferred", "avoid"}


def career_value_results(items: Any) -> dict[str, Any]:
    results: dict[str, Any] = {"aligned": [], "tradeoffs": [], "conflicts": [], "unknown": []}
    if items is None:
        return results
    if not isinstance(items, list):
        raise ValidationError("career_values: expected a list")
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not item.get("value"):
            raise ValidationError(f"career_values[{index}]: `value` is required")
        kind = item.get("kind")
        if kind not in _VALUE_KINDS:
            raise ValidationError(f"career_values[{index}].kind: must be one of {sorted(_VALUE_KINDS)}")
        satisfied = item.get("satisfied")
        if satisfied is not None and not isinstance(satisfied, bool):
            raise ValidationError(f"career_values[{index}].satisfied: must be true, false, or null")

        if satisfied is None or item.get("company_evidence") is None:
            bucket = "unknown"
        elif kind == "must_have":
            bucket = "aligned" if satisfied else "conflicts"
        elif kind == "avoid":
            # `satisfied: true` on an `avoid` item means the company DOES have the avoided condition.
            bucket = "conflicts" if satisfied else "aligned"
        else:
            bucket = "aligned" if satisfied else "tradeoffs"

        results[bucket].append({
            "value": item["value"],
            "kind": kind,
            "company_evidence": item.get("company_evidence"),
            **_evidence_meta(item),
        })
    return results


# ─────────────────────────────────────────────────────────────
# FR-5 / FR-6. Candidate Interest & Employer Signals — recorded, never scored
# ─────────────────────────────────────────────────────────────

def candidate_interest(payload: Any) -> dict[str, Any]:
    payload = payload or {}
    if not isinstance(payload, dict):
        raise ValidationError("candidate_interest: expected a mapping")
    level = payload.get("interest_level")
    if level is not None:
        if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 5:
            raise ValidationError("candidate_interest.interest_level: must be an integer 1-5 or null")
    evidence = payload.get("interest_evidence") or []
    if not isinstance(evidence, list):
        raise ValidationError("candidate_interest.interest_evidence: expected a list")
    for index, item in enumerate(evidence):
        if not isinstance(item, dict) or item.get("source") not in INTEREST_EVIDENCE_SOURCES:
            raise ValidationError(
                f"candidate_interest.interest_evidence[{index}].source: must be one of "
                f"{sorted(INTEREST_EVIDENCE_SOURCES)}"
            )
    return {
        "interest_level": level,
        "interest_reason": payload.get("interest_reason"),
        "interest_updated_at": payload.get("interest_updated_at"),
        "interest_evidence": list(evidence),
        "note": (
            "user-declared interest. Excluded from Eligibility, Skill, Portable Skill, "
            "Career Value and Decision Status. Absent interest stays null; it is not read as 3."
        ),
    }


def employer_signals(items: Any) -> list[dict[str, Any]]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise ValidationError("employer_signals: expected a list")
    signals = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or item.get("type") not in EMPLOYER_SIGNAL_TYPES:
            raise ValidationError(
                f"employer_signals[{index}].type: must be one of {sorted(EMPLOYER_SIGNAL_TYPES)}"
            )
        signals.append({
            "type": item["type"],
            "observed_at": item.get("observed_at"),
            "source": item.get("source"),
        })
    return signals


# ─────────────────────────────────────────────────────────────
# FR-7. Evidence & Confidence
# ─────────────────────────────────────────────────────────────

def _evidence_meta(item: dict[str, Any]) -> dict[str, Any]:
    source_type = item.get("source_type")
    if source_type is not None and source_type not in SOURCE_TYPES:
        raise ValidationError(f"source_type must be one of {sorted(SOURCE_TYPES)}, got {source_type!r}")
    provenance = item.get("provenance")
    if provenance is not None and provenance not in PROVENANCE_TYPES:
        raise ValidationError(f"provenance must be one of {sorted(PROVENANCE_TYPES)}, got {provenance!r}")
    if provenance is None:
        if source_type in {"official", "official_framework"}:
            provenance = "official_framework"
        elif source_type in {"job_posting", "recruiter", "third_party"}:
            provenance = "observed"
        elif source_type in {"company_public_source", "observed"}:
            provenance = "observed"
        elif source_type in {"user", "derived"}:
            provenance = source_type
        elif source_type in {"heuristic", "inferred"}:
            provenance = "heuristic"
        elif item.get("source") in {"observed", "user", "recruiter", "job_posting"}:
            provenance = "observed"
        elif item.get("source") == "official":
            provenance = "official_framework"
        else:
            provenance = "unknown"
    confidence = item.get("confidence") or "unknown"
    if confidence not in CONFIDENCE_LEVELS:
        raise ValidationError(f"confidence must be one of {sorted(CONFIDENCE_LEVELS)}, got {confidence!r}")
    return {
        "provenance": provenance,
        "source_type": {
            "official": "official_framework",
            "recruiter": "observed",
            "third_party": "observed",
            "inferred": "heuristic",
        }.get(source_type, source_type),
        "source": item.get("source"),
        "source_ref": item.get("source_ref"),
        "observed_at": item.get("observed_at"),
        "confidence": confidence,
    }


def _label(item: dict[str, Any]) -> str:
    return str(item.get("requirement") or item.get("name") or item.get("value") or "?")


def _stale(items: list[dict[str, Any]], as_of: str | None) -> list[str] | None:
    """Facts older than 180 days. Returns None when the caller gave no `as_of` date —
    deriving staleness from the wall clock would break NFR-2 (same input, same output)."""
    if not as_of:
        return None
    import datetime as dt

    try:
        today = dt.date.fromisoformat(as_of)
    except ValueError as exc:
        raise ValidationError(f"as_of: expected YYYY-MM-DD, got {as_of!r}") from exc
    stale = []
    for item in items:
        observed = item.get("observed_at")
        try:
            when = dt.date.fromisoformat(str(observed))
        except (TypeError, ValueError):
            continue
        if (today - when).days > 180:
            stale.append(f"{_label(item)} (observed {observed})")
    return sorted(stale)


def evidence_summary(facts: list[dict[str, Any]], conflicting: list[str], as_of: str | None) -> dict[str, Any]:
    by_source: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    for item in facts:
        by_source[str(item.get("source_type"))] = by_source.get(str(item.get("source_type")), 0) + 1
        by_confidence[str(item.get("confidence"))] = by_confidence.get(str(item.get("confidence")), 0) + 1
    return {
        "counts_by_source_type": dict(sorted(by_source.items())),
        "counts_by_confidence": dict(sorted(by_confidence.items())),
        "low_confidence": sorted({_label(i) for i in facts if i.get("confidence") == "low"}),
        "conflicting_evidence": list(conflicting),
        "stale": _stale(facts, as_of),
        "as_of": as_of,
    }


# ─────────────────────────────────────────────────────────────
# §6.1 Decision Status
# ─────────────────────────────────────────────────────────────

def decision_status(
    eligibility: list[dict[str, Any]],
    skills: dict[str, Any],
    values: dict[str, Any],
    conflicting_evidence: list[str],
) -> dict[str, Any]:
    """Not a total. It reports whether the current information supports a decision.

    `candidate_interest` is not a parameter and must never become one (PRD FR-5, AC-5).
    """
    conflicts = [f"eligibility: {item['requirement']}" for item in eligibility if item["status"] == "conflict"]
    conflicts += [f"career value ({item['kind']}): {item['value']}" for item in values["conflicts"]]

    unknowns = [f"eligibility: {item['requirement']}" for item in eligibility if item["status"] == "unknown"]
    unknowns += [f"required skill: {item['name']}" for item in skills["required_skills"]["unknown"]]
    unknowns += [f"experience: {item['name']}" for item in skills["experience"]["unknown"]]
    unknowns += [f"career value ({item['kind']}): {item['value']}"
                 for item in values["unknown"] if item["kind"] in {"must_have", "avoid"}]
    if skills["required_coverage_status"] == "insufficient_data":
        unknowns.append("required skills: no confirmed requirement to measure against")

    if conflicts:
        status = DECISION_CONFLICT
    elif unknowns or conflicting_evidence:
        status = DECISION_REVIEW
    else:
        status = DECISION_PROCEED
    return {
        "status": status,
        "conflicts": conflicts,
        "unknowns": unknowns,
        "conflicting_evidence": list(conflicting_evidence),
        "note": "Proceed means nothing blocks a decision on current information. "
                "It is not a recommendation to apply and not an outcome estimate.",
    }


# ─────────────────────────────────────────────────────────────
# Top-level
# ─────────────────────────────────────────────────────────────

def evaluate(payload: dict[str, Any], *, reference: dict[str, Any] | None = None) -> dict[str, Any]:
    """Full v3 diagnosis. Deterministic: same payload -> byte-identical output."""
    if not isinstance(payload, dict):
        raise ValidationError("payload must be a mapping")

    conflicting_evidence = list(payload.get("conflicting_evidence") or [])

    # Objective axes first, and complete, before interest is even read (P3 / AC-4).
    eligibility = eligibility_results(payload.get("eligibility"))
    skills = skill_results(payload.get("skills"))
    portable = portable_skill_result(payload.get("portable_skill"), reference=reference)
    values = career_value_results(payload.get("career_values"))
    decision = decision_status(eligibility, skills, values, conflicting_evidence)

    facts = (
        eligibility
        + [item for bucket in skills["required_skills"].values() for item in bucket]
        + [item for bucket in skills["preferred_skills"].values() for item in bucket]
        + [item for bucket in skills["experience"].values() for item in bucket]
        + [item for bucket in values.values() for item in bucket]
    )

    missing = list(decision["unknowns"])
    if portable["status"] != "available":
        missing.append(f"portable skill: {portable['status']} — {portable['reason']}")
    missing += [f"preferred skill: {item['name']}" for item in skills["preferred_skills"]["unknown"]]
    missing += [f"experience: {item['name']}" for item in skills["experience"]["unknown"]]
    missing += [f"career value ({item['kind']}): {item['value']}"
                for item in values["unknown"] if item["kind"] == "preferred"]
    missing = list(dict.fromkeys(missing))

    return {
        "model_version": MODEL_VERSION,
        "rules_version": RULES_VERSION,
        "candidate_name": payload.get("candidate_name"),
        "company_name": payload.get("company_name"),
        "position": payload.get("position"),
        "decision_status": decision["status"],
        "decision_basis": decision,
        "eligibility": eligibility,
        "skills": skills,
        "portable_skill": portable,
        "career_values": values,
        "candidate_interest": candidate_interest(payload.get("candidate_interest")),
        "employer_signals": employer_signals(payload.get("employer_signals")),
        "missing_information": missing,
        "clarifying_questions": [f"Can you confirm — {item}?" for item in decision["unknowns"]],
        "evidence_summary": evidence_summary(facts, conflicting_evidence, payload.get("as_of")),
    }


def _eligibility_detail(item: dict[str, Any]) -> str:
    """For an unknown, name the side that is missing — that is the actionable part."""
    if item["status"] == "matched":
        return ""
    if item["status"] == "conflict":
        return f" — candidate: {item['candidate_evidence']} / job: {item['job_evidence']}"
    missing = [side for side, key in (("job posting", "job_evidence"), ("candidate", "candidate_evidence"))
               if not item[key]]
    if missing:
        return f" — not stated by {' and '.join(missing)}"
    return " — both sides evidenced, comparison not confirmed"


def render(result: dict[str, Any]) -> str:
    """Plain-text report in the PRD §9 order. No score line, by construction."""
    out: list[str] = []
    header = " / ".join(str(x) for x in (result.get("company_name"), result.get("position")) if x)
    if header:
        out.append(header)
    out.append(f"Decision Status: {result['decision_status'].title()}")
    out.append("")

    out.append("Eligibility")
    out += [f"- {item['requirement']}: {item['status'].title()}{_eligibility_detail(item)}"
            for item in result["eligibility"]] or ["- none recorded"]
    out.append("")

    skills = result["skills"]
    out.append("Required Skills")
    if skills["required_coverage_status"] == "insufficient_data":
        out.append("- insufficient_data — no confirmed required skill to measure")
    else:
        basis = skills["required_coverage_basis"]
        out.append(f"- {basis['confirmed_matched']}/{basis['confirmed_matched'] + basis['confirmed_missing']}"
                   " confirmed requirements matched")
    for bucket, title in (("missing", "Missing"), ("unknown", "Unknown")):
        names = [item["name"] for item in skills["required_skills"][bucket]]
        if names:
            out.append(f"- {title}: {', '.join(names)}")
    out.append("")

    portable = result["portable_skill"]
    out.append("Portable Skills")
    if portable["status"] == "available":
        out.append(f"- MHLW mapped role: {portable['mapping']['mapped_role_profile_id']}")
        out.append(f"- Distance: {portable['distance']}")
        out.append(f"- Rank: {portable['rank']} / {portable['compared_profiles']}")
    else:
        out.append(f"- {portable['status']} — {portable['reason']}")
    out.append(f"- Note: {portable['note']}")
    out.append("")

    values = result["career_values"]
    out.append("Career Values & Conditions")
    for bucket, title in (("aligned", "Aligned"), ("tradeoffs", "Tradeoff"),
                          ("conflicts", "Conflict"), ("unknown", "Unknown")):
        names = [item["value"] for item in values[bucket]]
        out.append(f"- {title}: {', '.join(names) if names else 'none confirmed'}")
    out.append("")

    interest = result["candidate_interest"]
    out.append("Candidate Interest")
    level = interest["interest_level"]
    out.append(f"- {level}/5 — {interest['interest_reason'] or 'no reason recorded'}"
               if level is not None else "- not recorded (null; not read as neutral)")
    out.append("- Excluded from objective-fit calculations")
    out.append("")

    if result["employer_signals"]:
        out.append("Employer Signals (observed events only)")
        out += [f"- {s['type']} @ {s['observed_at'] or 'date unknown'} ({s['source'] or 'source unknown'})"
                for s in result["employer_signals"]]
        out.append("")

    out.append("Missing Information")
    out += [f"- {item}" for item in result["missing_information"]] or ["- none"]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    as_text = "--text" in argv
    argv = [arg for arg in argv if arg != "--text"]
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    payload = json.loads(Path(argv[0]).read_text(encoding="utf-8")) if argv else json.load(sys.stdin)
    try:
        result = evaluate(payload)
    except ValidationError as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 2
    if as_text:
        print(render(result))
    else:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False, sort_keys=False)
        print()
    return 0


if __name__ == "__main__":
    # Dispatch through the imported module so `ValidationError` raised inside
    # mhlw_reference is the same class this file's `main()` catches.
    from matching_v3 import main as _main

    raise SystemExit(_main())
