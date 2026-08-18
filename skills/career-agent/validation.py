"""Pure validation for Career Agent context and event contracts."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from models import (
    CAREER_CONTEXT_FIELDS,
    CAREER_MODES,
    EVENT_STATUSES,
    EXPERIENCE_CONTEXT_EVENT_TYPE,
    EXPERIENCE_CONTEXT_KINDS,
    EXPERIENCE_EVENT_TYPE,
    EXPERIENCE_KINDS,
    EXPERIENCE_SUPERSESSION_EVENT_TYPE,
    OUTCOME_STATES,
    EXTERNAL_USE_STATES,
    FACT_CATEGORIES,
    PROJECT_EVENT_TYPE,
    PROJECT_STATUSES,
    REQUIRED_EVENT_FIELDS,
    SKILL_EXECUTION,
    SKILL_INVOCATION_STATUSES,
    SKILL_INVOCATION_TERMINAL_STATUSES,
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
    # An experience and the context it happened in are unrouted for the same reason: a university
    # seminar belongs to no hiring market and to no step of a transition.
    unrouted = event.get("type") in {
        WORK_EVENT_TYPE,
        PROJECT_EVENT_TYPE,
        EXPERIENCE_EVENT_TYPE,
        EXPERIENCE_CONTEXT_EVENT_TYPE,
        EXPERIENCE_SUPERSESSION_EVENT_TYPE,
    }
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
    if event.get("type") == EXPERIENCE_SUPERSESSION_EVENT_TYPE:
        if event["status"] != "confirmed":
            raise CareerError("an experience supersession must be confirmed")
        link = event.get("supersession")
        if not isinstance(link, dict) or set(link) != {"predecessor_event_id", "replacement_event_id"}:
            raise CareerError("an experience supersession must name predecessor and replacement events")
        for field in ("predecessor_event_id", "replacement_event_id"):
            if not isinstance(link.get(field), str) or not link[field].strip():
                raise CareerError(f"event.supersession.{field} must be a non-empty event id")
        if link["predecessor_event_id"] == link["replacement_event_id"]:
            raise CareerError("an experience supersession cannot replace an event with itself")
        return
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
    if "experience" in event and event["experience"] is not None:
        validate_work_event(event["experience"], field="event.experience")
    if event.get("type") == EXPERIENCE_CONTEXT_EVENT_TYPE and event.get("experience_context") is None:
        raise CareerError("an experience_context event must carry event.experience_context")
    if "experience_context" in event and event["experience_context"] is not None:
        validate_experience_context(event["experience_context"])
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


def _validate_period(period: Any, field: str) -> None:
    if period is None:
        return
    if not isinstance(period, dict):
        raise CareerError(f"{field} must be an object or null")
    unknown = sorted(set(period) - {"from", "to", "current"})
    if unknown:
        raise CareerError(f"{field} has unknown fields: {', '.join(unknown)}")
    current = period.get("current")
    if current is not None and not isinstance(current, bool):
        raise CareerError(f"{field}.current must be a boolean or null")
    start = month_or_day(period.get("from"), f"{field}.from")
    end = month_or_day(period.get("to"), f"{field}.to")
    if current is True and end:
        raise CareerError(f"{field}.to must be empty while current is true")
    if start and end and end < start:
        raise CareerError(f"{field}.to is before period.from")


def validate_project(project: Any) -> None:
    """Validate the payload a `project` event carries.

    Only `title` is required. A project exists to give work events somewhere to hang, and
    demanding a role, a period, and a summary before the user can name it would make creating one
    the very form this workflow avoids. Everything else fills in later, or stays Unknown.

    `id` is present on every event about a project, including the first: it is the key the
    projection groups by, and without it two events about one project read as two projects.

    `external_label` exists because the honest internal name is often the unusable one. "내부 결제
    Phoenix 프로젝트" is what the user calls it and what should stay in their own record; a
    recruiter-facing document needs "payment reliability project". Keeping both means the
    abstraction is decided once, by the user, instead of being improvised per document — and the
    canonical title never has to be softened to make it safe to send.
    """
    if not isinstance(project, dict):
        raise CareerError("event.project must be an object")
    known = {"id", "title", "role", "scope", "summary", "status", "period", "external_label"}
    unknown = sorted(set(project) - known)
    if unknown:
        raise CareerError(f"event.project has unknown fields: {', '.join(unknown)}")
    for field in ("id", "title"):
        if not isinstance(project.get(field), str) or not project[field].strip():
            raise CareerError(f"event.project.{field} must be a non-empty string")
    for field in ("role", "scope", "summary", "external_label"):
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
    _validate_period(project.get("period"), "event.project.period")


def validate_experience_context(context: Any) -> None:
    """Validate the payload an `experience_context` event carries.

    Only `id`, `kind` and `label` are required, for the reason a project only requires a title: a
    context exists to give experiences somewhere to hang, and asking for a period and a role before
    the user can name their university would make creating one the form this workflow avoids.

    `kind` is required and closed, unlike the free-text fields around it, because it is the one
    thing a later reader cannot recover from the label. "A社" and "A大学" are both plausible as
    either an employer or a school to a downstream skill, and guessing wrong turns coursework into
    employment history in a 職務経歴書.

    `external_label` mirrors `project.external_label`: the honest internal name is often the
    unusable one, and deciding the safe abstraction once, here, beats improvising it per document.
    """
    if not isinstance(context, dict):
        raise CareerError("event.experience_context must be an object")
    known = {"id", "kind", "label", "external_label", "role", "summary", "period"}
    unknown = sorted(set(context) - known)
    if unknown:
        raise CareerError(f"event.experience_context has unknown fields: {', '.join(unknown)}")
    for field in ("id", "label"):
        if not isinstance(context.get(field), str) or not context[field].strip():
            raise CareerError(f"event.experience_context.{field} must be a non-empty string")
    if context.get("kind") not in EXPERIENCE_CONTEXT_KINDS:
        raise CareerError(
            "event.experience_context.kind must be one of: "
            f"{', '.join(sorted(EXPERIENCE_CONTEXT_KINDS))}"
        )
    for field in ("external_label", "role", "summary"):
        value = context.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise CareerError(
                f"event.experience_context.{field} must be a non-empty string or null"
            )
    _validate_period(context.get("period"), "event.experience_context.period")


def claim_surface(event: dict[str, Any]) -> str:
    """Every part of an event that can make a numeric claim, as one string.

    `metrics` is where an evidence payload puts its numbers, so leaving it out of the confirmation
    check would let "30% 감소" become confirmed history with no evidence behind it -- the exact
    thing the title/summary check already prevents everywhere else. Both payload keys are read:
    a thesis that claims a 40% speedup is a numeric claim exactly like a release that does.
    """
    surface = [str(event.get("summary") or ""), str(event.get("title") or "")]
    for key in ("work_event", "experience"):
        payload = event.get(key)
        if isinstance(payload, dict):
            surface.extend(str(item) for item in payload.get("metrics") or [])
    return " ".join(surface)


def validate_work_event(work_event: Any, *, field: str = "event.work_event") -> None:
    """Validate the evidence payload a `work_event` or an `experience_event` carries.

    Every field is optional: a note captured in one sentence is worth keeping, and an absent field
    is `Unknown` rather than a prompt to guess. Two things are refused outright. An unknown key is
    an error instead of an ignored typo, because a misspelled `metric` would otherwise drop the
    user's numbers and read as Unknown afterwards. And a payload flagged as containing confidential
    material must state its `external_use`, since the whole point of the flag is that "not decided
    yet" and "safe to send" cannot look the same.

    `individual_contribution` and `team_result` are separate keys and stay that way. Nothing here
    or downstream copies one into the other.

    One validator serves both event types because the payload is the same question in both: what
    was the role, what was the problem, what did *you* do, what did the team get, what number backs
    it. `field` only changes which key the error message names, so a mistake in an
    `experience_event` does not report itself as a work-event error.
    """
    if not isinstance(work_event, dict):
        raise CareerError(f"{field} must be an object or null")
    known = set(WORK_EVENT_TEXT_FIELDS) | set(WORK_EVENT_LIST_FIELDS) | {
        "confidentiality", "primary_project_id", "related_project_ids", "work_date",
        "context_id", "experience_kind", "experience_ref", "outcome_state",
    }
    unknown = sorted(set(work_event) - known)
    if unknown:
        raise CareerError(f"{field} has unknown fields: {', '.join(unknown)}")
    # Project links are references, never copies. One canonical work event is pointed at by every
    # project it belongs to, so changing a link cannot change what happened.
    primary = work_event.get("primary_project_id")
    if primary is not None and (not isinstance(primary, str) or not primary.strip()):
        raise CareerError(f"{field}.primary_project_id must be a project id or null")
    related = work_event.get("related_project_ids")
    if related is not None:
        if string_list_from(work_event, "related_project_ids") is None:
            raise CareerError(f"{field}.related_project_ids must be a list of project ids")
        if primary is not None and primary in related:
            raise CareerError(
                f"{field}.primary_project_id must not repeat in related_project_ids"
            )
        if len(set(related)) != len(related):
            raise CareerError(f"{field}.related_project_ids must not repeat a project")
    # Which context this happened in, and which experience inside it. Both stay optional: a note
    # that belongs to no recorded context is still evidence, and demanding one before the user has
    # done their 棚卸し would block capture on bookkeeping.
    context_id = work_event.get("context_id")
    if context_id is not None and (not isinstance(context_id, str) or not context_id.strip()):
        raise CareerError(f"{field}.context_id must be an experience_context id or null")
    kind = work_event.get("experience_kind")
    if kind is not None and kind not in EXPERIENCE_KINDS:
        raise CareerError(
            f"{field}.experience_kind must be one of: {', '.join(sorted(EXPERIENCE_KINDS))}"
        )
    # The grouping key for an experience that is not a project. A project already has an id, so
    # carrying both would give one experience two names and let them disagree.
    reference = work_event.get("experience_ref")
    if reference is not None:
        if not isinstance(reference, str) or not reference.strip():
            raise CareerError(f"{field}.experience_ref must be a non-empty string or null")
        if primary is not None:
            raise CareerError(
                f"{field}.experience_ref must be null when primary_project_id is set; "
                "the project id already identifies the experience"
            )
    # When the work actually happened, which is not when it was written down. Absent stays
    # Unknown: a note captured today about last June says June only if the user said June.
    month_or_day(work_event.get("work_date"), f"{field}.work_date")
    outcome_state = work_event.get("outcome_state")
    if outcome_state is not None and outcome_state not in OUTCOME_STATES:
        raise CareerError(
            f"{field}.outcome_state must be one of: {', '.join(sorted(OUTCOME_STATES))}"
        )
    for name in WORK_EVENT_TEXT_FIELDS:
        value = work_event.get(name)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise CareerError(f"{field}.{name} must be a non-empty string or null")
    for name in WORK_EVENT_LIST_FIELDS:
        if work_event.get(name) is None:
            continue
        if string_list_from(work_event, name) is None:
            raise CareerError(f"{field}.{name} must be a list of non-empty strings")
    confidentiality = work_event.get("confidentiality")
    if confidentiality is None:
        return
    if not isinstance(confidentiality, dict):
        raise CareerError(f"{field}.confidentiality must be an object or null")
    unknown = sorted(set(confidentiality) - {"contains_confidential", "external_use"})
    if unknown:
        raise CareerError(f"{field}.confidentiality has unknown fields: {', '.join(unknown)}")
    contains = confidentiality.get("contains_confidential", False)
    if not isinstance(contains, bool):
        raise CareerError(f"{field}.confidentiality.contains_confidential must be true or false")
    external_use = confidentiality.get("external_use")
    if external_use is None:
        if contains:
            raise CareerError(
                f"{field}.confidentiality.external_use is required once "
                "contains_confidential is true; use \"unknown\" when it has not been reviewed"
            )
        return
    if external_use not in EXTERNAL_USE_STATES:
        raise CareerError(
            f"{field}.confidentiality.external_use must be one of: "
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


def validate_skill_selection(selection: Any) -> None:
    """Validate the record `routing.select_skill()` returns.

    A selection is not an invocation: this only checks that the skill named exists in
    `SKILL_EXECUTION` and that the record says nothing that would let a reader mistake it for a
    completed run.
    """
    if not isinstance(selection, dict):
        raise CareerError("skill selection must be an object")
    skill = selection.get("skill")
    if not isinstance(skill, str) or not skill.strip():
        raise CareerError("skill_selection.skill must be a non-empty string")
    if skill not in SKILL_EXECUTION:
        raise CareerError(f"unknown skill: {skill}")
    if selection.get("status") != "selected":
        raise CareerError("skill_selection.status must be 'selected'")
    if selection.get("invocation") is not None:
        raise CareerError("skill_selection.invocation must be null; selection precedes invocation")


def validate_skill_result(result: Any, *, terminal: bool) -> None:
    """Validate an invocation record written by `skill-open` or `skill-report`.

    `terminal=False` is the shape `skill-open` writes (status is `started` or `unsupported`);
    `terminal=True` is what `skill-report` writes to close it. The two are checked separately
    because a `skill-report` call must never be allowed to reintroduce `started` -- that would let
    an invocation un-close itself.
    """
    if not isinstance(result, dict):
        raise CareerError("skill invocation must be an object")
    invocation_id = result.get("invocation_id")
    if not isinstance(invocation_id, str) or not invocation_id.strip():
        raise CareerError("skill_invocation.invocation_id must be a non-empty string")
    skill = result.get("skill")
    if skill not in SKILL_EXECUTION:
        raise CareerError(f"unknown skill: {skill}")
    status = result.get("status")
    if status not in SKILL_INVOCATION_STATUSES:
        raise CareerError(f"skill_invocation.status must be one of: {', '.join(sorted(SKILL_INVOCATION_STATUSES))}")
    if terminal and status not in SKILL_INVOCATION_TERMINAL_STATUSES:
        raise CareerError("skill-report must write a terminal status, not 'started' or 'selected'")
    if not terminal and status not in {"started", "unsupported"}:
        raise CareerError("skill-open must write 'started' or 'unsupported'")
    for field in ("artifacts", "evidence_used", "tools_used"):
        value = result.get(field, [])
        if not isinstance(value, list):
            raise CareerError(f"skill_invocation.{field} must be a list")
