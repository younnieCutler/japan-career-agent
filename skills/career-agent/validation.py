"""Pure validation for Career Agent context and event contracts."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from models import (
    CAREER_CONTEXT_FIELDS,
    CAREER_MODES,
    EVENT_STATUSES,
    EXTERNAL_USE_STATES,
    FACT_CATEGORIES,
    PROJECT_EVENT_TYPE,
    PROJECT_STATUSES,
    REQUIRED_EVENT_FIELDS,
    TRACKS,
    WORK_EVENT_TYPE,
    CareerError,
    as_text,
)


NUMERIC_CLAIM = re.compile(
    r"(?<![A-Za-z])[+-]?\d+(?:[.,]\d+)?\s*(?:%|％|명|人|건|件|배|倍|만|万円|원|円)"
)
DATE_VALUE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T[^Z]+Z)?$")


BARE_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def iso_date(value: Any, field: str) -> str | None:
    """Return a real calendar date as `YYYY-MM-DD`, or None when absent.

    The single date parser for every temporal contract in the agent. It exists because the same
    value used to be accepted by one code path and rejected by another (AC-22): `2026-13-45` was a
    hard error in `doctor` and a silently ignored "never expires" in context eligibility. A shared
    parser makes disagreement impossible rather than merely unlikely.

    The match is anchored on the whole string. Parsing a truncated prefix would accept
    `2026-01-20junk` and `2026-01-20T99:99:99Z` by quietly discarding the part that made them wrong
    -- and `effective_from`, `expires_on`, and `as_of` are bare-date contracts, so a timestamp
    arriving in one of them is a caller error worth surfacing, not trailing noise worth dropping.
    """
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not BARE_DATE.fullmatch(value):
        raise CareerError(f"{field} must be a bare calendar date (YYYY-MM-DD): {value!r}")
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise CareerError(f"{field} must be a real calendar date (YYYY-MM-DD): {value!r}") from exc


def iso_timestamp(value: Any, field: str) -> str:
    """Validate an observation instant: a UTC `YYYY-MM-DDThh:mm:ssZ`.

    `DATE_VALUE`'s `T[^Z]+Z` branch checks only that *something* sits between the `T` and the `Z`,
    so `2026-01-20T99:99:99Z` matched. This parses the time component instead of pattern-matching
    around it.

    The trailing `Z` is required rather than merely tolerated, and a bare date is not an instant.
    `fromisoformat` also accepts `+09:00` and naive local times, and admitting any of these would
    mean the ledger stores instants in notations that sort differently as strings -- while the
    contract says `observed_at` is a UTC instant and `utc_now()`, the only thing that has ever
    written one here, already emits exactly that.
    """
    if not isinstance(value, str) or not value.strip():
        raise CareerError(f"{field} must be a non-empty ISO timestamp string")
    if not value.endswith("Z") or "T" not in value:
        raise CareerError(
            f"{field} must be a UTC instant of the form YYYY-MM-DDThh:mm:ssZ: {value!r}"
        )
    try:
        dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise CareerError(
            f"{field} must be a UTC instant of the form YYYY-MM-DDThh:mm:ssZ: {value!r}"
        ) from exc
    return value


def string_list_from(value: dict[str, Any], field: str) -> list[str] | None:
    item = value.get(field)
    if not isinstance(item, list) or not all(isinstance(entry, str) and entry.strip() for entry in item):
        return None
    return item


def validate_career_context(value: Any) -> dict[str, Any]:
    """Validate the small, user-confirmed context payload shared across skills."""
    if not isinstance(value, dict):
        raise CareerError("career context must be an object")

    anchors = value.get("career_anchors")
    if anchors is not None:
        if not isinstance(anchors, dict):
            raise CareerError("career context career_anchors must be an object or null")
        if not isinstance(anchors.get("primary"), str) or not anchors["primary"].strip():
            raise CareerError("career context career_anchors.primary must be a non-empty string")
        secondary = anchors.get("secondary")
        if not isinstance(secondary, list) or not all(isinstance(entry, str) and entry.strip() for entry in secondary):
            raise CareerError("career context career_anchors.secondary must be a list of non-empty strings")
        if not isinstance(anchors.get("will_not_give_up"), str) or not anchors["will_not_give_up"].strip():
            raise CareerError("career context career_anchors.will_not_give_up must be a non-empty string")

    theme = value.get("career_theme")
    if theme is not None and (not isinstance(theme, str) or not theme.strip()):
        raise CareerError("career context career_theme must be a non-empty string or null")

    energy_map = value.get("energy_map")
    if energy_map is not None:
        if not isinstance(energy_map, dict):
            raise CareerError("career context energy_map must be an object or null")
        for field in ("energizes", "drains"):
            item = energy_map.get(field)
            if not isinstance(item, list) or not all(isinstance(entry, str) and entry.strip() for entry in item):
                raise CareerError(f"career context energy_map.{field} must be a list of non-empty strings")
        if energy_map.get("misfit_flag") is not None and not isinstance(energy_map["misfit_flag"], str):
            raise CareerError("career context energy_map.misfit_flag must be a string or null")

    values = value.get("career_values")
    if values is not None:
        if not isinstance(values, dict):
            raise CareerError("career context career_values must be an object or null")
        if string_list_from(values, "must_have") is None or string_list_from(values, "avoid") is None:
            raise CareerError("career context career_values requires must_have and avoid lists")

    if not any(value.get(field) is not None for field in CAREER_CONTEXT_FIELDS):
        raise CareerError("career context must contain at least one non-null field")
    return {field: value.get(field) for field in CAREER_CONTEXT_FIELDS}


def validate_event(event: dict[str, Any], *, for_confirmation: bool = False) -> None:
    """Validate an event without normalizing or silently filling missing evidence."""
    missing = [field for field in REQUIRED_EVENT_FIELDS if field not in event]
    if missing:
        raise CareerError(f"event missing fields: {', '.join(missing)}")
    # A work event records what happened at the job the user already has, and a project records
    # the context it happened in. Neither belongs to a hiring market or to a step of a transition,
    # so demanding a track and a stage would force an invented answer -- and the invented stage
    # would then move the user's routed state. Null is the honest value for these two types.
    unrouted = event.get("type") in {WORK_EVENT_TYPE, PROJECT_EVENT_TYPE}
    if not (unrouted and event["track"] is None) and event["track"] not in TRACKS:
        raise CareerError("event.track must be shinsotsu or chuto")
    if event["status"] not in EVENT_STATUSES:
        raise CareerError("event.status must be draft, confirmed, or superseded")
    for field in ("id", "type", "title", "summary", "source"):
        if not isinstance(event[field], str) or not event[field].strip():
            raise CareerError(f"event.{field} must be a non-empty string")
    for field in ("stage", "flow_phase"):
        if unrouted and event[field] is None:
            continue
        if not isinstance(event[field], str) or not event[field].strip():
            raise CareerError(f"event.{field} must be a non-empty string")
    if not isinstance(event["evidence"], list):
        raise CareerError("event.evidence must be a list")
    if event["deadline"] is not None and not isinstance(event["deadline"], str):
        raise CareerError("event.deadline must be an ISO date or null")
    if event["deadline"] and not DATE_VALUE.match(event["deadline"]):
        raise CareerError("event.deadline must use YYYY-MM-DD")
    if event["deadline"]:
        try:
            dt.date.fromisoformat(event["deadline"][:10])
        except ValueError:
            raise CareerError("event.deadline must be a real calendar date")
    # AC-22: `deadline` was calendar-checked while `occurred_at` was not validated at all, so an
    # impossible date entered the ledger through the field every projection orders by.
    iso_timestamp(event["occurred_at"], "event.occurred_at")
    if "fact" in event and event["fact"] is not None:
        validate_fact(event["fact"])
        if event["status"] == "superseded":
            # A fact's superseded state is DERIVED from the forward `supersedes` link, so a stored
            # copy is a second way to say the same thing -- and the two can disagree. Written by
            # hand it also removes the fact from the projection with no successor and no record of
            # why. Ordinary career events keep the status; fact-bearing ones do not.
            raise CareerError(
                "a fact-bearing event must be draft or confirmed; superseded is derived from "
                "another fact's supersedes link"
            )
    if "career_mode" in event and event["career_mode"] is not None:
        if event["career_mode"] not in CAREER_MODES:
            raise CareerError(f"event.career_mode must be one of: {', '.join(sorted(CAREER_MODES))}")
    if "work_event" in event and event["work_event"] is not None:
        validate_work_event(event["work_event"])
    if event.get("type") == PROJECT_EVENT_TYPE and event.get("project") is None:
        raise CareerError("a project event must carry event.project")
    if "project" in event and event["project"] is not None:
        validate_project(event["project"])
    if "company" in event and event["company"] is not None:
        if not isinstance(event["company"], str) or not event["company"].strip():
            raise CareerError("event.company must be a non-empty string")
    if "compensation" in event and event["compensation"] is not None:
        if isinstance(event["compensation"], bool) or not isinstance(event["compensation"], (int, float)) or event["compensation"] < 0:
            raise CareerError("event.compensation must be a number >= 0")
    if "currency" in event and event["currency"] is not None:
        if not isinstance(event["currency"], str) or not event["currency"].strip():
            raise CareerError("event.currency must be a non-empty string")
    if for_confirmation or event["status"] == "confirmed":
        claim_text = claim_surface(event)
        if not event["evidence"]:
            if NUMERIC_CLAIM.search(claim_text):
                raise CareerError("numeric claim is not present in evidence; event cannot be confirmed")
            raise CareerError("confirmed events require evidence; unsupported claims stay drafts")
        claims = NUMERIC_CLAIM.findall(claim_text)
        evidence_text = as_text(event["evidence"])
        evidence_claims = set(NUMERIC_CLAIM.findall(evidence_text))
        if claims and not all(claim in evidence_claims for claim in claims):
            raise CareerError("numeric claim is not present in evidence; event cannot be confirmed")


# `YYYY-MM` or `YYYY-MM-DD`. Month precision is a real answer, not a degraded one: "지난 6월"
# states a month, and demanding a day would invent the part the user did not say.
MONTH_OR_DAY = re.compile(r"^\d{4}-\d{2}(?:-\d{2})?$")

WORK_EVENT_TEXT_FIELDS = ("role", "scope", "problem", "individual_contribution", "team_result")
WORK_EVENT_LIST_FIELDS = (
    "direct_actions",
    "stakeholder_coordination",
    "reporting",
    "metrics",
    "improvements",
    "learning",
)


def month_or_day(value: Any, field: str) -> str | None:
    """A real calendar month or day, or None when absent. Never widened, never guessed."""
    if value is None:
        return None
    if not isinstance(value, str) or not MONTH_OR_DAY.match(value):
        raise CareerError(f"{field} must be YYYY-MM or YYYY-MM-DD")
    probe = value if len(value) == 10 else f"{value}-01"
    try:
        dt.date.fromisoformat(probe)
    except ValueError:
        raise CareerError(f"{field} must be a real calendar date") from None
    return value


def validate_project(project: Any) -> None:
    """Validate the payload a `project` event carries.

    Only `title` is required. A project exists to give work events somewhere to hang, and
    demanding a role, a period, and a summary before the user can name it would make creating one
    the very form this workflow avoids. Everything else fills in later, or stays Unknown.

    `id` is present on every event about a project, including the first: it is the key the
    projection groups by, and without it two events about one project read as two projects.
    """
    if not isinstance(project, dict):
        raise CareerError("event.project must be an object")
    known = {"id", "title", "role", "scope", "summary", "status", "period"}
    unknown = sorted(set(project) - known)
    if unknown:
        raise CareerError(f"event.project has unknown fields: {', '.join(unknown)}")
    for field in ("id", "title"):
        if not isinstance(project.get(field), str) or not project[field].strip():
            raise CareerError(f"event.project.{field} must be a non-empty string")
    for field in ("role", "scope", "summary"):
        value = project.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise CareerError(f"event.project.{field} must be a non-empty string or null")
    status = project.get("status")
    if status is not None and status not in PROJECT_STATUSES:
        raise CareerError(
            f"event.project.status must be one of: {', '.join(sorted(PROJECT_STATUSES))}"
        )
    period = project.get("period")
    if period is None:
        return
    if not isinstance(period, dict):
        raise CareerError("event.project.period must be an object or null")
    unknown = sorted(set(period) - {"from", "to"})
    if unknown:
        raise CareerError(f"event.project.period has unknown fields: {', '.join(unknown)}")
    start = month_or_day(period.get("from"), "event.project.period.from")
    end = month_or_day(period.get("to"), "event.project.period.to")
    if start and end and end < start:
        raise CareerError("event.project.period.to is before period.from")


def claim_surface(event: dict[str, Any]) -> str:
    """Every part of an event that can make a numeric claim, as one string.

    `work_event.metrics` is where a work event puts its numbers, so leaving it out of the
    confirmation check would let "30% 감소" become confirmed history with no evidence behind it --
    the exact thing the title/summary check already prevents everywhere else.
    """
    surface = [str(event.get("summary") or ""), str(event.get("title") or "")]
    work_event = event.get("work_event")
    if isinstance(work_event, dict):
        surface.extend(str(item) for item in work_event.get("metrics") or [])
    return " ".join(surface)


def validate_work_event(work_event: Any) -> None:
    """Validate the optional work-event payload a `work_event` type may carry.

    Every field is optional: a work note captured in one sentence is worth keeping, and an absent
    field is `Unknown` rather than a prompt to guess. Two things are refused outright. An unknown
    key is an error instead of an ignored typo, because a misspelled `metric` would otherwise drop
    the user's numbers and read as Unknown afterwards. And a payload flagged as containing
    confidential material must state its `external_use`, since the whole point of the flag is that
    "not decided yet" and "safe to send" cannot look the same.

    `individual_contribution` and `team_result` are separate keys and stay that way. Nothing here
    or downstream copies one into the other.
    """
    if not isinstance(work_event, dict):
        raise CareerError("event.work_event must be an object or null")
    known = set(WORK_EVENT_TEXT_FIELDS) | set(WORK_EVENT_LIST_FIELDS) | {
        "confidentiality", "primary_project_id", "related_project_ids", "work_date",
    }
    unknown = sorted(set(work_event) - known)
    if unknown:
        raise CareerError(f"event.work_event has unknown fields: {', '.join(unknown)}")
    # Project links are references, never copies. One canonical work event is pointed at by every
    # project it belongs to, so changing a link cannot change what happened.
    primary = work_event.get("primary_project_id")
    if primary is not None and (not isinstance(primary, str) or not primary.strip()):
        raise CareerError("event.work_event.primary_project_id must be a project id or null")
    related = work_event.get("related_project_ids")
    if related is not None:
        if string_list_from(work_event, "related_project_ids") is None:
            raise CareerError("event.work_event.related_project_ids must be a list of project ids")
        if primary is not None and primary in related:
            raise CareerError(
                "event.work_event.primary_project_id must not repeat in related_project_ids"
            )
        if len(set(related)) != len(related):
            raise CareerError("event.work_event.related_project_ids must not repeat a project")
    # When the work actually happened, which is not when it was written down. Absent stays
    # Unknown: a note captured today about last June says June only if the user said June.
    month_or_day(work_event.get("work_date"), "event.work_event.work_date")
    for field in WORK_EVENT_TEXT_FIELDS:
        value = work_event.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise CareerError(f"event.work_event.{field} must be a non-empty string or null")
    for field in WORK_EVENT_LIST_FIELDS:
        if work_event.get(field) is None:
            continue
        if string_list_from(work_event, field) is None:
            raise CareerError(f"event.work_event.{field} must be a list of non-empty strings")
    confidentiality = work_event.get("confidentiality")
    if confidentiality is None:
        return
    if not isinstance(confidentiality, dict):
        raise CareerError("event.work_event.confidentiality must be an object or null")
    unknown = sorted(set(confidentiality) - {"contains_confidential", "external_use"})
    if unknown:
        raise CareerError(
            f"event.work_event.confidentiality has unknown fields: {', '.join(unknown)}"
        )
    contains = confidentiality.get("contains_confidential", False)
    if not isinstance(contains, bool):
        raise CareerError(
            "event.work_event.confidentiality.contains_confidential must be true or false"
        )
    external_use = confidentiality.get("external_use")
    if external_use is None:
        if contains:
            raise CareerError(
                "event.work_event.confidentiality.external_use is required once "
                "contains_confidential is true; use \"unknown\" when it has not been reviewed"
            )
        return
    if external_use not in EXTERNAL_USE_STATES:
        raise CareerError(
            "event.work_event.confidentiality.external_use must be one of: "
            f"{', '.join(sorted(EXTERNAL_USE_STATES))}"
        )


def validate_fact(fact: Any) -> None:
    """Validate the optional personal-fact payload an event may carry (PRD sections 8, 8.1).

    `effective_to` is rejected outright rather than ignored: it is derived from supersession links
    (section 8.1), and a hand-authored copy is a second source of truth that goes stale silently the
    moment a link changes.
    """
    if not isinstance(fact, dict):
        raise CareerError("event.fact must be an object or null")
    if fact.get("category") not in FACT_CATEGORIES:
        raise CareerError(f"event.fact.category must be one of: {', '.join(sorted(FACT_CATEGORIES))}")
    if not isinstance(fact.get("key"), str) or not fact["key"].strip():
        raise CareerError("event.fact.key must be a non-empty string")
    if "value" not in fact:
        raise CareerError("event.fact.value is required; use null to record an explicit Unknown")
    if "effective_to" in fact:
        raise CareerError("event.fact.effective_to is derived from supersession and must not be set")
    iso_date(fact.get("effective_from"), "event.fact.effective_from")
    iso_date(fact.get("expires_on"), "event.fact.expires_on")
    supersedes = fact.get("supersedes")
    if supersedes is not None and (not isinstance(supersedes, str) or not supersedes.strip()):
        raise CareerError("event.fact.supersedes must be an event id or null")
