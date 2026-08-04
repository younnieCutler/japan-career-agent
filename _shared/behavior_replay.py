"""Deterministic replay adapters for critical product behavior.

These adapters deliberately do not simulate an LLM. They replay explicit input fixtures through
the deterministic matching and Career Agent paths, and run a policy-oracle contract replay for the
instruction-only interviewer without inventing a model identity.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CAREER_AGENT = ROOT / "skills" / "career-agent" / "career_agent.py"
UNRESOLVED = frozenset({"unprobed", "unknown", "Unknown", "user-stated-unverified", "conflict-needs-confirmation"})
AXES = ("Ownership", "Evidence", "Decision Logic", "Motivation & Fit", "Career Consistency", "Learning")
UNCERTAINTY_MARKERS = ("about", "around", "approximately", "i think", "mostly", "maybe", "roughly")


class ReplayError(ValueError):
    """Raised when a deterministic replay fixture is malformed or its contract fails."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayError(f"invalid replay fixture: {path.name}") from exc
    if not isinstance(value, dict):
        raise ReplayError(f"replay fixture must be an object: {path.name}")
    return value


def _require_skill(fixture: dict[str, Any], skill: str) -> None:
    if fixture.get("skill") != skill:
        raise ReplayError(f"fixture skill mismatch: expected {skill!r}")


def _mock_interviewer_contract(path: Path) -> dict[str, Any]:
    fixture = _load_json(path)
    _require_skill(fixture, "mock-interviewer")
    coverage = fixture.get("coverage") or {}
    if not isinstance(coverage, dict):
        raise ReplayError("mock-interviewer coverage must be an object")
    unresolved = [axis for axis in AXES if coverage.get(axis, "unprobed") in UNRESOLVED]
    next_probe = unresolved[0] if unresolved else None

    claim = fixture.get("claim") or {}
    if not isinstance(claim, dict):
        raise ReplayError("mock-interviewer claim must be an object")
    claim_text = claim.get("text", "")
    if not isinstance(claim_text, str):
        raise ReplayError("mock-interviewer claim.text must be a string")
    source = claim.get("source", "from-user")
    provenance = {
        "document": "document-stated",
        "document-stated": "document-stated",
        "confirmed": "confirmed-context",
        "confirmed-context": "confirmed-context",
        "user": "from-user",
        "from-user": "from-user",
    }.get(source, source)
    markers = claim.get("uncertainty_markers") or []
    if not isinstance(markers, list) or not all(isinstance(item, str) for item in markers):
        raise ReplayError("mock-interviewer claim.uncertainty_markers must be a string list")
    lowered = claim_text.lower()
    uncertainty_preserved = bool(markers) or any(marker in lowered for marker in UNCERTAINTY_MARKERS)

    axes = fixture.get("axes")
    if axes is None:
        readiness = "Not assessable"
    elif not isinstance(axes, dict):
        raise ReplayError("mock-interviewer axes must be an object")
    elif any(axes.get(axis) in UNRESOLVED for axis in AXES if axis in axes):
        readiness = "Needs targeted follow-up"
    else:
        outcome = fixture.get("outcome") or {}
        if not isinstance(outcome, dict):
            raise ReplayError("mock-interviewer outcome must be an object")
        quantitative = bool(outcome.get("quantitative_claim"))
        evidence_status = outcome.get("evidence_status")
        qualitative_bounded = bool(outcome.get("qualitative_bounded"))
        measured_unavailable = bool(outcome.get("measurement_unavailable"))
        if quantitative and evidence_status != "grounded":
            readiness = "Needs targeted follow-up"
        elif qualitative_bounded and measured_unavailable:
            readiness = "Ready"
        elif evidence_status == "grounded":
            readiness = "Ready"
        else:
            readiness = "Not assessable"

    confirmed = fixture.get("confirmed_context") or {}
    answer = fixture.get("answer_context") or {}
    contradiction = (
        isinstance(confirmed, dict)
        and isinstance(answer, dict)
        and confirmed.get("autonomy") == "essential"
        and answer.get("autonomy") == "avoid"
    )
    user_stopped = bool(fixture.get("user_stopped"))
    core_confirmed = bool(fixture.get("defensible_core_confirmed"))
    ambiguous_terms = fixture.get("ambiguous_terms") or []
    if not isinstance(ambiguous_terms, list):
        raise ReplayError("mock-interviewer ambiguous_terms must be a list")
    return {
        "case": fixture.get("case"),
        "coverage": {"unresolved_axes": unresolved, "next_probe_axis": next_probe},
        "claim": {
            "text": claim_text,
            "provenance": provenance,
            "uncertainty_preserved": uncertainty_preserved,
            "canonical_rewrite": False,
        },
        "readiness": {"state": readiness},
        "contradiction": {
            "detected": contradiction,
            "label": "Career Value Contradiction" if contradiction else None,
            "requires_user_confirmation": contradiction,
        },
        "session": {
            "assessment_emitted": user_stopped,
            "user_exit_allowed": True,
            "question_generation_stopped": user_stopped,
        },
        "defensible_core": {
            "confirmation_required": not core_confirmed,
            "canonical_write": False,
        },
        "probe": {
            "operational_definition": bool(ambiguous_terms),
            "counterexample": bool(fixture.get("high_impact_claim")),
        },
    }


def _without_interest(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "candidate_interest"}


def _matching(path: Path) -> dict[str, Any]:
    from _shared import matching_v3

    fixture = _load_json(path)
    _require_skill(fixture, "matching-simulator")
    variants = fixture.get("variants")
    payloads = variants if variants is not None else [fixture.get("payload")]
    if not isinstance(payloads, list) or not payloads or not all(isinstance(item, dict) for item in payloads):
        raise ReplayError("matching replay requires payload or variants")
    results = [matching_v3.evaluate(payload) for payload in payloads]
    if variants is None:
        return {
            "case": fixture.get("case"),
            "result": results[0],
        }
    return {
        "case": fixture.get("case"),
        "variants": [
            {
                "decision_status": result["decision_status"],
                "candidate_interest": result["candidate_interest"],
                "objective": _without_interest(result),
            }
            for result in results
        ],
        "objective_equal": all(_without_interest(result) == _without_interest(results[0]) for result in results[1:]),
        "decision_statuses": [result["decision_status"] for result in results],
        "interest_levels": [result["candidate_interest"]["interest_level"] for result in results],
    }


def _career_cli(vault: Path, cwd: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(CAREER_AGENT), arguments[0], "--vault", str(vault), *arguments[1:]],
        cwd=str(cwd),
        capture_output=True,
        check=False,
    )


def _json_stdout(result: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
    if result.returncode != 0:
        raise ReplayError("Career Agent command failed")
    try:
        value = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplayError("Career Agent returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise ReplayError("Career Agent JSON result must be an object")
    return value


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _career_approval_gate(vault: Path, workspace: Path) -> dict[str, Any]:
    _json_stdout(_career_cli(vault, workspace, "setup", "--track", "chuto", "--target-role", "Platform Engineer"))
    proposed = _json_stdout(
        _career_cli(vault, workspace, "run", "--mode", "chat", "--message", "Prepare interview evidence")
    )
    failed = _career_cli(vault, workspace, "approve", proposed["proposal"]["id"])
    return {
        "approval_blocked_without_evidence": failed.returncode == 2,
        "confirmed_event_count": len(_jsonl(vault / "02-state" / "events.jsonl")),
        "proposal_remains_pending": bool(_jsonl(vault / "02-state" / "proposals.jsonl"))
        and _jsonl(vault / "02-state" / "proposals.jsonl")[0].get("status") == "pending",
    }


def _career_approval_lifecycle(vault: Path, workspace: Path) -> dict[str, Any]:
    _json_stdout(_career_cli(vault, workspace, "setup", "--track", "chuto", "--target-role", "Platform Engineer"))
    proposed = _json_stdout(
        _career_cli(vault, workspace, "run", "--mode", "chat", "--message", "Prepare interview evidence")
    )
    evidence = "Confirmed interview preparation evidence"
    approved = _json_stdout(
        _career_cli(
            vault,
            workspace,
            "approve",
            proposed["proposal"]["id"],
            "--evidence",
            evidence,
            "--company",
            "Synthetic Co",
            "--workspace",
            str(workspace),
        )
    )
    proposals = _jsonl(vault / "02-state" / "proposals.jsonl")
    pipeline = workspace / "data" / "pipeline.yml"
    pipeline_text = pipeline.read_text(encoding="utf-8") if pipeline.exists() else ""
    event = approved["event"]
    return {
        "proposal_event_status_is_draft": proposals[0]["event"]["status"] == "draft",
        "confirmed_event_status": event["status"],
        "resolution_links_confirmed_event": proposals[0]["resolution"]["approved_event_id"] == event["id"],
        "pipeline_copies_evidence": evidence in pipeline_text,
        "pipeline_has_event_id": event["id"] in pipeline_text,
    }


def _career_concurrent_approval(vault: Path, workspace: Path) -> dict[str, Any]:
    _json_stdout(_career_cli(vault, workspace, "setup", "--track", "chuto", "--target-role", "Platform Engineer"))
    proposed = _json_stdout(
        _career_cli(vault, workspace, "run", "--mode", "chat", "--message", "Prepare interview evidence")
    )
    command = (
        "approve",
        proposed["proposal"]["id"],
        "--evidence",
        "Confirmed interview preparation evidence",
    )
    first = subprocess.Popen(
        [sys.executable, str(CAREER_AGENT), command[0], "--vault", str(vault), *command[1:]],
        cwd=str(workspace),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    second = subprocess.Popen(
        [sys.executable, str(CAREER_AGENT), command[0], "--vault", str(vault), *command[1:]],
        cwd=str(workspace),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    first.communicate()
    second.communicate()
    return {
        "return_codes": sorted([first.returncode, second.returncode]),
        "confirmed_event_count": len(_jsonl(vault / "02-state" / "events.jsonl")),
    }


def _career_context_approval(vault: Path, workspace: Path) -> dict[str, Any]:
    _json_stdout(_career_cli(vault, workspace, "setup", "--track", "chuto", "--target-role", "Platform Engineer"))
    source = workspace / "career-context.yml"
    source.write_text(
        "career_values:\n  must_have: [autonomy]\n  avoid: [unbounded overtime]\n",
        encoding="utf-8",
    )
    proposed = _json_stdout(_career_cli(vault, workspace, "propose-context", "--source", str(source)))
    before = _json_stdout(_career_cli(vault, workspace, "context", "--track", "chuto"))
    approved = _json_stdout(_career_cli(vault, workspace, "approve", proposed["proposal"]["id"]))
    after = _json_stdout(_career_cli(vault, workspace, "context", "--track", "chuto"))
    return {
        "proposal_is_not_confirmed_before_approval": before["career_context_confirmed"] is False,
        "approved_event_type": approved["event"]["type"],
        "confirmed_after_approval": after["career_context_confirmed"] is True,
        "canonical_value": after["career_context"]["career_values"]["must_have"],
    }


def _career_agent(path: Path) -> dict[str, Any]:
    fixture = _load_json(path)
    _require_skill(fixture, "career-agent")
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        vault = root / "vault"
        workspace = root / "workspace"
        workspace.mkdir()
        case = fixture.get("case")
        if case == "approval_gate":
            result = _career_approval_gate(vault, workspace)
        elif case == "approval_lifecycle":
            result = _career_approval_lifecycle(vault, workspace)
        elif case == "concurrent_approval":
            result = _career_concurrent_approval(vault, workspace)
        elif case == "context_approval":
            result = _career_context_approval(vault, workspace)
        else:
            raise ReplayError(f"unknown Career Agent replay case: {case!r}")
    return {"case": case, **result}


def run(kind: str, inputs: tuple[Path, ...]) -> dict[str, Any]:
    if len(inputs) != 1:
        raise ReplayError(f"{kind} replay requires exactly one fixture")
    if kind == "mock_interviewer_contract":
        return _mock_interviewer_contract(inputs[0])
    if kind == "matching_v3":
        return _matching(inputs[0])
    if kind == "career_agent":
        return _career_agent(inputs[0])
    raise ReplayError(f"unknown replay kind: {kind}")
