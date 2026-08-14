#!/usr/bin/env python3
"""Read-only projections of the confirmed record: readiness, maintenance, weekly review, pool.

No view writes, and no view produces a total. Readiness reports independent dimensions and
deliberately refuses to sum them into one number, because the axes measure different things.
"""

from __future__ import annotations

import datetime as dt
import sys

from pathlib import Path
from typing import Any

_SHARED_ROOT = Path(__file__).resolve().parent.parent.parent / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))
import pipeline_store  # noqa: E402

from experiences import pending_work_events, work_events  # noqa: E402
from models import (  # noqa: E402
    CareerError,
    employment_status_of,
    job_search_of,
    UNTRUSTED_DATA_MARKER,
    WORK_EVENT_TYPE,
)
from persistence import read_jsonl  # noqa: E402
from projection import (  # noqa: E402
    confirmed_evidence_events,
    experiences_from_events,
    pipeline_file,
    projects_from_events,
    work_event_date,
    work_event_project_ids,
    workspace_path,
)
from validation import iso_date  # noqa: E402
from vault import CareerVault, utc_now  # noqa: E402


def weekly_review(home: CareerVault, *, since: str | None = None, as_of: str | None = None) -> dict[str, Any]:
    """This period's work evidence, grouped by project, with what is worth asking about.

    Not a retrospective form. It shows what already accumulated and names the gaps that actually
    change how the record reads later, in the order they matter: what the user personally did,
    what came of it, where a number came from, what changed for the team, what they learned.

    A record with gaps is a good record. These are questions worth asking, never fields to force.
    """
    boundary = iso_date(as_of, "--as-of") or utc_now()[:10]
    start = iso_date(since, "--since") or (
        dt.date.fromisoformat(boundary) - dt.timedelta(days=7)
    ).isoformat()
    events = read_jsonl(home.events)
    projects = projects_from_events(events)
    pending, proposal_of = pending_work_events(home)
    # Windowed on capture time, not on when the work happened. The point of this view is "what did
    # I write down and not finish structuring", so a note captured today about last June belongs
    # here — it is exactly the one still needing a contribution and a result. `work_date` is shown
    # per row and is what recency uses downstream.
    recent = [
        event
        for event in [*pending, *confirmed_evidence_events(events)]
        if event.get("type") == WORK_EVENT_TYPE
        and start <= str(event.get("occurred_at") or "")[:10] <= boundary
    ]
    groups: dict[str, dict[str, Any]] = {}
    for event in recent:
        payload = event.get("work_event") or {}
        ids = work_event_project_ids(event) or [""]
        gaps = [name for name, ask in (
            ("individual_contribution", not payload.get("individual_contribution")),
            ("result", not payload.get("individual_contribution") and not payload.get("team_result")),
            ("metrics_evidence", bool(payload.get("metrics")) and not event.get("evidence")),
            ("improvements", not payload.get("improvements")),
            ("learning", not payload.get("learning")),
        ) if ask]
        for project_id in ids:
            group = groups.setdefault(
                project_id,
                {
                    "project_id": project_id or None,
                    "title": projects.get(project_id, {}).get("title") if project_id else None,
                    "events": [],
                },
            )
            group["events"].append({
                "event_id": event["id"],
                # Present for a draft, absent once confirmed. It is what `review-work-event` and
                # `approve` need, so a review can act on the row it is looking at.
                "proposal_id": proposal_of.get(event["id"]),
                "captured_on": str(event.get("occurred_at") or "")[:10],
                "work_date": payload.get("work_date"),
                "title": event.get("title"),
                "status": event.get("status"),
                "gaps": gaps,
            })
    ordered = sorted(groups.values(), key=lambda g: (g["project_id"] is None, str(g["title"] or "")))
    return {
        "mode": "weekly-review",
        "vault": str(home.path),
        "since": start,
        "as_of": boundary,
        "event_count": len(recent),
        "draft_count": sum(1 for event in recent if event.get("status") == "draft"),
        "confirmed_count": sum(1 for event in recent if event.get("status") == "confirmed"),
        "groups": ordered,
        # Ranked by what changes how the record reads later, not by field order. Ask at most a few.
        "ask_first": ["individual_contribution", "result", "metrics_evidence", "improvements", "learning"],
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "ok": True,
    }


def evidence_pool(home: CareerVault, *, as_of: str | None = None) -> dict[str, Any]:
    """Confirmed career evidence, grouped the way a JD is answered: by project, then by event.

    One call instead of three, because the mapping needs both levels at once — a project is what
    the user leads with, and the work events under it are what makes the claim checkable. Read
    only. Nothing here can be selected into a JD in a way that edits it.

    Every event carries `recency`, which prefers the stated `work_date` and falls back to capture
    time. The fallback is named in `dated` so a JD answer can say "recorded in August, work date
    not stated" instead of implying August work.
    """
    boundary = iso_date(as_of, "--as-of") or utc_now()[:10]
    events = read_jsonl(home.events)
    projects = projects_from_events(events)
    confirmed = [
        event
        for event in confirmed_evidence_events(events)
        if event.get("type") == WORK_EVENT_TYPE
        and event.get("status") == "confirmed"
        and str(event.get("occurred_at") or "")[:10] <= boundary
    ]

    def summarize(event: dict[str, Any]) -> dict[str, Any]:
        payload = event.get("work_event") or {}
        return {
            "event_id": event["id"],
            "title": event.get("title"),
            "summary": event.get("summary"),
            "recency": work_event_date(event),
            "dated": bool(payload.get("work_date")),
            "projects": work_event_project_ids(event),
            "work_event": payload,
            "evidence": event.get("evidence") or [],
        }

    grouped: dict[str, list[dict[str, Any]]] = {}
    unattached: list[dict[str, Any]] = []
    for event in confirmed:
        row = summarize(event)
        # A reference to a project this projection does not know about must not make the evidence
        # disappear. `link-work-event` already refuses an unknown id, so this should be
        # unreachable -- but silently dropping confirmed evidence from the view a JD is answered
        # from is the worst way for that assumption to turn out wrong.
        known = [project_id for project_id in row["projects"] if project_id in projects]
        if not known:
            unattached.append(row)
        for project_id in known:
            grouped.setdefault(project_id, []).append(row)
    return {
        "mode": "evidence-pool",
        "vault": str(home.path),
        "as_of": boundary,
        "projects": [
            {
                **record,
                "work_events": sorted(
                    grouped.get(project_id, []), key=lambda row: row["recency"], reverse=True
                ),
            }
            for project_id, record in projects.items()
        ],
        "unattached_work_events": sorted(unattached, key=lambda row: row["recency"], reverse=True),
        "confirmed_work_event_count": len(confirmed),
        # Only confirmed rows are here. A draft is a proposal the user never verified, and a
        # superseded one was replaced; neither may back a claim made to someone else.
        "confirmed_only": True,
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "ok": True,
    }


def maintenance_check(home: CareerVault, *, as_of: str | None = None) -> dict[str, Any]:
    """Situations worth mentioning, or none.

    Everything here is triggered by something that actually happened in the record, never by a
    date. "It has been a week, log your work" is an interruption with no information in it; "이
    프로젝트가 끝난 것 같은데 정리할까요?" is a suggestion the user can act on. If nothing here
    fires, the honest output is an empty list — say nothing rather than manufacture a nudge.

    Read only, and deliberately so: nothing in maintenance may change `job_search`, the career
    mode, or any record. It reports; the user decides.
    """
    boundary = iso_date(as_of, "--as-of") or utc_now()[:10]
    week_ago = (dt.date.fromisoformat(boundary) - dt.timedelta(days=7)).isoformat()
    events = read_jsonl(home.events)
    projects = projects_from_events(events)
    # Drafts count here. The situation worth mentioning is "you have been writing notes on this
    # project all week" -- which is true before any of them is approved, and is in fact the moment
    # a review helps most. Only the checks below that speak about finished records filter to
    # `confirmed`.
    pending, _ = pending_work_events(home)
    work = [e for e in [*pending, *confirmed_evidence_events(events)] if e.get("type") == WORK_EVENT_TYPE]
    confirmed = [e for e in work if e.get("status") == "confirmed"]
    suggestions: list[dict[str, Any]] = []

    per_project: dict[str, int] = {}
    for event in work:
        if str(event.get("occurred_at") or "")[:10] >= week_ago:
            for project_id in work_event_project_ids(event):
                per_project[project_id] = per_project.get(project_id, 0) + 1
    for project_id, count in sorted(per_project.items(), key=lambda item: -item[1]):
        if count >= 3:
            suggestions.append({
                "kind": "review_recent_project_activity",
                "project_id": project_id,
                "title": projects.get(project_id, {}).get("title"),
                "count": count,
                "detail": f"{count} notes this week on this project; a short review would tidy them",
            })

    for project_id, record in projects.items():
        if record.get("status") == "completed" and not record.get("summary"):
            suggestions.append({
                "kind": "project_ended_without_summary",
                "project_id": project_id,
                "title": record.get("title"),
                "detail": "this project is closed but has no summary yet",
            })

    missing = [
        event["id"]
        for event in confirmed
        if not (event.get("work_event") or {}).get("individual_contribution")
    ]
    if missing:
        suggestions.append({
            "kind": "individual_contribution_unknown",
            "event_ids": missing[:5],
            "count": len(missing),
            "detail": "confirmed notes where what the user personally did is still Unknown",
        })

    flagged = [
        event["id"]
        for event in confirmed
        if ((event.get("work_event") or {}).get("confidentiality") or {}).get("external_use")
        == "unknown"
    ]
    if flagged:
        suggestions.append({
            "kind": "external_use_unreviewed",
            "event_ids": flagged[:5],
            "count": len(flagged),
            "detail": "confidential material with external use not yet reviewed; unknown is not permission",
        })

    return {
        "mode": "maintenance-check",
        "vault": str(home.path),
        "as_of": boundary,
        "suggestions": suggestions,
        # Say at most one of these, and only when the turn has room for it. Silence is a valid
        # and frequent answer.
        "mention_at_most": 1,
        "changes_nothing": True,
        "ok": True,
    }


def readiness(home: CareerVault, *, as_of: str | None = None) -> dict[str, Any]:
    """Independent readiness dimensions. There is no total, and readiness is not intent.

    Each line answers its own question and is reported on its own. Collapsing them into one number
    would be the composite this repository refuses everywhere else, and it would also be read as
    "am I ready to leave", which is a different question from whether the record is current.
    """
    boundary = iso_date(as_of, "--as-of") or utc_now()[:10]
    cutoff = (dt.date.fromisoformat(boundary) - dt.timedelta(days=365)).isoformat()
    events = read_jsonl(home.events)
    projects = projects_from_events(events)
    confirmed = [
        e for e in confirmed_evidence_events(events) if e.get("type") == WORK_EVENT_TYPE
    ]
    # Recency uses the stated `work_date` and nothing else. Falling back to capture time is right
    # for ordering a timeline, where the alternative is no order at all; it is wrong here, because
    # it would turn "I wrote this down today about work I did five years ago" into confirmed
    # recent experience. An undated record is undated, and Unknown stays Unknown.
    dated = [e for e in confirmed if (e.get("work_event") or {}).get("work_date")]
    undated = [e for e in confirmed if not (e.get("work_event") or {}).get("work_date")]
    # A `YYYY-MM` sorts as the first of that month against a `YYYY-MM-DD` cutoff, so a month that
    # straddles the boundary reads as older. That is the conservative direction: it can understate
    # recency, never overstate it.
    recent = [e for e in dated if str(e["work_event"]["work_date"]) >= cutoff]
    with_contribution = [
        e for e in confirmed if (e.get("work_event") or {}).get("individual_contribution")
    ]
    with_metrics = [e for e in confirmed if (e.get("work_event") or {}).get("metrics")]
    needs_review = [
        e["id"] for e in confirmed
        if ((e.get("work_event") or {}).get("confidentiality") or {}).get("external_use") == "unknown"
    ]

    # Contexts and experiences cover the whole record, not just the working part of it: a new
    # graduate's university and seminar are the evidence base, and a dimension that only counted
    # work would report them as nothing.
    grouped = experiences_from_events(events)
    contexts = grouped["contexts"]
    experiences = grouped["experiences"]

    def dimension(subset: list[Any], total: list[Any]) -> str:
        if not total:
            return "Unknown"
        if len(subset) == len(total):
            return "Confirmed"
        return "Partial" if subset else "Unknown"

    return {
        "mode": "readiness",
        "vault": str(home.path),
        "as_of": boundary,
        "dimensions": {
            # `Stale` is a claim that the recent record is empty, so it may only be made when
            # every record is dated. One undated note could be last week's work; mixing it with
            # old dated ones is Partial, not Stale.
            "recent_work_evidence": (
                "Unknown" if not dated
                else "Partial" if undated
                else "Confirmed" if recent
                else "Stale"
            ),
            "project_history": dimension(
                [p for p in projects.values() if p.get("summary")], list(projects.values())
            ),
            "individual_contribution": dimension(with_contribution, confirmed),
            "metrics_evidence": dimension(with_metrics, confirmed),
            # A context with no period is a name without a timeline, which is exactly what an
            # employment history section cannot be built from.
            "career_contexts": dimension(
                [c for c in contexts.values() if c.get("period")], list(contexts.values())
            ),
            # An experience with no individual contribution cannot answer "what did *you* do",
            # which is the question every 職務経歴書 and every interview asks.
            "experience_coverage": dimension(
                [e for e in experiences if e["individual_contribution"]], experiences
            ),
        },
        "counts": {
            "projects": len(projects),
            "confirmed_work_events": len(confirmed),
            "dated_work_events": len(dated),
            "undated_work_events": len(undated),
            "dated_in_last_year": len(recent),
            "external_use_review_required": len(needs_review),
            "career_contexts": len(contexts),
            "experiences": len(experiences),
            "unattached_evidence": len(grouped["unattached_evidence_ids"]),
        },
        # Readiness says the record is current. It says nothing about wanting to leave.
        "job_search": job_search_of(home.load_profile()),
        # Not a score and not a threshold on one: it is the fact that the ledger holds nothing to
        # quote. Someone with seven years of experience and a fresh install is in exactly this
        # state, and telling them so is more useful than an analysis with nothing behind it.
        # Independent of `job_search`: a record worth having is worth having before the search.
        "bootstrap_suggested": not confirmed and not experiences and not contexts,
        "no_total_by_design": True,
        "ok": True,
    }


def workspace_summary(workspace: str | Path | None = None) -> dict[str, Any]:
    """Read a safe workspace projection without creating a missing workspace or pipeline."""
    resolved = workspace_path(workspace)
    explicit = workspace is not None
    if explicit and not resolved.is_dir():
        raise CareerError(
            f"workspace not found: {resolved}",
            code="WORKSPACE_NOT_FOUND",
            details={"workspace": str(resolved)},
        )
    pipeline = pipeline_file(workspace)
    data = pipeline_store.load(pipeline)
    companies = data.get("companies") if isinstance(data, dict) else []
    if not isinstance(companies, list):
        companies = []
    return {
        "path": str(resolved),
        "exists": resolved.is_dir(),
        "pipeline": str(pipeline),
        "pipeline_exists": pipeline.is_file(),
        "company_count": len(companies),
        "updated": data.get("updated") if isinstance(data, dict) else None,
    }


def status(home: CareerVault, workspace: str | Path | None = None) -> dict[str, Any]:
    state = home.load_state()
    profile = home.load_profile()
    pending_rows = [row for row in read_jsonl(home.proposals) if row.get("status") == "pending"]
    pending_kind = (
        str(pending_rows[0].get("kind") or "") or None
        if len(pending_rows) == 1
        else None
    )
    return {
        "vault": str(home.path),
        "profile": {
            "track": profile.get("track"),
            "career_status": profile.get("career_status", "active"),
            "target_role": profile.get("target_role"),
            # The two user-declared axes, always shown. Reading them here says what the user
            # declared; it never changes it, and `career_mode` in `state` below is projected
            # separately so a disagreement between the two stays visible instead of averaged away.
            "employment_status": employment_status_of(profile),
            "job_search": job_search_of(profile),
        },
        "state": state,
        "work_event_count": len(work_events(home, confirmed_only=True)["work_events"]),
        "event_count": len(read_jsonl(home.events)),
        "pending_proposals": len(pending_rows),
        "pending_kind": pending_kind,
        "posting_count": len(read_jsonl(home.postings)),
        "workspace": workspace_summary(workspace),
    }
