"""Pure validation for Career Agent context and event contracts."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from models import (
    CAREER_CONTEXT_FIELDS,
    EVENT_STATUSES,
    REQUIRED_EVENT_FIELDS,
    TRACKS,
    CareerError,
    as_text,
)


NUMERIC_CLAIM = re.compile(
    r"(?<![A-Za-z])[+-]?\d+(?:[.,]\d+)?\s*(?:%|％|명|人|건|件|배|倍|만|万円|원|円)"
)
DATE_VALUE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T[^Z]+Z)?$")


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
