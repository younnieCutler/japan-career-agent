#!/usr/bin/env python3
"""The command line itself: the parser, and the one place a result becomes bytes.

Nothing here decides what a command means. The parser owns the argument contract and this
module owns the output boundary, so the machine JSON and the human projection are produced
once for every command rather than once per branch.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from pathlib import Path
from typing import Any, Iterable, Mapping

from dispatch import run_command
from document import GENERATED_DOCUMENT_TYPES
from guided import render_human as render_guided_human
from localization import normalize_language
from models import (
    CareerError,
    EXPERIENCE_CONTEXT_KINDS,
    FACT_CATEGORIES,
    PLAN_SIGNALS,
    PLAN_QUALITY_OPTIONS,
    PROFILE_AXES,
    PROJECT_STATUSES,
    SKILL_INVOCATION_TERMINAL_STATUSES,
    TRACKS,
)
from private_store import DOCUMENT_TYPES, PRIVATE_ENV
from render import available_templates
from routing import language_for
from sessions import SESSION_ENTRYPOINTS, SESSION_WORKFLOW_STAGES
from ux import attach as project_ux, error_payload, render_human
from vault import CareerVault, today, utc_now


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local-first Japan career agent runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_vault_argument(command: argparse.ArgumentParser) -> None:
        command.add_argument("--vault", default=os.environ.get("CAREER_VAULT"), help="initialized Career Vault; falls back to CAREER_VAULT")

    def add_workspace_argument(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--workspace", default=os.environ.get("CAREER_WORKSPACE"),
            help="job-search workspace containing data/pipeline.yml; defaults to the current directory",
        )

    def add_as_of_argument(command: argparse.ArgumentParser) -> None:
        # AC-21: the ONLY place a wall clock touches the temporal path. Everything downstream takes
        # `as_of` as a required parameter, so the same history and the same date always project the
        # same way, and a test can change the date without changing the system clock.
        command.add_argument(
            "--as-of", default=today().isoformat(), metavar="YYYY-MM-DD",
            help="project as of this date instead of today; the projection never reads the clock",
        )

    def add_output_format(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--format",
            dest="output_format",
            choices=("json", "human"),
            default="json",
            help="output format; JSON remains the default machine-readable contract",
        )

    init_parser = subparsers.add_parser("init")
    add_vault_argument(init_parser)
    add_output_format(init_parser)
    setup_parser = subparsers.add_parser(
        "setup",
        help="one-shot first run: init the vault (default ~/.career-agent-vault) + profile fields + doctor",
    )
    setup_parser.add_argument("--vault", default=os.environ.get("CAREER_VAULT"), help="defaults to CAREER_VAULT, then ~/.career-agent-vault")
    setup_parser.add_argument("--track", choices=sorted(TRACKS))
    setup_parser.add_argument("--target-role")
    setup_parser.add_argument("--graduation-year", type=int)
    setup_parser.add_argument("--language", default=None)
    add_output_format(setup_parser)
    ui_parser = subparsers.add_parser(
        "ui",
        help="start the local loopback GUI. Starting the server writes nothing; the GUI it serves "
             "saves drafts, cases and artifacts, and can approve evidence into the Career Vault "
             "with your confirmation",
    )
    add_vault_argument(ui_parser)
    add_workspace_argument(ui_parser)
    add_as_of_argument(ui_parser)
    ui_parser.add_argument("--port", type=int, default=0, help="loopback port; 0 chooses a free port")
    ui_parser.add_argument("--no-browser", action="store_true", help="print the launch URL without opening a browser")
    ui_parser.add_argument("--language", choices=("ko", "ja", "en"), default="ko")
    add_output_format(ui_parser)
    sessions_parser = subparsers.add_parser(
        "sessions", help="list resumable workflows with human context; this command is read-only",
    )
    add_vault_argument(sessions_parser)
    sessions_parser.add_argument("--workflow", choices=sorted(SESSION_WORKFLOW_STAGES))
    sessions_parser.add_argument("--archived", action="store_true", help="include safely archived work")
    add_output_format(sessions_parser)
    workflow_parser = subparsers.add_parser(
        "workflow",
        help="start, resume, save, review, approve, or archive host-neutral workflow state",
    )
    add_vault_argument(workflow_parser)
    workflow_parser.add_argument(
        "action",
        choices=("start", "resume", "save", "checkpoint", "propose", "approve", "archive", "restore"),
    )
    workflow_parser.add_argument("--workflow", choices=sorted(SESSION_WORKFLOW_STAGES))
    workflow_parser.add_argument(
        "--entrypoint", choices=sorted(SESSION_ENTRYPOINTS - {"unknown"}), default="cli",
    )
    workflow_parser.add_argument("--session-ref", help="opaque reference returned after an explicit choice")
    workflow_parser.add_argument(
        "--context",
        help="visible context label, or Employer / Project path, for an id-free exact choice",
    )
    workflow_parser.add_argument("--case-ref", help="opaque project reference for a career experience")
    workflow_parser.add_argument("--subject-json", default="{}", help="human context labels as a JSON object")
    workflow_parser.add_argument("--json", dest="draft_json", help="workflow draft JSON; '-' reads stdin")
    workflow_parser.add_argument("--revision", type=int, help="revision returned by resume; required for writes")
    workflow_parser.add_argument("--proposal-ref", help="opaque reviewed proposal reference")
    workflow_parser.add_argument("--stage", help="semantic stage for checkpoint")
    workflow_parser.add_argument("--current-item", help="human-semantic item currently in progress")
    workflow_parser.add_argument("--missing", action="append")
    workflow_parser.add_argument("--completed", action="append")
    add_output_format(workflow_parser)
    for command, field in (("set-job-search", "job_search"), ("set-employment-status", "employment_status")):
        axis_parser = subparsers.add_parser(
            command,
            help=f"set profile.{field}; this is the only command that may change it",
        )
        add_vault_argument(axis_parser)
        axis_parser.add_argument("value", choices=sorted(PROFILE_AXES[field]))
        add_output_format(axis_parser)
    guided_parser = subparsers.add_parser(
        "guided",
        help="show a canonical-state guided menu; writes require an explicit choice and confirmation",
    )
    add_vault_argument(guided_parser)
    add_workspace_argument(guided_parser)
    add_as_of_argument(guided_parser)
    guided_parser.add_argument(
        "--choice",
        action="append",
        default=[],
        help="deterministic action ID or one-based menu number; repeat for scripted confirmation",
    )
    guided_parser.add_argument(
        "--confirm",
        action="store_true",
        help="confirm a write-capable guided action after reviewing its summary",
    )
    guided_parser.add_argument("--message", help="user-described task for the start_task action")
    guided_parser.add_argument("--proposal-id", help="pending proposal to approve when more than one is available")
    guided_parser.add_argument("--evidence", action="append", help="evidence for approval; repeat for multiple sources")
    guided_parser.add_argument("--deadline", help="confirmed event deadline in YYYY-MM-DD")
    guided_parser.add_argument("--company", help="company name for an approved event")
    guided_parser.add_argument("--compensation", type=float, help="compensation amount for an approved event")
    guided_parser.add_argument("--currency", help="currency for --compensation, e.g. JPY")
    guided_parser.add_argument("--next-action", help="actual action that remains after approval")
    guided_parser.add_argument("--version", help="saved state version for the restore_state action")
    guided_parser.add_argument("--track", choices=sorted(TRACKS), help="track for guided setup")
    guided_parser.add_argument("--target-role", help="target role for guided setup")
    guided_parser.add_argument("--graduation-year", type=int, help="graduation year for guided shinsotsu setup")
    guided_parser.add_argument("--language", default=None, help="profile language for guided setup")
    add_output_format(guided_parser)
    doctor_parser = subparsers.add_parser("doctor")
    add_vault_argument(doctor_parser)
    add_workspace_argument(doctor_parser)
    doctor_parser.add_argument("--fix", action="store_true", help="migrate the legacy nested data/pipeline.yml shape")
    add_output_format(doctor_parser)
    run = subparsers.add_parser("run")
    add_vault_argument(run)
    run.add_argument("--mode", choices=("chat", "heartbeat", "discover"), required=True)
    run.add_argument("--message")
    run.add_argument("--track", choices=sorted(TRACKS))
    run.add_argument("--source", help="JSON file for discover; stdin is used when omitted")
    run.add_argument(
        "--non-work", dest="non_work", action="store_true",
        help="this experience did not happen at a job: a seminar, a thesis, a club, a volunteer "
             "shift. Same fields, different type, so coursework never reads as work history",
    )
    add_as_of_argument(run)
    add_output_format(run)
    work_events_parser = subparsers.add_parser(
        "work-events",
        help="read work events from the ledger; the query downstream skills use for evidence",
    )
    add_vault_argument(work_events_parser)
    work_events_parser.add_argument(
        "--confirmed",
        dest="confirmed_only",
        action="store_true",
        help="only user-confirmed events; drafts are proposals, not evidence",
    )
    # This boundary is UTC, not the local date `add_as_of_argument` uses. `occurred_at` is stored
    # in UTC, and comparing its day against a local calendar day drops an event the user just
    # recorded: west of UTC an evening capture lands on tomorrow's UTC day, which a local `today`
    # boundary then filters out. The fact projection keeps the local default because it compares
    # against plain `YYYY-MM-DD` fact dates that carry no timezone at all.
    work_events_parser.add_argument(
        "--as-of", default=utc_now()[:10], metavar="YYYY-MM-DD",
        help="include events captured on or before this UTC date; defaults to today in UTC. This "
             "is capture time, not when the work happened",
    )
    add_output_format(work_events_parser)
    add_project_parser = subparsers.add_parser(
        "add-project", help="propose a project, or an update to one that already exists",
    )
    add_vault_argument(add_project_parser)
    add_project_parser.add_argument("title")
    add_project_parser.add_argument("--project-id", help="update this project instead of adding one")
    add_project_parser.add_argument("--role")
    add_project_parser.add_argument("--scope")
    add_project_parser.add_argument("--summary")
    add_project_parser.add_argument(
        "--external-label", dest="external_label",
        help="safe name for recruiter-facing output when the real title cannot leave",
    )
    add_project_parser.add_argument("--status", choices=sorted(PROJECT_STATUSES))
    add_project_parser.add_argument("--from", dest="period_from", metavar="YYYY-MM[-DD]")
    add_project_parser.add_argument("--to", dest="period_to", metavar="YYYY-MM[-DD]")
    add_output_format(add_project_parser)
    add_context_parser = subparsers.add_parser(
        "add-context",
        help="propose a context an experience happened in: a company, a university, a club",
    )
    add_vault_argument(add_context_parser)
    add_context_parser.add_argument("label")
    add_context_parser.add_argument(
        "--kind", required=True, choices=sorted(EXPERIENCE_CONTEXT_KINDS),
        help="a context is not always an employer; this is the part a label cannot say",
    )
    add_context_parser.add_argument(
        "--context-id", dest="context_id", help="update this context instead of adding one",
    )
    add_context_parser.add_argument("--role")
    add_context_parser.add_argument("--summary")
    add_context_parser.add_argument(
        "--external-label", dest="external_label",
        help="safe name for recruiter-facing output when the real one cannot leave",
    )
    add_context_parser.add_argument("--from", dest="period_from", metavar="YYYY-MM[-DD]")
    add_context_parser.add_argument("--to", dest="period_to", metavar="YYYY-MM[-DD]")
    add_output_format(add_context_parser)
    contexts_parser = subparsers.add_parser(
        "contexts", help="confirmed contexts and how much hangs on each",
    )
    add_vault_argument(contexts_parser)
    contexts_parser.add_argument("--kind", choices=sorted(EXPERIENCE_CONTEXT_KINDS))
    add_output_format(contexts_parser)
    experiences_parser = subparsers.add_parser(
        "experiences",
        help="context, experience and the evidence under it; the 棚卸し view, with no total",
    )
    add_vault_argument(experiences_parser)
    experiences_parser.add_argument(
        "--context", dest="context_id", help="only experiences inside this context",
    )
    add_output_format(experiences_parser)
    model_parser = subparsers.add_parser(
        "document-model",
        help="arrange confirmed evidence for one target; reads the ledger and writes nothing",
    )
    add_vault_argument(model_parser)
    add_workspace_argument(model_parser)
    model_parser.add_argument("slug", help="the company slug in data/pipeline.yml")
    model_parser.add_argument(
        "--document-type", dest="document_type", default="shokumukeirekisho",
        choices=sorted(GENERATED_DOCUMENT_TYPES),
    )
    add_output_format(model_parser)
    check_parser = subparsers.add_parser(
        "document-check",
        help="the Career Fidelity Gate: whether written Japanese says what the evidence says",
    )
    check_parser.add_argument("--model", required=True, help="document-model output")
    check_parser.add_argument("--draft", required=True, help="evidence-grounded draft slots")
    check_parser.add_argument(
        "--humanized",
        help="the polished replacement; the draft is then checked as its predecessor too",
    )
    add_output_format(check_parser)
    render_parser = subparsers.add_parser(
        "document-render", help="render a checked document; an unchecked one is refused",
    )
    render_parser.add_argument("--model", required=True)
    render_parser.add_argument("--draft", required=True)
    render_parser.add_argument("--humanized")
    render_parser.add_argument(
        "--template", default="standard-chuto",
        choices=available_templates(Path(__file__).resolve().parent),
    )
    render_parser.add_argument(
        "--out", default="./career-docs", help="output directory, relative to CWD",
    )
    add_output_format(render_parser)
    for name, helptext in (
        ("maintenance-check", "situations worth mentioning, or none; never a scheduled reminder"),
        ("readiness", "independent readiness dimensions; there is no total and it is not intent"),
    ):
        sub = subparsers.add_parser(name, help=helptext)
        add_vault_argument(sub)
        sub.add_argument("--as-of", metavar="YYYY-MM-DD", help="defaults to today in UTC")
        add_output_format(sub)
    pool_parser = subparsers.add_parser(
        "evidence-pool",
        help="confirmed evidence grouped by project, the read a JD mapping starts from",
    )
    add_vault_argument(pool_parser)
    pool_parser.add_argument("--as-of", metavar="YYYY-MM-DD", help="defaults to today in UTC")
    add_output_format(pool_parser)
    weekly_parser = subparsers.add_parser(
        "weekly-review", help="this period's work evidence grouped by project, with the gaps worth asking about",
    )
    add_vault_argument(weekly_parser)
    weekly_parser.add_argument("--since", metavar="YYYY-MM-DD", help="defaults to seven days before --as-of")
    weekly_parser.add_argument("--as-of", metavar="YYYY-MM-DD", help="defaults to today in UTC")
    add_output_format(weekly_parser)
    projects_parser = subparsers.add_parser(
        "projects", help="list confirmed projects and how much evidence hangs on each",
    )
    add_vault_argument(projects_parser)
    projects_parser.add_argument("--status", choices=sorted(PROJECT_STATUSES))
    add_output_format(projects_parser)
    timeline_parser = subparsers.add_parser(
        "project-timeline", help="one project's confirmed work events, as ledger references",
    )
    add_vault_argument(timeline_parser)
    timeline_parser.add_argument("project_id")
    add_output_format(timeline_parser)
    link_parser = subparsers.add_parser(
        "link-work-event", help="point a pending work event at projects, or at none",
    )
    add_vault_argument(link_parser)
    link_parser.add_argument("proposal_id")
    link_parser.add_argument("--project", dest="primary", help="the project this work mainly belongs to")
    link_parser.add_argument(
        "--related", action="append", default=None,
        help="another project this work also belongs to; repeat for several",
    )
    link_parser.add_argument(
        "--none", dest="clear", action="store_true",
        help="record general work that belongs to no project",
    )
    add_output_format(link_parser)
    review_parser = subparsers.add_parser(
        "review-work-event",
        help="fill the structured fields of a pending work event before it is confirmed",
    )
    add_vault_argument(review_parser)
    review_parser.add_argument("proposal_id")
    review_parser.add_argument(
        "--json", dest="work_event_json", required=True,
        help="work_event fields as a JSON object; '-' reads stdin",
    )
    review_parser.add_argument(
        "--replace", action="store_true",
        help="replace the payload instead of merging, e.g. to clear a field back to Unknown",
    )
    add_output_format(review_parser)
    skills_parser = subparsers.add_parser(
        "skills",
        help="every installed Skill and whether it can run without a host; reads nothing from a Vault",
    )
    add_output_format(skills_parser)
    plan_parser = subparsers.add_parser(
        "plan",
        help="create a bounded host-coordinated Skill execution plan",
    )
    add_vault_argument(plan_parser)
    plan_parser.add_argument("--skill", required=True, help="the routed Domain Skill to start")
    plan_parser.add_argument("--goal", required=True, help="the user goal for this plan")
    plan_parser.add_argument(
        "--quality", action="append", choices=sorted(PLAN_QUALITY_OPTIONS), default=None,
        help="an explicitly requested optional Quality Skill; repeat for several",
    )
    add_output_format(plan_parser)
    plan_next_parser = subparsers.add_parser(
        "plan-next",
        help="reconcile a plan and return its next Host Skill step",
    )
    add_vault_argument(plan_next_parser)
    plan_next_parser.add_argument("plan_id")
    plan_next_parser.add_argument("--resume", action="store_true", help="rerun an input-paused step")
    plan_next_parser.add_argument("--retry", action="store_true", help="retry one failed step")
    plan_next_parser.add_argument(
        "--approval", choices=("continue", "abort"),
        help="resolve a needs_approval step without rerunning its Skill",
    )
    add_output_format(plan_next_parser)
    plan_status_parser = subparsers.add_parser(
        "plan-status",
        help="show one execution plan and its current linked invocation",
    )
    add_vault_argument(plan_status_parser)
    plan_status_parser.add_argument("plan_id")
    add_output_format(plan_status_parser)
    skill_open_parser = subparsers.add_parser(
        "skill-open",
        help="open a Skill invocation before its SOP runs; the host closes it with skill-report",
    )
    add_vault_argument(skill_open_parser)
    skill_open_parser.add_argument("--skill", required=True, help="a Skill named in `skills`")
    skill_open_parser.add_argument(
        "--entrypoint", choices=sorted(SESSION_ENTRYPOINTS - {"unknown"}), default="cli",
        help="who is opening this invocation; a host-required Skill opened from cli or gui closes "
             "immediately as unsupported rather than left running with nothing to close it",
    )
    skill_open_parser.add_argument("--reason", help="why this Skill was selected")
    skill_open_parser.add_argument("--goal", help="the task this invocation is meant to accomplish")
    skill_open_parser.add_argument("--plan-id", help="Gate D execution plan id")
    skill_open_parser.add_argument("--step-id", help="Gate D execution plan step id")
    add_output_format(skill_open_parser)
    skill_report_parser = subparsers.add_parser(
        "skill-report",
        help="close a Skill invocation opened by skill-open with what actually happened",
    )
    add_vault_argument(skill_report_parser)
    skill_report_parser.add_argument("invocation_id")
    skill_report_parser.add_argument(
        "--status", required=True, choices=sorted(SKILL_INVOCATION_TERMINAL_STATUSES),
    )
    skill_report_parser.add_argument(
        "--summary",
        help="what happened; required for completed/needs_input/needs_approval so a status this "
             "runtime cannot verify still carries evidence it means something",
    )
    skill_report_parser.add_argument(
        "--artifact", dest="artifacts", action="append", default=None,
        help="a file or reference the Skill produced; repeat for several",
    )
    skill_report_parser.add_argument(
        "--evidence", dest="evidence_used", action="append", default=None,
        help="evidence the Skill drew on; repeat for several",
    )
    skill_report_parser.add_argument(
        "--tool", dest="tools_used", action="append", default=None,
        help="a tool or command the Skill used; repeat for several",
    )
    skill_report_parser.add_argument(
        "--error", help="what went wrong; required for blocked/failed/unsupported",
    )
    skill_report_parser.add_argument(
        "--signal", dest="signals", action="append", choices=sorted(PLAN_SIGNALS), default=None,
        help="a fixed plan condition signal observed by the Host; repeat for several",
    )
    add_output_format(skill_report_parser)
    status_parser = subparsers.add_parser("status")
    add_vault_argument(status_parser)
    add_workspace_argument(status_parser)
    add_output_format(status_parser)
    proposals_parser = subparsers.add_parser(
        "proposals",
        help="list proposal metadata without exposing proposal bodies",
    )
    add_vault_argument(proposals_parser)
    proposals_parser.add_argument("--all", dest="include_all", action="store_true", help="include approved and superseded proposals")
    proposals_parser.add_argument("--limit", type=int, help="return at most N proposals (N must be positive)")
    proposals_parser.add_argument("--id", dest="proposal_id", help="review one proposal body explicitly")
    add_output_format(proposals_parser)
    approve_parser = subparsers.add_parser("approve")
    add_vault_argument(approve_parser)
    add_workspace_argument(approve_parser)
    approve_parser.add_argument("proposal_id")
    approve_parser.add_argument("--evidence", action="append", help="evidence for an event; repeat for multiple sources")
    approve_parser.add_argument("--deadline", help="confirmed event deadline in YYYY-MM-DD")
    approve_parser.add_argument("--company", help="company name for an offer/application event")
    approve_parser.add_argument("--compensation", type=float, help="compensation amount for an offer/application event")
    approve_parser.add_argument("--currency", help="currency for --compensation, e.g. JPY")
    approve_parser.add_argument("--next-action", help="actual action that remains after approval")
    add_output_format(approve_parser)
    restore_parser = subparsers.add_parser(
        "restore-state",
        help="replace the current state with a saved snapshot; the append-only ledger is kept",
    )
    add_vault_argument(restore_parser)
    restore_parser.add_argument("version")
    add_output_format(restore_parser)
    index_parser = subparsers.add_parser("index")
    add_vault_argument(index_parser)
    index_parser.add_argument("--include-archives", action="store_true", help="include 06-archives in the index")
    add_output_format(index_parser)
    context_parser = subparsers.add_parser("context")
    add_vault_argument(context_parser)
    context_parser.add_argument("--track", choices=sorted(TRACKS), help="override the profile/state track")
    context_parser.add_argument("--stage", help="select verified notes for this exact stage")
    add_as_of_argument(context_parser)
    add_output_format(context_parser)
    profile_parser = subparsers.add_parser(
        "personal-profile",
        help="current personal-profile projection; Unknown and Conflict are explicit states",
    )
    add_vault_argument(profile_parser)
    add_as_of_argument(profile_parser)
    add_output_format(profile_parser)
    timeline_parser = subparsers.add_parser(
        "personal-timeline",
        help="full labelled history for one fact key, including superseded records",
    )
    add_vault_argument(timeline_parser)
    timeline_parser.add_argument("--category", required=True, choices=sorted(FACT_CATEGORIES))
    timeline_parser.add_argument("--key", required=True, help="the logical fact key, e.g. jlpt")
    add_output_format(timeline_parser)
    personal_context_parser = subparsers.add_parser(
        "personal-context",
        help="stage-relevant personal context; --historical is the opt-in labelled comparison",
    )
    add_vault_argument(personal_context_parser)
    add_as_of_argument(personal_context_parser)
    personal_context_parser.add_argument("--stage", help="select facts relevant to this exact stage")
    personal_mode = personal_context_parser.add_mutually_exclusive_group()
    personal_mode.add_argument(
        "--historical", action="store_true",
        help="section 12.2: retrieve the requested superseded documents, every role labelled",
    )
    personal_mode.add_argument(
        "--candidate-profile", action="store_true",
        help="emit confirmed facts in CANDIDATE_PROFILE terms for the job-seeker skill to quote",
    )
    personal_context_parser.add_argument(
        "--type", dest="document_type", choices=sorted(DOCUMENT_TYPES),
        help="with --historical: restrict the comparison to this document type",
    )
    personal_context_parser.add_argument(
        "--company", help="with --historical: restrict the comparison to this company",
    )
    personal_context_parser.add_argument(
        "--document-id", action="append", dest="document_ids", metavar="ID",
        help="with --historical: compare these exact versions (repeatable; see private-list)",
    )
    personal_context_parser.add_argument(
        "--all-documents", action="store_true",
        help="with --historical: sweep every document instead of naming what is being compared",
    )
    add_output_format(personal_context_parser)
    fact_proposal_parser = subparsers.add_parser(
        "propose-fact",
        help="propose a personal fact backed by an imported document; approve confirms it",
    )
    # The private root comes from the Vault or CAREER_PRIVATE_HOME, as every other read of it does.
    add_vault_argument(fact_proposal_parser)
    fact_proposal_parser.add_argument("--document-id", required=True, help="see private-list")
    fact_proposal_parser.add_argument("--category", required=True, choices=sorted(FACT_CATEGORIES))
    fact_proposal_parser.add_argument("--key", required=True, help="the logical fact key, e.g. jlpt")
    fact_proposal_parser.add_argument(
        "--value", required=True, help="the value you are stating; this tool does not read the file",
    )
    fact_proposal_parser.add_argument("--effective-from", help="YYYY-MM-DD; when it became true")
    fact_proposal_parser.add_argument("--expires-on", help="YYYY-MM-DD; when it stops being valid")
    fact_proposal_parser.add_argument(
        "--supersedes", help="the confirmed fact id this one replaces (see personal-timeline)",
    )
    add_output_format(fact_proposal_parser)
    context_proposal_parser = subparsers.add_parser(
        "propose-context",
        help="create an approval-gated proposal from a SELF_ANALYSIS_PROFILE YAML",
    )
    add_vault_argument(context_proposal_parser)
    context_proposal_parser.add_argument("--source", required=True, help="CWD-relative SELF_ANALYSIS_PROFILE YAML")
    add_output_format(context_proposal_parser)

    def add_private_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("--private-home", help=f"private root; falls back to {PRIVATE_ENV}")
        command.add_argument("--vault", default=os.environ.get("CAREER_VAULT"), help="only used to derive <vault>/private")

    private_doctor_parser = subparsers.add_parser(
        "private-doctor",
        help="diagnose the private career-document store; never requires an initialized Vault",
    )
    add_private_arguments(private_doctor_parser)
    private_doctor_parser.add_argument(
        "--scan-root", action="append", default=None, metavar="DIR",
        help="directory to scan for stray personal documents; repeatable, defaults to the "
             "current working directory",
    )
    add_output_format(private_doctor_parser)
    private_import_parser = subparsers.add_parser(
        "private-import",
        help="copy a document into the private store; the original file is preserved",
    )
    add_private_arguments(private_import_parser)
    private_import_parser.add_argument("source")
    private_import_parser.add_argument("--type", dest="document_type", required=True, choices=DOCUMENT_TYPES)
    private_import_parser.add_argument("--effective-from", help="YYYY-MM-DD when the document became applicable")
    private_import_parser.add_argument("--company", help="company for a company-scoped ES/application document")
    private_import_parser.add_argument("--purpose", default="general")
    private_import_parser.add_argument("--language", default="ja")
    add_output_format(private_import_parser)
    private_list_parser = subparsers.add_parser(
        "private-list", help="list document metadata; document bodies are never printed",
    )
    add_private_arguments(private_list_parser)
    add_as_of_argument(private_list_parser)
    add_output_format(private_list_parser)
    return parser


def _output_language(args: argparse.Namespace, result: Mapping[str, Any] | None = None, home: CareerVault | None = None) -> str:
    """Choose human-output language without changing the machine contract."""
    if args.command == "run" and args.mode == "chat":
        message = args.message or ""
        return normalize_language((result or {}).get("language") or language_for(message))
    if args.command == "guided" and args.message:
        return language_for(args.message)
    # The GUI can fail before a Vault/profile is available. Its explicit launch locale must still
    # determine the recovery message instead of silently falling back to Korean.
    if args.command == "ui" and args.language:
        return normalize_language(args.language)
    if args.command == "setup" and args.language:
        return normalize_language(args.language)
    if result and isinstance(result.get("profile"), dict) and result["profile"].get("language"):
        return normalize_language(result["profile"].get("language"))
    if home is not None:
        try:
            return normalize_language(home.load_profile().get("language"))
        except (CareerError, OSError, ValueError):
            pass
    return normalize_language(None)


def _emit(args: argparse.Namespace, context: dict[str, Any]) -> int:
    """Project one result and write it out. Every successful command leaves through here."""
    result = project_ux(
        args.command,
        context["result"],
        args=vars(args),
        language=_output_language(args, context["result"], context.get("output_home")),
    )
    context["result"] = result
    if args.output_format == "human":
        # `guided` is the one command whose human form is a menu rather than a report, so it has
        # its own renderer. The machine JSON is identical in shape to every other command's.
        print(render_guided_human(result) if args.command == "guided" else render_human(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    # Only the commands that answer a yes/no question report it as an exit status. A `doctor` that
    # finds problems, or a `status` with pending proposals, succeeded at reporting: exiting non-zero
    # there would tell a script the command failed when it did exactly what it was asked to do.
    if context.get("ok_is_exit_status") and not result.get("ok", True):
        return 2
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    context: dict[str, Any] = {}
    try:
        context["result"] = run_command(args, context)
        return _emit(args, context)
    except CareerError as exc:
        result = error_payload(
            exc,
            language=_output_language(args, context.get("result"), context.get("home")),
        )
        if getattr(args, "output_format", "json") == "human":
            print(render_human(result), file=sys.stderr)
        else:
            print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        return 2
