"""Pure validation for Career Agent context and event contracts."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from models import (
    CAREER_CONTEXT_FIELDS,
    EVENT_STATUSES,
    FACT_CATEGORIES,
    REQUIRED_EVENT_FIELDS,
    TRACKS,
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
    if event["track"] not in TRACKS:
        raise CareerError("event.track must be shinsotsu or chuto")
    if event["status"] not in EVENT_STATUSES:
        raise CareerError("event.status must be draft, confirmed, or superseded")
    for field in ("id", "stage", "flow_phase", "type", "title", "summary", "source"):
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
        if not event["evidence"]:
            if NUMERIC_CLAIM.search(event["summary"] + " " + event["title"]):
                raise CareerError("numeric claim is not present in evidence; event cannot be confirmed")
            raise CareerError("confirmed events require evidence; unsupported claims stay drafts")
        claims = NUMERIC_CLAIM.findall(event["summary"] + " " + event["title"])
        evidence_text = as_text(event["evidence"])
        evidence_claims = set(NUMERIC_CLAIM.findall(evidence_text))
        if claims and not all(claim in evidence_claims for claim in claims):
            raise CareerError("numeric claim is not present in evidence; event cannot be confirmed")


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
