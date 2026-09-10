"""Deterministic month-by-month projection over confirmed career evidence.

Months are a read model, never a second store. Canonical evidence stays in events.jsonl and this
module groups it by the user-supplied work_date. Capture time is deliberately not used as a
fallback: writing down old work today must not make it look like today's work.
"""

from __future__ import annotations

from typing import Any

from projection import confirmed_evidence_events, evidence_payload


DIMENSIONS = (
    "responsibility",
    "problem_framing",
    "direct_action",
    "stakeholder_coordination",
    "outcome",
    "quantification",
    "reflection",
)


def _present(payload: dict[str, Any], dimension: str) -> bool:
    if dimension == "responsibility":
        return bool(payload.get("role") or payload.get("scope") or payload.get("individual_contribution"))
    if dimension == "problem_framing":
        return bool(payload.get("problem"))
    if dimension == "direct_action":
        return bool(payload.get("direct_actions") or payload.get("individual_contribution"))
    if dimension == "stakeholder_coordination":
        return bool(payload.get("stakeholder_coordination"))
    if dimension == "outcome":
        return bool(
            payload.get("team_result")
            or payload.get("metrics")
            or payload.get("outcome_state") in {"qualitative", "quantitative"}
        )
    if dimension == "quantification":
        return bool(payload.get("metrics"))
    if dimension == "reflection":
        return bool(payload.get("improvements") or payload.get("learning"))
    raise KeyError(dimension)


def monthly_career_projection(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group current confirmed evidence by work month with deterministic coverage counts.

    Evidence without work_date is intentionally excluded from a month rather than assigned to its
    capture month. The caller can still show it through the ordinary experience projection.

    Coverage is counts, not an LLM-generated score. `present` answers only whether the confirmed
    evidence carries that dimension; it does not judge quality or seniority.
    """
    months: dict[str, dict[str, Any]] = {}
    for event in confirmed_evidence_events(events):
        payload = evidence_payload(event)
        work_date = payload.get("work_date")
        if not isinstance(work_date, str) or len(work_date) < 7:
            continue
        month = work_date[:7]
        current = months.setdefault(
            month,
            {
                "month": month,
                "evidence_count": 0,
                "claim_refs": [],
                "coverage": {
                    name: {"present": 0, "total": 0}
                    for name in DIMENSIONS
                },
            },
        )
        current["evidence_count"] += 1
        current["claim_refs"].append(event["id"])
        for name in DIMENSIONS:
            current["coverage"][name]["total"] += 1
            if _present(payload, name):
                current["coverage"][name]["present"] += 1

    result = []
    for month in sorted(months, reverse=True):
        current = months[month]
        current["gaps"] = [
            name
            for name in DIMENSIONS
            if current["coverage"][name]["present"] < current["coverage"][name]["total"]
        ]
        result.append(current)
    return result
