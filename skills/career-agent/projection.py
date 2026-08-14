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

from models import (  # noqa: E402
    CAREER_MODES,
    EVIDENCE_EVENT_TYPES,
    EXPERIENCE_CONTEXT_EVENT_TYPE,
    EXPERIENCE_SUPERSESSION_EVENT_TYPE,
    PIPELINE_STAGE,
    PROJECT_EVENT_TYPE,
    USER_CONFIRMATION_EVIDENCE,
    WORK_EVENT_TYPE,
    CareerError,
)
from validation import validate_event  # noqa: E402

# The types that record something without moving the user through the hiring flow. They share one
# name because three separate call sites need exactly this set, and three separate literals would
# be three chances to add a type to two of them.
UNROUTED_EVENT_TYPES = (
    EVIDENCE_EVENT_TYPES | {
        PROJECT_EVENT_TYPE, EXPERIENCE_CONTEXT_EVENT_TYPE, EXPERIENCE_SUPERSESSION_EVENT_TYPE,
        "career_context",
    }
)


_LEGAL_ENTITY_MARKERS = ("株式会社", "有限会社", "合同会社", "(株)")


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
    # An unrouted event has no application behind it. `company` on one names an employer the user
    # worked at, not a company they are applying to, and projecting it would put a past job in the
    # kanban as a live opportunity. The caller also checks `company`; this refuses by type, which
    # is the part a future caller cannot forget.
    if event.get("type") in UNROUTED_EVENT_TYPES:
        return None
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


PROJECT_FIELDS = ("title", "external_label", "role", "scope", "summary", "status", "period")


def projects_from_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The current state of every project, projected from confirmed project events.

    Grouped by `project.id` and accumulated in ledger order: a later event's non-null fields win,
    and the fields it leaves out keep what an earlier one said. That matches how the record is
    actually filled -- a project is named in one turn, given a role in another, and closed in a
    third -- without needing a supersession link, because the ledger already is the history.

    Confirmed only. A draft project is a proposal the user has not agreed to yet, and nothing
    should be filed under a project that does not exist for them.
    """
    projects: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("type") != PROJECT_EVENT_TYPE or event.get("status") != "confirmed":
            continue
        payload = event.get("project")
        if not isinstance(payload, dict) or not payload.get("id"):
            continue
        project_id = str(payload["id"])
        current = projects.setdefault(
            project_id, {"id": project_id, "first_seen": event.get("occurred_at")}
        )
        for field in PROJECT_FIELDS:
            value = payload.get(field)
            if value is None:
                continue
            # `period` merges a level deeper for the same reason `confidentiality` does: its two
            # ends are learned at different times. A project is given a start when it begins and an
            # end when it closes, and replacing the whole object on the second turn would drop the
            # start -- which is the opposite of "later non-null wins, earlier survives the silence".
            if field == "period" and isinstance(value, dict) and isinstance(current.get(field), dict):
                merged = dict(current[field])
                merged.update({key: item for key, item in value.items() if item is not None})
                current[field] = merged
            else:
                current[field] = value
        current["updated_at"] = event.get("occurred_at")
    for record in projects.values():
        record.setdefault("status", "unknown")
    return projects


EXPERIENCE_CONTEXT_FIELDS = ("kind", "label", "external_label", "role", "summary", "period")


def contexts_from_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The current state of every context, projected from confirmed context events.

    Identical accumulation to `projects_from_events`, for the identical reason: a context is named
    in one turn and given a period in another, and the ledger already is the history.
    """
    contexts: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("type") != EXPERIENCE_CONTEXT_EVENT_TYPE or event.get("status") != "confirmed":
            continue
        payload = event.get("experience_context")
        if not isinstance(payload, dict) or not payload.get("id"):
            continue
        context_id = str(payload["id"])
        current = contexts.setdefault(
            context_id, {"id": context_id, "first_seen": event.get("occurred_at")}
        )
        for field in EXPERIENCE_CONTEXT_FIELDS:
            value = payload.get(field)
            if value is None:
                continue
            if field == "period" and isinstance(value, dict) and isinstance(current.get(field), dict):
                merged = dict(current[field])
                merged.update({key: item for key, item in value.items() if item is not None})
                current[field] = merged
            else:
                current[field] = value
        current["updated_at"] = event.get("occurred_at")
    return contexts


def evidence_payload(event: dict[str, Any]) -> dict[str, Any]:
    """The evidence payload, under whichever key this event type carries it.

    Two keys rather than one because a `work_event` key on a university record would read as
    employment (see models.EXPERIENCE_EVENT_TYPE). Readers that only care about the fields --
    which is most of them -- go through here and never learn there were two.
    """
    for key in ("work_event", "experience"):
        payload = event.get(key)
        if isinstance(payload, dict):
            return payload
    return {}


def confirmed_evidence_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Confirmed evidence excluding rows retired by a confirmed append-only correction."""
    by_id = {str(event.get("id")): event for event in events if event.get("id")}
    retired: set[str] = set()
    for event in events:
        if event.get("type") != EXPERIENCE_SUPERSESSION_EVENT_TYPE or event.get("status") != "confirmed":
            continue
        validate_event(event)
        link = event["supersession"]
        predecessor_id = link["predecessor_event_id"]
        replacement_id = link["replacement_event_id"]
        predecessor = by_id.get(predecessor_id)
        replacement = by_id.get(replacement_id)
        if predecessor is None or replacement is None:
            raise CareerError("experience supersession references an unknown event")
        if any(row.get("type") not in EVIDENCE_EVENT_TYPES or row.get("status") != "confirmed"
               for row in (predecessor, replacement)):
            raise CareerError("experience supersession requires confirmed evidence events")
        if predecessor.get("type") != replacement.get("type"):
            raise CareerError("experience supersession must preserve the evidence event type")
        if predecessor_id in retired:
            raise CareerError("an experience event may be superseded only once")
        retired.add(predecessor_id)
    return [
        event for event in events
        if event.get("type") in EVIDENCE_EVENT_TYPES
        and event.get("status") == "confirmed"
        and event.get("id") not in retired
    ]


def experience_key(event: dict[str, Any]) -> str | None:
    """Which experience this evidence belongs to, or None when it hangs on nothing.

    A project id wins over an `experience_ref` and the validator refuses both at once, so one
    experience never ends up with two names. Returning None is a normal answer: a note captured
    before any 棚卸し belongs to no experience yet, and inventing a bucket for it would be a guess.
    """
    payload = evidence_payload(event)
    project_id = payload.get("primary_project_id")
    if isinstance(project_id, str) and project_id.strip():
        return f"project:{project_id}"
    reference = payload.get("experience_ref")
    if isinstance(reference, str) and reference.strip():
        return f"ref:{reference}"
    return None


def experiences_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Context → Experience → Evidence, grouped over the confirmed ledger.

    An experience is not stored anywhere. It is the set of confirmed evidence that names the same
    project or the same `experience_ref`, which is why a work event can be re-linked without any
    history being rewritten, and why the same evidence never exists twice to appear in two views.

    `unattached` is reported rather than hidden. Evidence that belongs to no recorded experience is
    still evidence, and a view that dropped it would understate what the user has.
    """
    projects = projects_from_events(events)
    contexts = contexts_from_events(events)
    experiences: dict[str, dict[str, Any]] = {}
    claims: list[dict[str, Any]] = []
    unattached: list[str] = []
    for event in confirmed_evidence_events(events):
        key = experience_key(event)
        if key is None:
            unattached.append(event["id"])
            continue
        payload = evidence_payload(event)
        confidentiality = payload.get("confidentiality")
        confidentiality = confidentiality if isinstance(confidentiality, dict) else {}
        contains_confidential = bool(confidentiality.get("contains_confidential"))
        material_evidence = [
            item
            for item in (event.get("evidence") or [])
            if item != USER_CONFIRMATION_EVIDENCE
            and item != "User confirmation in the local Career Agent GUI"
        ]
        detail = {
            field: payload[field]
            for field in (
                "role",
                "scope",
                "problem",
                "direct_actions",
                "individual_contribution",
                "team_result",
                "outcome_state",
                "metrics",
            )
            if payload.get(field) not in (None, "", [])
        }
        claims.append({
            "claim_id": event["id"],
            "experience_id": key,
            "context_id": payload.get("context_id"),
            "project_id": payload.get("primary_project_id"),
            "kind": payload.get("experience_kind"),
            "label": event.get("summary") or event.get("title"),
            "work_date": payload.get("work_date"),
            "evidence_count": len(event.get("evidence") or []),
            "material_evidence_count": len(material_evidence),
            "individual_contribution": bool(payload.get("individual_contribution")),
            "outcome_state": payload.get("outcome_state"),
            # Confidential narrative never enters summary/detail payloads that the GUI receives.
            "detail": None if contains_confidential else detail,
            "contains_confidential": contains_confidential,
            "external_use": confidentiality.get("external_use"),
        })
        current = experiences.setdefault(
            key,
            {
                "experience_id": key,
                "context_id": None,
                "kind": None,
                "label": key.split(":", 1)[1],
                "evidence_event_ids": [],
                "individual_contribution": 0,
                "team_result": 0,
                "metrics": 0,
                "external_use_review_required": [],
            },
        )
        current["evidence_event_ids"].append(event["id"])
        # Later non-null wins here too: the context and the kind are often supplied on a second
        # pass, and the first note about an experience rarely knows both.
        for field, source in (("context_id", "context_id"), ("kind", "experience_kind")):
            if payload.get(source) is not None:
                current[field] = payload[source]
        for field in ("individual_contribution", "team_result"):
            if payload.get(field):
                current[field] += 1
        if payload.get("metrics"):
            current["metrics"] += 1
        if ((payload.get("confidentiality") or {}).get("external_use")) == "unknown":
            current["external_use_review_required"].append(event["id"])
    for record in experiences.values():
        if record["experience_id"].startswith("project:"):
            project = projects.get(record["experience_id"].split(":", 1)[1], {})
            record["label"] = project.get("title") or record["label"]
            record["external_label"] = project.get("external_label")
            record["kind"] = record["kind"] or "project"
    return {
        "contexts": contexts,
        "experiences": sorted(experiences.values(), key=lambda item: item["experience_id"]),
        "claims": sorted(claims, key=lambda item: (str(item.get("work_date") or ""), item["claim_id"])),
        "unattached_evidence_ids": unattached,
    }


def work_event_project_ids(event: dict[str, Any]) -> list[str]:
    """Every project a work event points at, primary first, without duplicates."""
    payload = event.get("work_event")
    if not isinstance(payload, dict):
        return []
    ids: list[str] = []
    primary = payload.get("primary_project_id")
    if isinstance(primary, str) and primary.strip():
        ids.append(primary)
    for related in payload.get("related_project_ids") or []:
        if isinstance(related, str) and related.strip() and related not in ids:
            ids.append(related)
    return ids


def work_event_date(event: dict[str, Any]) -> str:
    """When the work happened, falling back to when it was captured.

    `work_date` is what the user said; `occurred_at` is when they said it. Recency should prefer
    the first and may only use the second because a note with no stated date has nothing better --
    not because the two mean the same thing.
    """
    payload = event.get("work_event")
    if isinstance(payload, dict) and payload.get("work_date"):
        return str(payload["work_date"])
    return str(event.get("occurred_at") or "")[:10]


def project_timeline(events: list[dict[str, Any]], project_id: str) -> list[dict[str, Any]]:
    """One project's confirmed work events in time order.

    References, not copies. The timeline is a view over the canonical ledger, so a work event that
    belongs to three projects appears in three timelines and still exists once.
    """
    entries = [
        {
            "event_id": event["id"],
            "date": work_event_date(event),
            "dated": bool((event.get("work_event") or {}).get("work_date")),
            "title": event.get("title"),
            "summary": event.get("summary"),
            "primary": (event.get("work_event") or {}).get("primary_project_id") == project_id,
        }
        for event in confirmed_evidence_events(events)
        if event.get("type") == WORK_EVENT_TYPE
        and project_id in work_event_project_ids(event)
    ]
    return sorted(entries, key=lambda entry: (entry["date"], entry["event_id"]))


def next_career_mode(event: dict[str, Any], job_search: str, current: str | None) -> str | None:
    """The career mode an event moves to, or None to leave it exactly where it was.

    Only an intent the user actually stated moves this. An earlier version derived the mode from
    the event's type and stage, and derivation produced two wrong answers: recording a work note
    while at 面接 with a search underway reset the mode to `maintenance`, and routine document
    upkeep with job search off became `opportunity_review` when no opportunity existed at all.

    So `career_mode` is carried on the event by the chat turn that read the user's words, and is
    absent whenever they stated no workflow intent. `active_search` additionally requires the
    declared `job_search`; without it the mode stays put rather than being promoted, because
    reading a posting is not the same as deciding to look.
    """
    stated = event.get("career_mode")
    if stated not in CAREER_MODES:
        return None
    if stated == "active_search" and job_search != "on":
        return None
    return stated if stated != current else None


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
    # Work events, experiences, the contexts and projects they happened in, and career-context
    # events all record something without moving the user through the hiring flow, so none touches
    # track, stage, flow_phase, or the mode. Someone at 面接 with a search underway who writes down
    # what they did at work today is still at 面接 and still searching.
    if event.get("type") in UNROUTED_EVENT_TYPES:
        next_state["last_event_id"] = event["id"]
        return next_state
    mode = next_career_mode(event, job_search, state.get("career_mode"))
    if mode is not None:
        next_state["career_mode"] = mode
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
