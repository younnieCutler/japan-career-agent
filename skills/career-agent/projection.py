"""Workspace projection and legacy pipeline migration boundary."""

from __future__ import annotations

import hashlib
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

_SHARED_ROOT = Path(__file__).resolve().parent.parent.parent / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))
import pipeline_store  # noqa: E402

from models import PIPELINE_STAGE, WORK_EVENT_TYPE, CareerError  # noqa: E402


_LEGAL_ENTITY_MARKERS = ("株式会社", "有限会社", "合同会社", "(株)")
# Stages where a move is already decided and underway rather than being looked for. Reaching one
# of these is not a claim about search intent, so it does not depend on the job-search flag.
TRANSITION_STAGES = frozenset({"内定・条件交渉", "退職・入社準備", "内々定・内定・入社準備"})


def _canonical_company_name(name: str) -> str:
    value = unicodedata.normalize("NFKC", name).strip()
    marker_pattern = "|".join(re.escape(marker) for marker in _LEGAL_ENTITY_MARKERS)
    value = re.sub(rf"^(?:{marker_pattern})\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(rf"\s*(?:{marker_pattern})$", "", value, flags=re.IGNORECASE)
    return value.casefold().strip()


def _legacy_company_slug(name: str) -> str:
    return re.sub(r"[^\w]+", "-", name.strip().lower(), flags=re.UNICODE).strip("-")


def company_slug(name: str) -> str:
    """Canonical join key for pipeline and company-profile projections."""
    canonical = _canonical_company_name(name)
    slug = re.sub(r"[^\w]+", "-", canonical, flags=re.UNICODE).strip("-")
    return slug or hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]


def workspace_path(workspace: str | Path | None = None) -> Path:
    """Resolve the job-search workspace through the shared precedence implementation."""
    return pipeline_store.resolve_workspace(workspace)


def pipeline_file(workspace: str | Path | None = None) -> Path:
    return pipeline_store.resolve_pipeline_path(workspace)


def upsert_pipeline_entry(
    event: dict[str, Any], path: Path | None = None, workspace: str | Path | None = None,
) -> Path | None:
    """Project short confirmed-event metadata; evidence stays in the canonical event ledger."""
    path = path or pipeline_file(workspace)
    stage = PIPELINE_STAGE.get(event["stage"])
    day = str(event["occurred_at"])[:10]
    fields: dict[str, Any] = {"name": event["company"]}
    if stage is not None:
        fields["stage"] = stage
    if event.get("next_action"):
        fields["next_action"] = event["next_action"]
    if event.get("deadline"):
        fields["deadline"] = event["deadline"]
    hist_entry: dict[str, Any] = {"date": day, "event": event["title"]}
    if event.get("id"):
        hist_entry["event_id"] = event["id"]
    try:
        pipeline_store.upsert_company(
            path,
            company_slug(event["company"]),
            fields,
            history=hist_entry,
            slug_aliases=(_legacy_company_slug(event["company"]),),
        )
    except ImportError:  # pyyaml is optional for a degraded local proposal path
        return None
    return path


def next_career_mode(event: dict[str, Any], job_search: str) -> str:
    """The career mode a routed event implies, without ever inferring an active search.

    `active_search` is the only mode that asserts something about what the user intends, so it is
    the only one that requires them to have said it. With job search off the same event lands on
    `opportunity_review`: reading a JD, comparing offers, or answering a recruiter can then never
    promote someone into a search they never declared.
    """
    if event.get("type") == WORK_EVENT_TYPE:
        return "maintenance"
    if event.get("stage") in TRANSITION_STAGES:
        return "transition"
    return "active_search" if job_search == "on" else "opportunity_review"


def clamp_career_mode(state: dict[str, Any], job_search: str) -> dict[str, Any]:
    """Drop a stored `active_search` once job search is off.

    The step down is to `opportunity_review`, not `maintenance`: turning search off does not
    delete the opportunities already in the pipeline, and saying otherwise would hide them.
    """
    next_state = dict(state)
    if job_search == "off" and next_state.get("career_mode") == "active_search":
        next_state["career_mode"] = "opportunity_review"
    return next_state


def apply_event_to_state(
    state: dict[str, Any], event: dict[str, Any], *, job_search: str = "off",
) -> dict[str, Any]:
    next_state = dict(state)
    # A work event and a career-context event both record something without moving the user
    # through the hiring flow, so neither touches track, stage, or flow_phase. A work event does
    # set the mode: recording what happened at the current job is maintenance by definition.
    if event.get("type") == WORK_EVENT_TYPE:
        next_state["career_mode"] = "maintenance"
        next_state["last_event_id"] = event["id"]
        return next_state
    if event.get("type") == "career_context":
        next_state["last_event_id"] = event["id"]
        return next_state
    next_state["career_mode"] = next_career_mode(event, job_search)
    next_state["track"] = event["track"]
    next_state["stage"] = event["stage"]
    next_state["flow_phase"] = event["flow_phase"]
    next_state["last_event_id"] = event["id"]
    actions = [item for item in next_state.get("open_actions", []) if item.get("event_id") != event["id"]]
    if event.get("next_action"):
        actions.append({"text": event["next_action"], "event_id": event["id"], "stage": event["stage"]})
    next_state["open_actions"] = actions[-10:]
    if event.get("deadline"):
        deadlines = [item for item in next_state.get("deadlines", []) if item.get("event_id") != event["id"]]
        deadlines.append({"date": event["deadline"], "event_id": event["id"], "title": event["title"], "status": "open"})
        next_state["deadlines"] = sorted(deadlines, key=lambda item: item["date"])
    return next_state


def _merge_pipeline_companies(nested: list[dict[str, Any]], top_level: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for company in [*nested, *top_level]:
        if not isinstance(company, dict) or not str(company.get("slug") or "").strip():
            raise CareerError("legacy pipeline companies must be objects with a slug")
        slug = str(company["slug"])
        if slug not in merged:
            merged[slug] = dict(company)
            order.append(slug)
            continue
        history = merged[slug].get("history")
        merged[slug].update(company)
        if isinstance(history, list) and isinstance(company.get("history"), list):
            merged[slug]["history"] = history + company["history"]
    return [merged[slug] for slug in order]


def migrate_pipeline_file(path: Path) -> bool:
    """Flatten the pre-1.2.0 nested pipeline shape without dropping company history."""
    data = pipeline_store.load(path)
    nested = data.get("pipeline")
    if nested is None:
        return False
    if not isinstance(nested, dict):
        raise CareerError(f"{path}: legacy pipeline key must contain an object")

    def apply(current: dict[str, Any]) -> dict[str, Any]:
        legacy = current.pop("pipeline", {})
        nested_companies = legacy.get("companies") or []
        top_companies = current.get("companies") or []
        if not isinstance(nested_companies, list) or not isinstance(top_companies, list):
            raise CareerError(f"{path}: legacy pipeline companies must be lists")
        current["companies"] = _merge_pipeline_companies(nested_companies, top_companies)
        nested_updated = legacy.get("updated")
        top_updated = current.get("updated")
        if nested_updated or top_updated:
            current["updated"] = max(str(nested_updated or ""), str(top_updated or ""))
        for key, value in legacy.items():
            if key not in {"companies", "updated"} and key not in current:
                current[key] = value
        return current

    pipeline_store.mutate(path, apply)
    return True
