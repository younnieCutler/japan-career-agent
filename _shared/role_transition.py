#!/usr/bin/env python3
"""Evidence-backed target-role exploration without fit scores or hidden ranking.

The evaluator answers a narrow question: given confirmed candidate evidence and a set of
source-backed role hypotheses, what is directly demonstrated, what is explicitly absent,
what remains unknown, and which transfer ideas still need verification?

It deliberately does NOT discover or rank roles by itself. Role hypotheses and their
requirements must arrive with provenance. The job-seeker workflow may research those hypotheses
from sources such as MHLW job tag and current job postings, then this module keeps the comparison
reproducible and prevents unsupported transfer claims from becoming `Matched`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

MODEL_VERSION = "evidence_based_role_transition_v1"

EVIDENCE_STATES = {"Confirmed", "Unknown", "Contradictory", "Stale", "Low Confidence"}
REQUIREMENT_STATES = {"Matched", "Missing", "Unknown"}
REQUIREMENT_KINDS = {"core", "preferred", "context"}
TARGETING_STATES = {
    "evidence_supported",
    "needs_validation",
    "confirmed_core_gap",
    "insufficient_role_evidence",
}
SOURCE_TYPES = {
    "official_framework",
    "job_posting",
    "company_public_source",
    "user",
    "observed",
    "derived",
    "heuristic",
    "unknown",
}
ROLE_SOURCE_TYPES = {"official_framework", "job_posting", "company_public_source"}
DIRECT_CANDIDATE_SOURCE_TYPES = {"user", "observed"}
USABLE_CONFIDENCE_LEVELS = {"high", "medium"}
CONFIDENCE_LEVELS = {"high", "medium", "low", "unknown"}
PROVENANCE_TYPES = {
    "official_framework",
    "job_posting",
    "company_public_source",
    "user",
    "observed",
    "derived",
    "heuristic",
    "synthetic",
    "unknown",
}


class RoleTransitionError(ValueError):
    """Input violates a contract that must not be repaired by guessing."""


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RoleTransitionError(f"{label}: expected object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise RoleTransitionError(f"{label}: expected list")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoleTransitionError(f"{label}: expected non-empty string")
    return value.strip()


def _optional_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _unique_ids(items: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        item_id = _text(item.get("id"), f"{label}[{index}].id")
        if item_id in by_id:
            raise RoleTransitionError(f"{label}: duplicate id {item_id!r}")
        by_id[item_id] = item
    return by_id


def _validate_evidence(item: dict[str, Any], index: int) -> None:
    _text(item.get("id"), f"candidate.evidence[{index}].id")
    _text(item.get("capability"), f"candidate.evidence[{index}].capability")
    state = item.get("state")
    if state not in EVIDENCE_STATES:
        raise RoleTransitionError(
            f"candidate.evidence[{index}].state: expected one of {sorted(EVIDENCE_STATES)}, got {state!r}"
        )
    source_type = item.get("source_type", "unknown")
    if source_type not in SOURCE_TYPES:
        raise RoleTransitionError(f"candidate.evidence[{index}].source_type: unsupported {source_type!r}")
    confidence = item.get("confidence", "unknown")
    if confidence not in CONFIDENCE_LEVELS:
        raise RoleTransitionError(f"candidate.evidence[{index}].confidence: unsupported {confidence!r}")
    provenance = item.get("provenance", "unknown")
    if provenance not in PROVENANCE_TYPES:
        raise RoleTransitionError(f"candidate.evidence[{index}].provenance: unsupported {provenance!r}")
    _text(item.get("source_ref"), f"candidate.evidence[{index}].source_ref")
    _optional_text(item.get("observed_at"), f"candidate.evidence[{index}].observed_at")


def _validate_role_source(source: dict[str, Any], role_id: str, index: int) -> None:
    prefix = f"role_candidates[{role_id}].sources[{index}]"
    _text(source.get("id"), f"{prefix}.id")
    source_type = source.get("source_type")
    if source_type not in ROLE_SOURCE_TYPES:
        raise RoleTransitionError(
            f"{prefix}.source_type: expected one of {sorted(ROLE_SOURCE_TYPES)}, got {source_type!r}"
        )
    state = source.get("state", "Confirmed")
    if state not in EVIDENCE_STATES:
        raise RoleTransitionError(f"{prefix}.state: unsupported {state!r}")
    _text(source.get("source_ref"), f"{prefix}.source_ref")
    _text(source.get("observed_at"), f"{prefix}.observed_at")
    confidence = source.get("confidence", "unknown")
    if confidence not in CONFIDENCE_LEVELS:
        raise RoleTransitionError(f"{prefix}.confidence: unsupported {confidence!r}")
    provenance = source.get("provenance", source_type)
    if provenance != source_type:
        raise RoleTransitionError(
            f"{prefix}.provenance: expected {source_type!r} for role source, got {provenance!r}"
        )


def _validate_requirement(
    requirement: dict[str, Any],
    *,
    role_id: str,
    index: int,
    source_ids: set[str],
    evidence_ids: set[str],
) -> None:
    prefix = f"role_candidates[{role_id}].requirements[{index}]"
    _text(requirement.get("id"), f"{prefix}.id")
    _text(requirement.get("text"), f"{prefix}.text")
    kind = requirement.get("kind")
    if kind not in REQUIREMENT_KINDS:
        raise RoleTransitionError(f"{prefix}.kind: expected one of {sorted(REQUIREMENT_KINDS)}")

    refs = _list(requirement.get("source_refs"), f"{prefix}.source_refs")
    if not refs:
        raise RoleTransitionError(f"{prefix}.source_refs: at least one source is required")
    unknown_sources = sorted({_text(ref, f"{prefix}.source_refs") for ref in refs} - source_ids)
    if unknown_sources:
        raise RoleTransitionError(f"{prefix}.source_refs: unknown source id(s) {unknown_sources}")

    direct_ids = _list(requirement.get("direct_evidence_ids", []), f"{prefix}.direct_evidence_ids")
    transfer_ids = _list(requirement.get("transfer_evidence_ids", []), f"{prefix}.transfer_evidence_ids")
    direct = {_text(ref, f"{prefix}.direct_evidence_ids") for ref in direct_ids}
    transfer = {_text(ref, f"{prefix}.transfer_evidence_ids") for ref in transfer_ids}
    unknown_evidence = sorted((direct | transfer) - evidence_ids)
    if unknown_evidence:
        raise RoleTransitionError(f"{prefix}: unknown candidate evidence id(s) {unknown_evidence}")

    absent = requirement.get("candidate_absence_confirmed", False)
    if not isinstance(absent, bool):
        raise RoleTransitionError(f"{prefix}.candidate_absence_confirmed: expected boolean")
    if absent and direct:
        raise RoleTransitionError(
            f"{prefix}: direct evidence and candidate_absence_confirmed cannot both be set"
        )

    if transfer:
        _text(requirement.get("transfer_rationale"), f"{prefix}.transfer_rationale")
        _text(requirement.get("verification_question"), f"{prefix}.verification_question")
    else:
        _optional_text(requirement.get("transfer_rationale"), f"{prefix}.transfer_rationale")
        _optional_text(requirement.get("verification_question"), f"{prefix}.verification_question")


def validate_payload(payload: Any) -> dict[str, Any]:
    data = _mapping(payload, "payload")
    candidate = _mapping(data.get("candidate"), "candidate")
    evidence = [_mapping(item, f"candidate.evidence[{index}]") for index, item in enumerate(
        _list(candidate.get("evidence"), "candidate.evidence")
    )]
    for index, item in enumerate(evidence):
        _validate_evidence(item, index)
    evidence_by_id = _unique_ids(evidence, "candidate.evidence")

    roles = [_mapping(item, f"role_candidates[{index}]") for index, item in enumerate(
        _list(data.get("role_candidates"), "role_candidates")
    )]
    if not roles:
        raise RoleTransitionError("role_candidates: at least one role hypothesis is required")
    role_by_id = _unique_ids(roles, "role_candidates")

    for role_id, role in role_by_id.items():
        _text(role.get("label"), f"role_candidates[{role_id}].label")
        sources = [_mapping(item, f"role_candidates[{role_id}].sources") for item in _list(
            role.get("sources"), f"role_candidates[{role_id}].sources"
        )]
        if not sources:
            raise RoleTransitionError(f"role_candidates[{role_id}].sources: at least one source required")
        for index, source in enumerate(sources):
            _validate_role_source(source, role_id, index)
        source_by_id = _unique_ids(sources, f"role_candidates[{role_id}].sources")

        requirements = [_mapping(item, f"role_candidates[{role_id}].requirements") for item in _list(
            role.get("requirements"), f"role_candidates[{role_id}].requirements"
        )]
        if not requirements:
            raise RoleTransitionError(
                f"role_candidates[{role_id}].requirements: at least one sourced requirement required"
            )
        _unique_ids(requirements, f"role_candidates[{role_id}].requirements")
        for index, requirement in enumerate(requirements):
            _validate_requirement(
                requirement,
                role_id=role_id,
                index=index,
                source_ids=set(source_by_id),
                evidence_ids=set(evidence_by_id),
            )
    return data


def _source_is_confirmed(source: dict[str, Any]) -> bool:
    return (
        source.get("state", "Confirmed") == "Confirmed"
        and source.get("confidence", "unknown") in USABLE_CONFIDENCE_LEVELS
    )


def _candidate_evidence_is_direct(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("state") == "Confirmed"
        and evidence.get("confidence", "unknown") in USABLE_CONFIDENCE_LEVELS
        and evidence.get("source_type") in DIRECT_CANDIDATE_SOURCE_TYPES
        and evidence.get("provenance") in DIRECT_CANDIDATE_SOURCE_TYPES
    )


def _requirement_result(
    requirement: dict[str, Any],
    *,
    sources: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_refs = list(requirement["source_refs"])
    direct_ids = list(requirement.get("direct_evidence_ids", []))
    transfer_ids = list(requirement.get("transfer_evidence_ids", []))

    unconfirmed_sources = [source_id for source_id in source_refs if not _source_is_confirmed(sources[source_id])]
    direct_usable = all(_candidate_evidence_is_direct(evidence[evidence_id]) for evidence_id in direct_ids)

    if unconfirmed_sources:
        state = "Unknown"
        reason = "role_source_not_confirmed"
    elif direct_ids and direct_usable:
        state = "Matched"
        reason = "direct_confirmed_evidence"
    elif direct_ids:
        state = "Unknown"
        reason = "candidate_evidence_not_direct_confirmed"
    elif requirement.get("candidate_absence_confirmed", False):
        state = "Missing"
        reason = "candidate_absence_confirmed"
    else:
        state = "Unknown"
        reason = "no_comparable_confirmed_evidence"

    transfer = None
    if transfer_ids:
        transfer_usable = all(
            _candidate_evidence_is_direct(evidence[evidence_id]) for evidence_id in transfer_ids
        )
        transfer = {
            "status": (
                "hypothesis_with_confirmed_basis"
                if transfer_usable
                else "hypothesis_basis_unconfirmed"
            ),
            "evidence_ids": transfer_ids,
            "rationale": requirement["transfer_rationale"],
            "verification_question": requirement["verification_question"],
            "note": "transfer evidence is a hypothesis and never changes Requirement state to Matched",
        }

    return {
        "id": requirement["id"],
        "text": requirement["text"],
        "kind": requirement["kind"],
        "state": state,
        "reason": reason,
        "source_refs": source_refs,
        "direct_evidence_ids": direct_ids,
        "transfer_hypothesis": transfer,
    }


def _targeting_state(requirements: list[dict[str, Any]]) -> str:
    core = [item for item in requirements if item["kind"] == "core"]
    if not core:
        return "insufficient_role_evidence"
    if any(item["state"] == "Missing" for item in core):
        return "confirmed_core_gap"
    if any(item["state"] == "Unknown" for item in core):
        return "needs_validation"
    return "evidence_supported"


def evaluate(payload: Any) -> dict[str, Any]:
    data = validate_payload(payload)
    candidate_evidence = data["candidate"]["evidence"]
    evidence_by_id = {item["id"]: item for item in candidate_evidence}

    roles_out: list[dict[str, Any]] = []
    for role in data["role_candidates"]:
        sources = {item["id"]: item for item in role["sources"]}
        requirement_results = [
            _requirement_result(requirement, sources=sources, evidence=evidence_by_id)
            for requirement in role["requirements"]
        ]
        transfer_hypotheses = [
            {
                "requirement_id": item["id"],
                **item["transfer_hypothesis"],
            }
            for item in requirement_results
            if item["transfer_hypothesis"] is not None
        ]
        roles_out.append(
            {
                "id": role["id"],
                "label": role["label"],
                "targeting_state": _targeting_state(requirement_results),
                "requirements": requirement_results,
                "confirmed_reuse": [
                    {
                        "requirement_id": item["id"],
                        "evidence_ids": item["direct_evidence_ids"],
                    }
                    for item in requirement_results
                    if item["state"] == "Matched"
                ],
                "confirmed_gaps": [
                    item["id"] for item in requirement_results if item["state"] == "Missing"
                ],
                "unknowns": [
                    item["id"] for item in requirement_results if item["state"] == "Unknown"
                ],
                "transfer_hypotheses": transfer_hypotheses,
                "sources": list(role["sources"]),
            }
        )

    return {
        "model_version": MODEL_VERSION,
        "note": (
            "role hypotheses are compared independently; no fit score, hiring probability, "
            "hidden ranking, or automatic target-role selection is produced"
        ),
        "candidate": {
            "evidence_count": len(candidate_evidence),
            "confirmed_evidence_ids": [
                item["id"] for item in candidate_evidence if item["state"] == "Confirmed"
            ],
        },
        "roles": roles_out,
    }


def render_text(result: dict[str, Any]) -> str:
    lines = [
        f"model_version: {result['model_version']}",
        result["note"],
        "",
    ]
    for role in result["roles"]:
        lines.extend(
            [
                f"Role: {role['label']} ({role['id']})",
                f"Targeting state: {role['targeting_state']}",
            ]
        )
        for requirement in role["requirements"]:
            lines.append(
                f"- [{requirement['kind']}] {requirement['state']}: {requirement['text']} "
                f"(sources={','.join(requirement['source_refs']) or '-'})"
            )
            transfer = requirement.get("transfer_hypothesis")
            if transfer:
                lines.append(
                    "  transfer hypothesis: "
                    f"{transfer['status']} | verify: {transfer['verification_question']}"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _load_payload(path: str | None) -> Any:
    if path in (None, "-"):
        text = sys.stdin.read()
        suffix = ".json"
    else:
        source = Path(path)
        text = source.read_text(encoding="utf-8")
        suffix = source.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        import yaml

        return yaml.safe_load(text)
    return json.loads(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="-", help="JSON/YAML file, or - for stdin")
    parser.add_argument("--text", action="store_true", help="render a human-readable report")
    args = parser.parse_args(argv)
    try:
        result = evaluate(_load_payload(args.input))
    except (OSError, json.JSONDecodeError, RoleTransitionError, ValueError) as exc:
        print(f"role transition error: {exc}", file=sys.stderr)
        return 2
    if args.text:
        print(render_text(result), end="")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
