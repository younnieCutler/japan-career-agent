#!/usr/bin/env python3
"""Run the three deterministic P1 Career Agent workflow specifications.

The runner creates an isolated temporary workspace, invokes the canonical Career Agent and
matching CLIs, and checks semantic invariants instead of snapshots.  It never writes to the
repository's data directory and it never submits an application or sends a message.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
CAREER_AGENT = ROOT / "skills" / "career-agent" / "career_agent.py"
MATCHING = ROOT / "_shared" / "matching_v3.py"
REAL_APPLICATION_FIXTURE = ROOT / "examples" / "workflows" / "real-application" / "matching-input.example.json"
SYNTHETIC_DOCUMENT = ROOT / "examples" / "workflows" / "first-10-minutes" / "synthetic-resume.example.txt"
AS_OF = "2026-08-06"
WORKFLOW_NAMES = ("first-10-minutes", "real-application", "recovery")


class WorkflowFailure(RuntimeError):
    """Raised when a workflow invariant is not satisfied."""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise WorkflowFailure(message)


def _invoke(
    root: Path,
    arguments: list[str],
    *,
    expected_exit: int = 0,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Invoke a canonical CLI and parse its JSON result from the correct stream."""
    child_env = os.environ.copy()
    child_env.pop("CAREER_VAULT", None)
    child_env.pop("CAREER_WORKSPACE", None)
    if env:
        child_env.update(env)
    command = [sys.executable, str(CAREER_AGENT), *arguments]
    completed = subprocess.run(
        command,
        cwd=root,
        env=child_env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if completed.returncode != expected_exit:
        raise WorkflowFailure(
            f"command {' '.join(arguments)} exited {completed.returncode}, expected {expected_exit}: "
            f"{completed.stderr or completed.stdout}"
        )
    stream = completed.stdout if completed.returncode == 0 else completed.stderr
    try:
        payload = json.loads(stream)
    except json.JSONDecodeError as exc:
        raise WorkflowFailure(f"command {' '.join(arguments)} did not return JSON: {stream}") from exc
    if not isinstance(payload, dict):
        raise WorkflowFailure(f"command {' '.join(arguments)} returned a non-object JSON value")
    return payload


def _workflow_env(private_home: Path) -> dict[str, str]:
    return {"CAREER_PRIVATE_HOME": str(private_home)}


def _setup(root: Path, vault: Path, workspace: Path, private_home: Path) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    return _invoke(
        root,
        [
            "setup",
            "--vault",
            str(vault),
            "--track",
            "chuto",
            "--target-role",
            "Platform Engineer",
            "--language",
            "en",
        ],
        env=_workflow_env(private_home),
    )


def _first_10_minutes(root: Path) -> dict[str, Any]:
    vault = root / "vault"
    workspace = root / "workspace"
    private_home = root / "private-store"
    setup = _setup(root, vault, workspace, private_home)
    _assert(setup.get("ok") is True, "first-10-minutes: setup did not complete")
    _assert(
        any(item.get("id") == "vault-purpose" for item in setup["ux"].get("disclosures", [])),
        "first-10-minutes: setup did not explain the Vault at the relevant point",
    )

    status = _invoke(
        root,
        ["status", "--vault", str(vault), "--workspace", str(workspace)],
        env=_workflow_env(private_home),
    )
    _assert(status.get("pending_proposals") == 0, "first-10-minutes: initial state has a proposal")
    _assert(
        any(item.get("id") == "workspace-purpose" for item in status["ux"].get("disclosures", [])),
        "first-10-minutes: status did not explain the workspace",
    )

    source = root / "synthetic-resume.example.txt"
    source.write_text(SYNTHETIC_DOCUMENT.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    imported = _invoke(
        root,
        [
            "private-import",
            "--private-home",
            str(private_home),
            str(source),
            "--type",
            "resume",
            "--effective-from",
            "2026-01-01",
        ],
        env=_workflow_env(private_home),
    )
    document_id = str(imported.get("document_id") or "")
    _assert(bool(document_id), "first-10-minutes: private import did not return a document id")
    _assert(imported.get("source_preserved") is True, "first-10-minutes: private import did not preserve source")
    _assert(source.is_file(), "first-10-minutes: source file disappeared after import")
    _assert(
        any(item.get("id") == "private-store-boundary" for item in imported["ux"].get("disclosures", [])),
        "first-10-minutes: private-store boundary was not disclosed",
    )

    proposed = _invoke(
        root,
        [
            "propose-fact",
            "--vault",
            str(vault),
            "--document-id",
            document_id,
            "--category",
            "skill",
            "--key",
            "python",
            "--value",
            "Python platform maintenance",
            "--effective-from",
            "2026-01-01",
        ],
        env=_workflow_env(private_home),
    )
    proposal = proposed.get("proposal") if isinstance(proposed.get("proposal"), dict) else {}
    proposal_id = str(proposal.get("id") or "")
    _assert(proposal.get("status") == "pending", "first-10-minutes: proposal was not pending")
    _assert(proposed["ux"]["state"] == "needs_confirmation", "first-10-minutes: proposal did not require confirmation")
    _assert(
        any(item.get("id") == "proposal-approval-boundary" for item in proposed["ux"].get("disclosures", [])),
        "first-10-minutes: proposal/approval boundary was not disclosed",
    )

    reviewed = _invoke(
        root,
        ["proposals", "--vault", str(vault), "--id", proposal_id],
        env=_workflow_env(private_home),
    )
    _assert(reviewed.get("read_only") is True, "first-10-minutes: review changed the proposal")
    reviewed_event = reviewed.get("proposal", {}).get("event", {})
    _assert(
        f"private-document:{document_id}" in reviewed_event.get("evidence", []),
        "first-10-minutes: review did not expose the provenance link",
    )

    before_approval = _invoke(
        root,
        ["personal-profile", "--vault", str(vault), "--as-of", AS_OF],
        env=_workflow_env(private_home),
    )
    _assert(
        before_approval.get("skill", {}).get("python") is None,
        "first-10-minutes: proposal mutated canonical profile before approval",
    )

    approved = _invoke(
        root,
        [
            "approve",
            "--vault",
            str(vault),
            "--workspace",
            str(workspace),
            proposal_id,
            "--evidence",
            "Synthetic candidate statement confirms Python platform maintenance",
        ],
        env=_workflow_env(private_home),
    )
    _assert(approved.get("approved") is True, "first-10-minutes: approval did not complete")
    _assert(approved["ux"]["state"] == "completed", "first-10-minutes: approval UX was not completed")

    profile = _invoke(
        root,
        ["personal-profile", "--vault", str(vault), "--as-of", AS_OF],
        env=_workflow_env(private_home),
    )
    python_fact = profile.get("skill", {}).get("python", {})
    _assert(python_fact.get("state") == "confirmed", "first-10-minutes: approved fact is not projected")
    _assert(profile.get("ux", {}).get("state") in {"ready", "review"}, "first-10-minutes: profile result is not inspectable")
    return {
        "workflow": "first-10-minutes",
        "ok": True,
        "goal": "setup -> status -> private import -> proposal -> review -> explicit approval -> confirmed profile",
        "invariants": {
            "setup_ready": True,
            "proposal_pending_before_approval": True,
            "review_read_only": True,
            "canonical_unchanged_before_approval": True,
            "approval_explicit": True,
            "confirmed_projection": True,
            "source_preserved": bool(imported.get("source_preserved")),
        },
        "decision_point": "The user chooses whether to approve the reviewed proposal.",
        "product_does_not_do": [
            "infer a fact from document text",
            "auto-approve a proposal",
            "submit an application or send a message",
        ],
        "repeatable": True,
    }


def _contains_key(value: Any, fragments: tuple[str, ...]) -> bool:
    if isinstance(value, dict):
        return any(
            any(fragment in str(key).casefold() for fragment in fragments) or _contains_key(child, fragments)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_key(child, fragments) for child in value)
    return False


def _real_application(root: Path) -> dict[str, Any]:
    payload = json.loads(REAL_APPLICATION_FIXTURE.read_text(encoding="utf-8"))
    _assert(str(payload.get("company_name", "")).endswith("(Synthetic)"), "real-application: company is not synthetic")
    matching = subprocess.run(
        [sys.executable, str(MATCHING), str(REAL_APPLICATION_FIXTURE)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    _assert(matching.returncode == 0, f"real-application: matching command failed: {matching.stderr}")
    diagnosis = json.loads(matching.stdout)
    _assert(diagnosis.get("decision_status") == "conflict", "real-application: Conflict was not preserved")
    eligibility_states = {item.get("status") for item in diagnosis.get("eligibility", [])}
    _assert({"unknown", "conflict"} <= eligibility_states, "real-application: eligibility states are not independent")
    required = diagnosis.get("skills", {}).get("required_skills", {})
    _assert(all(required.get(bucket) for bucket in ("matched", "missing", "unknown")), "real-application: skill states are not independent")
    _assert(not _contains_key(diagnosis, ("score", "probability")), "real-application: forbidden aggregate outcome was produced")

    vault = root / "vault"
    workspace = root / "workspace"
    private_home = root / "private-store"
    _setup(root, vault, workspace, private_home)
    transition = _invoke(
        root,
        ["run", "--vault", str(vault), "--mode", "chat", "--message", "I need interview prep", "--as-of", AS_OF],
        env=_workflow_env(private_home),
    )
    _assert(transition.get("flow_phase") == "interview", "real-application: interview transition was not routed canonically")
    _assert(transition.get("proposal", {}).get("status") == "pending", "real-application: transition bypassed proposal gate")
    _assert(transition.get("ux", {}).get("state") == "needs_confirmation", "real-application: transition was not user-owned")
    return {
        "workflow": "real-application",
        "ok": True,
        "goal": "synthetic JD -> independent evidence diagnosis -> user review -> interview-preparation transition",
        "invariants": {
            "matched": True,
            "missing": True,
            "unknown": True,
            "conflict": True,
            "no_aggregate_outcome": True,
            "no_hiring_probability": True,
            "interview_transition": True,
        },
        "decision_point": "The user chooses whether to provide more evidence, keep Unknown/Conflict, or continue where the existing route allows.",
        "product_does_not_do": [
            "rank companies",
            "offset Missing or Conflict with Matched evidence",
            "command the user to apply",
        ],
        "repeatable": True,
    }


def _recovery(root: Path) -> dict[str, Any]:
    vault = root / "vault"
    workspace = root / "workspace"
    private_home = root / "private-store"
    _setup(root, vault, workspace, private_home)

    missing_workspace = _invoke(
        root,
        ["status", "--vault", str(vault), "--workspace", str(root / "missing-workspace")],
        expected_exit=2,
        env=_workflow_env(private_home),
    )
    _assert(missing_workspace.get("error_code") == "WORKSPACE_NOT_FOUND", "recovery: workspace blocker was not classified")
    _assert(missing_workspace.get("state_changed") is False, "recovery: workspace failure mutated state")
    _assert(
        any(item.get("id") == "workspace-resolution" for item in missing_workspace["ux"].get("disclosures", [])),
        "recovery: workspace resolution explanation was missing",
    )

    proposal = _invoke(
        root,
        ["run", "--vault", str(vault), "--mode", "chat", "--message", "I need interview prep", "--as-of", AS_OF],
        env=_workflow_env(private_home),
    )
    proposal_id = str(proposal["proposal"]["id"])
    missing_evidence = _invoke(
        root,
        ["approve", "--vault", str(vault), proposal_id],
        expected_exit=2,
        env=_workflow_env(private_home),
    )
    _assert(missing_evidence.get("error_code") == "EVIDENCE_REQUIRED", "recovery: missing evidence was not blocked")
    _assert(missing_evidence.get("state_changed") is False, "recovery: blocked approval changed state")
    _assert(not any(row.get("status") == "confirmed" for row in _read_jsonl(vault / "02-state" / "events.jsonl")), "recovery: blocked approval created a confirmed event")

    source = root / "synthetic-recovery-resume.example.txt"
    source.write_text(SYNTHETIC_DOCUMENT.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    imported = _invoke(
        root,
        ["private-import", "--private-home", str(private_home), str(source), "--type", "resume", "--effective-from", "2026-01-01"],
        env=_workflow_env(private_home),
    )
    document_id = str(imported["document_id"])
    fact_proposal = _invoke(
        root,
        [
            "propose-fact",
            "--vault",
            str(vault),
            "--document-id",
            document_id,
            "--category",
            "skill",
            "--key",
            "python",
            "--value",
            "Python platform maintenance",
            "--effective-from",
            "2026-01-01",
        ],
        env=_workflow_env(private_home),
    )
    record = _read_jsonl(private_home / "timeline" / "documents.jsonl")[0]
    blob = private_home / "blobs" / str(record["sha256"])
    _assert(blob.is_file(), "recovery: synthetic private document was not stored")
    blob.unlink()
    missing_document = _invoke(
        root,
        ["approve", "--vault", str(vault), fact_proposal["proposal"]["id"]],
        expected_exit=2,
        env=_workflow_env(private_home),
    )
    _assert(missing_document.get("error_code") == "DOCUMENT_NOT_FOUND", "recovery: missing private document was not revalidated")
    _assert(missing_document.get("state_changed") is False, "recovery: missing document changed canonical state")

    restore_root = root / "restore-case"
    restore_root.mkdir()
    restore_vault = restore_root / "vault"
    restore_workspace = restore_root / "workspace"
    restore_private = restore_root / "private-store"
    _setup(restore_root, restore_vault, restore_workspace, restore_private)
    first = _invoke(
        restore_root,
        ["run", "--vault", str(restore_vault), "--mode", "chat", "--message", "I need interview prep", "--as-of", AS_OF],
        env=_workflow_env(restore_private),
    )
    first_approval = _invoke(
        restore_root,
        ["approve", "--vault", str(restore_vault), first["proposal"]["id"], "--evidence", "Synthetic interview preparation evidence"],
        env=_workflow_env(restore_private),
    )
    second = _invoke(
        restore_root,
        ["run", "--vault", str(restore_vault), "--mode", "chat", "--message", "I received a job offer", "--as-of", AS_OF],
        env=_workflow_env(restore_private),
    )
    _invoke(
        restore_root,
        ["approve", "--vault", str(restore_vault), second["proposal"]["id"], "--evidence", "Synthetic offer evidence"],
        env=_workflow_env(restore_private),
    )
    restored = _invoke(
        restore_root,
        ["restore-state", "--vault", str(restore_vault), first_approval["version"]],
        env=_workflow_env(restore_private),
    )
    _assert(restored.get("ledger_retained") is True, "recovery: restore-state did not retain the ledger")
    _assert("State only" in str(restored.get("note")), "recovery: restore-state was described as a generic undo")
    _assert(restored["ux"]["reason"]["code"] == "STATE_RECOVERY_COMPLETE", "recovery: restore UX reason is unstable")
    _assert(len(_read_jsonl(restore_vault / "02-state" / "events.jsonl")) == 2, "recovery: restore-state rewound append-only history")
    return {
        "workflow": "recovery",
        "ok": True,
        "goal": "workspace/evidence/private-document failures -> safe recovery and snapshot restore",
        "invariants": {
            "workspace_missing_blocked": True,
            "missing_evidence_blocked": True,
            "private_document_revalidated": True,
            "canonical_state_unchanged_on_blockers": True,
            "restore_is_snapshot_only": True,
            "ledger_retained": True,
        },
        "decision_point": "The user chooses whether to repair evidence/storage or keep the proposal unapproved.",
        "product_does_not_do": [
            "bypass approval after a recovery error",
            "silently recreate missing provenance",
            "rewind append-only history with restore-state",
        ],
        "repeatable": True,
    }


RUNNERS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "first-10-minutes": _first_10_minutes,
    "real-application": _real_application,
    "recovery": _recovery,
}


def run_workflow(name: str) -> dict[str, Any]:
    if name not in RUNNERS:
        raise WorkflowFailure(f"unknown workflow: {name}")
    with tempfile.TemporaryDirectory(prefix=f"career-agent-{name}-") as directory:
        return RUNNERS[name](Path(directory))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", choices=("all", *WORKFLOW_NAMES), default="all")
    parser.add_argument("--format", choices=("json", "human"), default="json")
    args = parser.parse_args(argv)
    names = WORKFLOW_NAMES if args.workflow == "all" else (args.workflow,)
    try:
        results = [run_workflow(name) for name in names]
    except (OSError, WorkflowFailure, json.JSONDecodeError) as exc:
        print(f"workflow failure: {exc}", file=sys.stderr)
        return 1
    payload: dict[str, Any] = {"workflows": results, "count": len(results), "all_passed": True}
    if args.format == "human":
        print(f"P1 workflows passed: {len(results)}")
        for result in results:
            print(f"- {result['workflow']}: {result['goal']}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
