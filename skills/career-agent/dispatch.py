#!/usr/bin/env python3
"""Map a parsed command to its owner, and nothing else.

This module holds no domain rule. It exists so that adding a command means adding an entry here
and a function in an owner module, rather than editing the parser and the runtime facade.
"""

from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path
from typing import Any

from approvals import approve, recover_approval
from diagnostics import doctor
from documents import build_document_model, check_document, render_document
from execution_plans import create_plan, next_step, plan_status
from experiences import (
    add_context,
    add_project,
    link_work_event,
    list_contexts,
    list_experiences,
    list_projects,
    private_records,
    run_context,
    show_project_timeline,
    work_events,
)
from guided_flow import run_guided
from ingest import read_stdin_utf8, run_discover, run_heartbeat, run_index
from lifecycle import restore_state, review_work_event
from models import CareerError
from onboarding import DEFAULT_VAULT_PATH, complete_onboarding, set_profile_axis, setup
from personal_timeline import (
    candidate_profile_values,
    document_states,
    historical_comparison,
    project,
    select_personal_context,
    timeline,
)
from persistence import read_jsonl
from private_store import (
    documents as private_documents,
    import_document,
    initialize_private_home,
    private_doctor,
    PrivateHome,
    resolve_private_home,
)
from proposals import list_proposals, propose_career_context, propose_fact, review_proposal, run_chat
from skill_invocations import open_invocation, report_invocation
from skill_registry import discover as discover_skills
from sessions import (
    approve_proposal as approve_workflow_proposal,
    archive_session,
    checkpoint_session,
    create_proposal as create_workflow_proposal,
    create_session,
    list_sessions,
    resume_session,
    resume_workflow,
    restore_session,
    save_draft,
)
from vault import CareerVault, initialize_vault
from views import (
    evidence_pool,
    maintenance_check,
    readiness,
    status,
    weekly_review,
    workspace_summary,
)


def run_private_command(args: argparse.Namespace) -> dict[str, Any]:
    """Private-store commands resolve their own root and never touch the Vault contract."""
    if args.command == "private-doctor":
        # The CLI boundary supplies the default scan root (section 13.1); the store itself never
        # invents one, so a caller always knows exactly what was walked.
        return private_doctor(args.private_home, args.vault, args.scan_root or [Path.cwd()])
    home = PrivateHome(resolve_private_home(args.private_home, args.vault))
    if args.command == "private-list":
        initialize_private_home(home)
        return {
            "private_home": str(home.path),
            "as_of": args.as_of,
            # Metadata only: raw document bodies never leave the private store (section 28.1).
            # `status` is derived here for the requested date, never read from the registry, which
            # records observation alone.
            "documents": document_states(private_documents(home), args.as_of),
        }
    return import_document(
        home, args.source, args.document_type,
        effective_from=args.effective_from, company=args.company,
        purpose=args.purpose, language=args.language,
    )


def _requires_approval_recovery(args: argparse.Namespace) -> bool:
    """Only gate commands that can write; read-only inspection must remain available."""
    if args.command == "workflow":
        return args.action != "resume"
    if args.command in {
        "setup", "guided", "approve", "restore-state", "index",
        "propose-fact", "propose-context",
        "set-job-search", "set-employment-status", "review-work-event",
        "add-project", "add-context", "link-work-event",
    }:
        return True
    if args.command == "doctor":
        return bool(args.fix)
    return args.command == "run"


def _workflow_resume(args: argparse.Namespace, home: CareerVault, *, archived: bool = False) -> dict[str, Any]:
    if args.session_ref:
        return resume_session(home, args.session_ref)
    if archived:
        rows = [
            row
            for row in list_sessions(
                home,
                workflow=args.workflow,
                include_archived=True,
                context=args.context,
            )["sessions"]
            if row["status"] == "archived"
        ]
        if len(rows) != 1:
            raise CareerError(
                "choose one archived workflow by its visible context",
                code="SESSION_NOT_FOUND" if not rows else "SESSION_AMBIGUOUS",
                details={"choices": rows},
            )
        return resume_session(home, rows[0]["session_id"])
    return resume_workflow(home, workflow=args.workflow, context=args.context)


def _json_object(raw: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CareerError(f"{label} must be valid JSON: {exc}", code="INVALID_INPUT") from exc
    if not isinstance(value, dict):
        raise CareerError(f"{label} must be a JSON object", code="INVALID_INPUT")
    return value


def _run_workflow(args: argparse.Namespace, home: CareerVault) -> dict[str, Any]:
    if args.action == "start":
        if not args.workflow:
            raise CareerError("workflow start requires --workflow", code="INVALID_INPUT")
        subject = _json_object(args.subject_json, "--subject-json")
        session = create_session(
            home,
            workflow=args.workflow,
            entrypoint=args.entrypoint,
            case_ref=args.case_ref,
            subject=subject,
        )
        return resume_session(home, session["session_id"])
    resumed = _workflow_resume(args, home, archived=args.action == "restore")
    if args.action == "resume":
        return resumed
    if args.revision is None:
        raise CareerError(
            "workflow writes require the revision returned by resume",
            code="INVALID_INPUT",
        )
    session_id = resumed["session"]["session_id"]
    if args.action == "save":
        if args.draft_json is None:
            raise CareerError("workflow save requires --json", code="INVALID_INPUT")
        raw = sys.stdin.read() if args.draft_json == "-" else args.draft_json
        draft = _json_object(raw, "--json")
        if resumed["session"]["workflow"] == "self_analysis" and "self_analysis_version" in draft:
            draft = {"profile": draft}
        return save_draft(
            home,
            session_id,
            draft,
            expected_revision=args.revision,
            entrypoint=args.entrypoint,
        )
    if args.action == "checkpoint":
        return checkpoint_session(
            home,
            session_id,
            stage=args.stage,
            current_item_ref=args.current_item,
            missing=args.missing,
            completed=args.completed,
            expected_revision=args.revision,
            entrypoint=args.entrypoint,
        )
    if args.action == "propose":
        return create_workflow_proposal(
            home,
            session_id,
            expected_revision=args.revision,
            entrypoint=args.entrypoint,
        )
    if args.action == "approve":
        proposal_id = args.proposal_ref
        if proposal_id is None:
            refs = resumed["session"]["proposal_refs"]
            if len(refs) != 1:
                raise CareerError(
                    "choose the reviewed proposal before approval",
                    code="PROPOSAL_NOT_FOUND" if not refs else "SESSION_AMBIGUOUS",
                )
            proposal_id = refs[0]
        return approve_workflow_proposal(
            home,
            session_id,
            proposal_id,
            expected_revision=args.revision,
            entrypoint=args.entrypoint,
        )
    if args.action == "archive":
        return archive_session(
            home,
            session_id,
            expected_revision=args.revision,
            entrypoint=args.entrypoint,
        )
    return restore_session(
        home,
        session_id,
        expected_revision=args.revision,
        entrypoint=args.entrypoint,
    )


def run_command(args: argparse.Namespace, context: dict[str, Any]) -> dict[str, Any]:
    """Run one parsed command and return its machine result.

    `context` carries what the CLI's failure path needs and a return value cannot supply, because a
    command can fail after a result already exists: the last result produced, the Vault the failure
    happened against, and the Vault whose profile decides the human output language. Only the
    branches that reach a Vault record one, which is why a `setup` that fails before initialization
    still reports in the language the user asked for rather than in a Vault's stored preference.
    """
    skills_root = Path(__file__).resolve().parent.parent
    if args.command == "setup":
        vault_path = Path(args.vault).expanduser() if args.vault else DEFAULT_VAULT_PATH
        setup_home = CareerVault(vault_path)
        if setup_home.initialized():
            recover_approval(setup_home)
        result = setup(vault_path, args.track, args.target_role, args.graduation_year, args.language)
        context["ok_is_exit_status"] = True
        return result
    if args.command == "ui":
        from gui.server import serve as serve_gui

        ui_vault = CareerVault(Path(args.vault).expanduser()) if args.vault else CareerVault(DEFAULT_VAULT_PATH)
        try:
            return serve_gui(
                port=args.port,
                no_browser=args.no_browser,
                home=ui_vault,
                workspace=args.workspace,
                as_of=args.as_of,
                language=args.language,
            )
        except OSError as exc:
            # The browser cannot display a recovery state before loopback is listening. The
            # application bridge owns conversion to a stable, localizable runtime error.
            raise CareerError(
                "local GUI could not start",
                code="GUI_START_FAILED",
                retryable=True,
            ) from exc
    if args.command == "guided":
        vault_path = Path(args.vault).expanduser() if args.vault else DEFAULT_VAULT_PATH
        guided_home = CareerVault(vault_path)
        if guided_home.initialized():
            recover_approval(guided_home, workspace=args.workspace)
        context["output_home"] = guided_home
        result = run_guided(
            guided_home,
            workspace=args.workspace,
            as_of=args.as_of,
            choices=args.choice,
            interactive=args.output_format == "human" and sys.stdin.isatty(),
            confirm=args.confirm,
            message=args.message,
            proposal_id=args.proposal_id,
            evidence=args.evidence,
            deadline=args.deadline,
            company=args.company,
            compensation=args.compensation,
            currency=args.currency,
            next_action=args.next_action,
            version=args.version,
            track=args.track,
            target_role=args.target_role,
            graduation_year=args.graduation_year,
            language=args.language,
        )
        context["ok_is_exit_status"] = True
        return result
    # AC-23: the private store is independent of the Vault, so these branch above the Vault
    # requirement. A user checking whether a resume is about to be committed must not first be
    # told to initialize an unrelated Vault.
    if args.command in ("private-doctor", "private-import", "private-list"):
        result = run_private_command(args)
        context["ok_is_exit_status"] = True
        return result
    if args.command == "skills":
        return {"skills": discover_skills(skills_root)}
    # These two read a model file that was already produced from the Vault, so requiring one
    # again would only ask for a path the answer does not depend on. The gate in particular
    # must stay runnable on its own: it is the check a caller runs before sending anything.
    if args.command in ("document-check", "document-render"):
        if args.command == "document-check":
            result = check_document(args.model, args.draft, args.humanized)
        else:
            result = render_document(
                args.model, args.draft, template=args.template, out_dir=args.out,
                humanized_path=args.humanized,
            )
        context["ok_is_exit_status"] = True
        return result
    if not args.vault:
        raise CareerError("--vault or CAREER_VAULT is required; the runtime never defaults to the current directory")
    home = CareerVault(Path(args.vault))
    context["home"] = home
    context["output_home"] = home
    if args.command == "init":
        result = initialize_vault(home.path)
        return result
    home.require_initialized()
    if _requires_approval_recovery(args):
        recover_approval(home, workspace=getattr(args, "workspace", None))
    result = _run_vault_command(args, home, skills_root)
    return result


def _run_vault_command(
    args: argparse.Namespace, home: CareerVault, skills_root: Path
) -> dict[str, Any]:
    """Every command that needs an initialized Vault, in one place."""
    if args.command == "plan":
        return create_plan(home, skills_root, goal=args.goal, skill=args.skill)
    if args.command == "plan-next":
        return next_step(
            home, args.plan_id, resume=args.resume, retry=args.retry, approval=args.approval,
        )
    if args.command == "plan-status":
        return plan_status(home, args.plan_id)
    if args.command == "set-job-search":
        return set_profile_axis(home, "job_search", args.value)
    if args.command == "set-employment-status":
        return set_profile_axis(home, "employment_status", args.value)
    if args.command == "doctor":
        return doctor(home, fix=args.fix, workspace=args.workspace)
    if args.command == "add-project":
        period = {k: v for k, v in {"from": args.period_from, "to": args.period_to}.items() if v is not None}
        fields = {
            "role": args.role, "scope": args.scope, "summary": args.summary, "status": args.status,
            "external_label": args.external_label, "period": period or None,
        }
        fields = {k: v for k, v in fields.items() if v is not None}
        return add_project(home, args.title, project_id=args.project_id, **fields)
    if args.command == "add-context":
        period = {k: v for k, v in {"from": args.period_from, "to": args.period_to}.items() if v is not None}
        fields = {
            "role": args.role, "summary": args.summary, "external_label": args.external_label,
            "period": period or None,
        }
        fields = {k: v for k, v in fields.items() if v is not None}
        return add_context(home, args.kind, args.label, context_id=args.context_id, **fields)
    if args.command == "document-model":
        return build_document_model(
            home, args.slug, workspace=args.workspace, document_type=args.document_type,
        )
    if args.command == "contexts":
        return list_contexts(home, kind=args.kind)
    if args.command == "experiences":
        return list_experiences(home, context_id=args.context_id)
    if args.command == "maintenance-check":
        return maintenance_check(home, as_of=args.as_of)
    if args.command == "readiness":
        return readiness(home, as_of=args.as_of)
    if args.command == "evidence-pool":
        return evidence_pool(home, as_of=args.as_of)
    if args.command == "weekly-review":
        return weekly_review(home, since=args.since, as_of=args.as_of)
    if args.command == "projects":
        return list_projects(home, status=args.status)
    if args.command == "project-timeline":
        return show_project_timeline(home, args.project_id)
    if args.command == "link-work-event":
        if args.clear and (args.primary or args.related):
            raise CareerError(
                "--none records no project; it cannot be combined with --project or --related",
                code="INVALID_INPUT",
            )
        return link_work_event(
            home, args.proposal_id,
            primary=args.primary, related=args.related, clear=args.clear,
        )
    if args.command == "review-work-event":
        raw = sys.stdin.read() if args.work_event_json == "-" else args.work_event_json
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CareerError(f"--json must be valid JSON: {exc}", code="INVALID_INPUT") from exc
        return review_work_event(home, args.proposal_id, payload, replace=args.replace)
    if args.command == "work-events":
        return work_events(
            home, confirmed_only=args.confirmed_only, as_of=args.as_of,
        )
    if args.command == "skill-open":
        return open_invocation(
            home, skills_root, args.skill,
            entrypoint=args.entrypoint, reason=args.reason, goal=args.goal,
            plan_id=args.plan_id, step_id=args.step_id,
        )
    if args.command == "skill-report":
        return report_invocation(
            home, args.invocation_id, status=args.status, summary=args.summary,
            artifacts=args.artifacts, evidence_used=args.evidence_used,
            tools_used=args.tools_used, error=args.error, signals=args.signals,
        )
    if args.command == "status":
        return status(home, workspace=args.workspace)
    if args.command == "sessions":
        return list_sessions(
            home,
            workflow=args.workflow,
            include_archived=args.archived,
        )
    if args.command == "workflow":
        return _run_workflow(args, home)
    if args.command == "proposals":
        if args.limit is not None and args.limit < 1:
            raise CareerError("--limit must be a positive integer")
        return review_proposal(home, args.proposal_id) if args.proposal_id else list_proposals(home, include_all=args.include_all, limit=args.limit)
    if args.command == "approve":
        if args.workspace is not None:
            workspace_summary(args.workspace)
        return approve(
            home, args.proposal_id, args.evidence, args.deadline, args.company,
            args.compensation, args.currency, args.workspace, args.next_action,
        )
    if args.command == "restore-state":
        return restore_state(home, args.version)
    if args.command == "index":
        return run_index(home, include_archives=args.include_archives)
    if args.command == "context":
        return run_context(home, args.track, args.stage, args.as_of)
    if args.command == "personal-profile":
        return project(read_jsonl(home.events), args.as_of)
    if args.command == "personal-timeline":
        return {
            # Section 12.2: historical values are explicitly labelled, never presented as
            # current facts. The caller asked for history, so it is told which is which.
            "context_mode": "historical",
            "category": args.category,
            "key": args.key,
            "history": timeline(read_jsonl(home.events), args.category, args.key),
        }
    if args.command == "personal-context":
        return _personal_context(args, home)
    if args.command == "propose-fact":
        # No degradation here, unlike the read paths: this writes a provenance link, and a
        # store we cannot resolve is a link we cannot verify.
        store = PrivateHome(resolve_private_home(None, home.path))
        return propose_fact(
            home, store,
            document_id=args.document_id, category=args.category, key=args.key,
            value=args.value, effective_from=args.effective_from,
            expires_on=args.expires_on, supersedes=args.supersedes,
        )
    if args.command == "propose-context":
        return propose_career_context(home, args.source)
    if args.mode == "chat":
        message = args.message if args.message is not None else read_stdin_utf8().strip()
        if not message:
            raise CareerError("chat requires --message or stdin")
        result = run_chat(
            home, skills_root, message, args.track, args.as_of,
            non_work=args.non_work,
        )
        complete_onboarding(home, result)
        return result
    if args.mode == "heartbeat":
        return run_heartbeat(home)
    return run_discover(home, args.source)


def _personal_context(args: argparse.Namespace, home: CareerVault) -> dict[str, Any]:
    document_arguments = (
        args.document_type, args.company, args.document_ids, args.all_documents,
    )
    if not args.historical and any(document_arguments):
        # Accepting an argument and then ignoring it teaches the caller that a filter
        # was applied when none was. Say so instead.
        raise CareerError(
            "--type, --company, --document-id and --all-documents apply to --historical"
        )
    if args.stage and (args.historical or args.candidate_profile):
        raise CareerError(
            "--stage selects facts for the default mode and does not apply here"
        )
    events = read_jsonl(home.events)
    if args.candidate_profile:
        return candidate_profile_values(events, args.as_of)
    if args.historical:
        records, unavailable = private_records(home.path)
        result = historical_comparison(
            records, args.as_of,
            document_type=args.document_type, company=args.company,
            document_ids=tuple(args.document_ids or ()),
            all_documents=args.all_documents,
        )
        if unavailable:
            result["documents_unavailable"] = unavailable
        return result
    # Stage validation lives in the selector, not here: it is a public boundary
    # symbol and a caller that skips argparse must fail closed too.
    return select_personal_context(events, args.stage, args.as_of)
