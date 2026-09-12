"""Deterministic application-history and learning-pattern core.

`data/pipeline.yml` remains the current per-company projection. This module owns the separate
application-level history in `data/applications.yml`, because one company can be applied to more than
once and a historical outcome must never be overwritten by the next application.

The learning engine does not infer why a rejection happened. It reports three independent evidence
classes:

- repeated direct employer/recruiter feedback;
- recurring pre-application diagnostic gaps captured from matching;
- repeated candidate self-observations.

LLM theme proposals may be stored, but only the latest user decision for a theme participates in a
pattern. Nothing here promotes a pattern into `rules.yml` automatically.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import pipeline_store

SCHEMA_VERSION = "1.0"
MODEL_VERSION = "learning_loop_v1"
DIRECT_FEEDBACK_KINDS = {"employer_feedback", "recruiter_feedback"}
OBSERVATION_KINDS = DIRECT_FEEDBACK_KINDS | {"candidate_observation"}
CLASSIFICATION_STATES = {"proposed", "confirmed", "rejected"}
CLASSIFICATION_SOURCES = {"llm", "user"}
CHANNELS = {"site", "agent", "scout", "referral", "direct", "unknown"}
REPEATED_DIRECT_EMPLOYERS = 2
RECURRING_GAP_APPLICATIONS = 2
REPEATED_SELF_APPLICATIONS = 2
STAGE_OBSERVATION_FLOOR = 3

# Fields that describe one current application in the company-level projection. Starting a new
# application removes them so an old JD, gap, deadline, or rejection never leaks into the new one.
# Company-level interest is intentionally retained: it is the user's view of the company, not an
# outcome snapshot.
APPLICATION_SCOPED_PIPELINE_FIELDS = {
    "stage",
    "status",
    "channel",
    "kyujin_legitimacy",
    "match_model_version",
    "decision_status",
    "match_conflicts",
    "match_required_gaps",
    "match_unknowns",
    "primary_project_ids",
    "primary_experience_ids",
    "supporting_experience_ids",
    "unknown_requirements",
    "jd_source",
    "jd_observed_at",
    "jd_digest",
    "jd_requirements",
    "employer_signals",
    "next_action",
    "deadline",
    "closed_reason",
    "agent_feedback",
    "reached_stage",
    "feedback_obtained",
    "root_cause",
    "demo_slot",
    "prep_lines",
    "gate_override",
    "action_items",
}


def applications_path(workspace: str | Path | None = None) -> Path:
    return pipeline_store.resolve_workspace(workspace) / "data" / "applications.yml"


def pipeline_path(workspace: str | Path | None = None) -> Path:
    return pipeline_store.resolve_pipeline_path(workspace)


def _new_store() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "applications": []}


def load_store(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _new_store()
    import yaml

    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    validate_store(value)
    return value


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _date(value: Any, field: str) -> str:
    text = _nonempty(value, field)
    try:
        dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc
    return text


def _instant(value: Any, field: str) -> str:
    text = _nonempty(value, field)
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt.datetime.fromisoformat(candidate)
    except ValueError:
        try:
            dt.date.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO date or datetime") from exc
    return text


def _stage(value: Any, field: str, *, nullable: bool = False) -> int | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 7:
        raise ValueError(f"{field} must be an integer from 0 to 7")
    return value


def _string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(one, str) and one.strip() for one in value):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return [one.strip() for one in value]


def _validate_observation(value: Any, app_id: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{app_id}.observations items must be objects")
    _nonempty(value.get("id"), "observation.id")
    kind = _nonempty(value.get("kind"), "observation.kind")
    if kind not in OBSERVATION_KINDS:
        raise ValueError(f"observation.kind must be one of {sorted(OBSERVATION_KINDS)}")
    _nonempty(value.get("text"), "observation.text")
    _instant(value.get("observed_at"), "observation.observed_at")
    _nonempty(value.get("source_ref"), "observation.source_ref")
    _stage(value.get("stage"), "observation.stage", nullable=True)


def _validate_classification(value: Any, app_id: str, observation_ids: set[str]) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{app_id}.classifications items must be objects")
    _nonempty(value.get("id"), "classification.id")
    observation_id = _nonempty(value.get("observation_id"), "classification.observation_id")
    if observation_id not in observation_ids:
        raise ValueError(f"classification references unknown observation {observation_id!r}")
    _nonempty(value.get("theme"), "classification.theme")
    state = _nonempty(value.get("state"), "classification.state")
    if state not in CLASSIFICATION_STATES:
        raise ValueError(f"classification.state must be one of {sorted(CLASSIFICATION_STATES)}")
    source = _nonempty(value.get("source"), "classification.source")
    if source not in CLASSIFICATION_SOURCES:
        raise ValueError(f"classification.source must be one of {sorted(CLASSIFICATION_SOURCES)}")
    if state in {"confirmed", "rejected"} and source != "user":
        raise ValueError("only the user may confirm or reject a learning theme")
    _instant(value.get("classified_at"), "classification.classified_at")


def _validate_match_snapshot(value: Any, app_id: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"{app_id}.match_snapshot must be an object or null")
    for field in ("required_gaps", "unknowns", "conflicts"):
        _string_list(value.get(field), f"match_snapshot.{field}")
    digest = value.get("jd_digest")
    if digest is not None:
        _nonempty(digest, "match_snapshot.jd_digest")
    requirements = value.get("jd_requirements")
    if requirements is not None and not isinstance(requirements, list):
        raise ValueError("match_snapshot.jd_requirements must be a list or null")


def _validate_application(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("applications items must be objects")
    app_id = _nonempty(value.get("id"), "application.id")
    _nonempty(value.get("company_slug"), f"{app_id}.company_slug")
    _nonempty(value.get("company_name"), f"{app_id}.company_name")
    _nonempty(value.get("position_title"), f"{app_id}.position_title")
    role_family = value.get("role_family")
    if role_family is not None:
        _nonempty(role_family, f"{app_id}.role_family")
    channel = _nonempty(value.get("channel"), f"{app_id}.channel")
    if channel not in CHANNELS:
        raise ValueError(f"{app_id}.channel must be one of {sorted(CHANNELS)}")
    _date(value.get("opened_at"), f"{app_id}.opened_at")
    _stage(value.get("start_stage"), f"{app_id}.start_stage")

    closed_at = value.get("closed_at")
    reached_stage = value.get("reached_stage")
    closed_reason = value.get("closed_reason")
    if closed_at is None:
        if reached_stage is not None or closed_reason is not None or value.get("match_snapshot") is not None:
            raise ValueError(f"open application {app_id} cannot contain outcome fields")
    else:
        _date(closed_at, f"{app_id}.closed_at")
        _stage(reached_stage, f"{app_id}.reached_stage")
        _nonempty(closed_reason, f"{app_id}.closed_reason")
        _validate_match_snapshot(value.get("match_snapshot"), app_id)

    observations = value.get("observations")
    classifications = value.get("classifications")
    if not isinstance(observations, list) or not isinstance(classifications, list):
        raise ValueError(f"{app_id}.observations and classifications must be lists")
    observation_ids: set[str] = set()
    for observation in observations:
        _validate_observation(observation, app_id)
        observation_id = observation["id"]
        if observation_id in observation_ids:
            raise ValueError(f"duplicate observation id {observation_id!r} in {app_id}")
        observation_ids.add(observation_id)
    classification_ids: set[str] = set()
    for classification in classifications:
        _validate_classification(classification, app_id, observation_ids)
        classification_id = classification["id"]
        if classification_id in classification_ids:
            raise ValueError(f"duplicate classification id {classification_id!r} in {app_id}")
        classification_ids.add(classification_id)


def validate_store(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("applications store must be an object")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"applications schema_version must be {SCHEMA_VERSION}")
    applications = value.get("applications")
    if not isinstance(applications, list):
        raise ValueError("applications must be a list")
    ids: set[str] = set()
    for application in applications:
        _validate_application(application)
        app_id = application["id"]
        if app_id in ids:
            raise ValueError(f"duplicate application id {app_id!r}")
        ids.add(app_id)


def _mutate_store(path: Path, fn: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    with pipeline_store.locked(path):
        data = fn(load_store(path))
        validate_store(data)
        pipeline_store.atomic_write(path, data)
        return data


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^\w]+", "-", value.strip().casefold(), flags=re.UNICODE).strip("-")
    return cleaned or "application"


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _application_id(company_slug: str, position_title: str, opened_at: str) -> str:
    return f"app-{_slug(company_slug)}-{opened_at.replace('-', '')}-{_stable_id('x', company_slug, position_title, opened_at)[2:10]}"


def _find_application(data: dict[str, Any], application_id: str) -> dict[str, Any]:
    for application in data["applications"]:
        if application.get("id") == application_id:
            return application
    raise ValueError(f"unknown application {application_id!r}")


def _current_company_entry(pipeline: dict[str, Any], company_slug: str) -> dict[str, Any] | None:
    companies = pipeline.get("companies") if isinstance(pipeline, dict) else None
    if not isinstance(companies, list):
        return None
    return next(
        (one for one in companies if isinstance(one, dict) and one.get("slug") == company_slug),
        None,
    )


def _project_begin(
    path: Path,
    *,
    company_slug: str,
    company_name: str,
    stage: int,
    channel: str,
    opened_at: str,
) -> None:
    """Reset only application-scoped projection state; application history lives elsewhere."""

    def apply(data: dict[str, Any]) -> dict[str, Any]:
        companies = data.setdefault("companies", [])
        if not isinstance(companies, list):
            raise ValueError("pipeline companies must be a list")
        entry = next(
            (one for one in companies if isinstance(one, dict) and one.get("slug") == company_slug),
            None,
        )
        if entry is None:
            entry = {"slug": company_slug, "name": company_name, "history": []}
            companies.append(entry)
        for field in APPLICATION_SCOPED_PIPELINE_FIELDS:
            entry.pop(field, None)
        entry.update({
            "name": company_name,
            "stage": stage,
            "channel": channel,
            "closed": False,
        })
        data["updated"] = opened_at
        return data

    pipeline_store.mutate(path, apply)


def _project_close(
    path: Path,
    *,
    company_slug: str,
    reached_stage: int,
    closed_reason: str,
    closed_at: str,
) -> None:
    def apply(data: dict[str, Any]) -> dict[str, Any]:
        entry = _current_company_entry(data, company_slug)
        if entry is None:
            raise ValueError(f"no pipeline company {company_slug!r}")
        entry["closed"] = True
        entry["reached_stage"] = reached_stage
        entry["closed_reason"] = closed_reason
        if not isinstance(entry.get("stage"), int) or entry["stage"] < reached_stage:
            entry["stage"] = reached_stage
        data["updated"] = closed_at
        return data

    pipeline_store.mutate(path, apply)


def _projection_needs_begin(
    path: Path,
    *,
    company_slug: str,
    start_stage: int,
    channel: str,
) -> bool:
    """Detect an interrupted/missing begin projection without wiping legitimate later progress."""
    entry = _current_company_entry(pipeline_store.load(path), company_slug)
    if entry is None or entry.get("closed") is True:
        return True
    current_stage = entry.get("stage")
    if not isinstance(current_stage, int) or current_stage < start_stage:
        return True
    return entry.get("channel") != channel


def begin_application(
    *,
    workspace: str | Path | None,
    company_slug: str,
    company_name: str,
    position_title: str,
    role_family: str | None,
    channel: str,
    opened_at: str,
    stage: int,
    application_id: str | None = None,
) -> dict[str, Any]:
    company_slug = _nonempty(company_slug, "company_slug")
    company_name = _nonempty(company_name, "company_name")
    position_title = _nonempty(position_title, "position_title")
    if role_family is not None:
        role_family = _nonempty(role_family, "role_family")
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {sorted(CHANNELS)}")
    opened_at = _date(opened_at, "opened_at")
    stage = _stage(stage, "stage")  # type: ignore[assignment]
    application_id = application_id or _application_id(company_slug, position_title, opened_at)
    _nonempty(application_id, "application_id")
    path = applications_path(workspace)
    created = False

    identity = {
        "id": application_id,
        "company_slug": company_slug,
        "company_name": company_name,
        "position_title": position_title,
        "role_family": role_family,
        "channel": channel,
        "opened_at": opened_at,
        "start_stage": stage,
    }

    def apply(data: dict[str, Any]) -> dict[str, Any]:
        nonlocal created
        existing = next((one for one in data["applications"] if one.get("id") == application_id), None)
        if existing is not None:
            if any(existing.get(key) != value for key, value in identity.items()):
                raise ValueError(f"application id {application_id!r} already exists with different identity")
            if existing.get("closed_at") is not None:
                raise ValueError(f"application {application_id!r} is already closed")
            return data
        active_same_company = next(
            (
                one for one in data["applications"]
                if one.get("company_slug") == company_slug and one.get("closed_at") is None
            ),
            None,
        )
        if active_same_company is not None:
            raise ValueError(
                f"company {company_slug!r} already has open application {active_same_company['id']!r}"
            )
        data["applications"].append({
            **identity,
            "closed_at": None,
            "reached_stage": None,
            "closed_reason": None,
            "match_snapshot": None,
            "observations": [],
            "classifications": [],
        })
        created = True
        return data

    data = _mutate_store(path, apply)
    projection = pipeline_path(workspace)
    if created or _projection_needs_begin(
        projection,
        company_slug=company_slug,
        start_stage=stage,
        channel=channel,
    ):
        _project_begin(
            projection,
            company_slug=company_slug,
            company_name=company_name,
            stage=stage,
            channel=channel,
            opened_at=opened_at,
        )
    return _find_application(data, application_id)


def add_observation(
    *,
    workspace: str | Path | None,
    application_id: str,
    kind: str,
    text: str,
    observed_at: str,
    source_ref: str,
    stage: int | None = None,
    observation_id: str | None = None,
) -> dict[str, Any]:
    application_id = _nonempty(application_id, "application_id")
    if kind not in OBSERVATION_KINDS:
        raise ValueError(f"kind must be one of {sorted(OBSERVATION_KINDS)}")
    text = _nonempty(text, "text")
    observed_at = _instant(observed_at, "observed_at")
    source_ref = _nonempty(source_ref, "source_ref")
    stage = _stage(stage, "stage", nullable=True)
    observation_id = observation_id or _stable_id(
        "obs", application_id, kind, observed_at, source_ref, text
    )
    observation = {
        "id": observation_id,
        "kind": kind,
        "text": text,
        "observed_at": observed_at,
        "source_ref": source_ref,
        "stage": stage,
    }
    path = applications_path(workspace)

    def apply(data: dict[str, Any]) -> dict[str, Any]:
        application = _find_application(data, application_id)
        existing = next(
            (one for one in application["observations"] if one.get("id") == observation_id),
            None,
        )
        if existing is not None:
            if existing != observation:
                raise ValueError(f"observation id {observation_id!r} already exists with different data")
            return data
        application["observations"].append(observation)
        return data

    data = _mutate_store(path, apply)
    return next(
        one for one in _find_application(data, application_id)["observations"]
        if one["id"] == observation_id
    )


def classify_observation(
    *,
    workspace: str | Path | None,
    application_id: str,
    observation_id: str,
    theme: str,
    state: str,
    source: str,
    classified_at: str,
    classification_id: str | None = None,
) -> dict[str, Any]:
    application_id = _nonempty(application_id, "application_id")
    observation_id = _nonempty(observation_id, "observation_id")
    theme = _nonempty(theme, "theme")
    if state not in CLASSIFICATION_STATES:
        raise ValueError(f"state must be one of {sorted(CLASSIFICATION_STATES)}")
    if source not in CLASSIFICATION_SOURCES:
        raise ValueError(f"source must be one of {sorted(CLASSIFICATION_SOURCES)}")
    if state in {"confirmed", "rejected"} and source != "user":
        raise ValueError("only the user may confirm or reject a learning theme")
    classified_at = _instant(classified_at, "classified_at")
    classification_id = classification_id or _stable_id(
        "cls", application_id, observation_id, theme, state, source, classified_at
    )
    classification = {
        "id": classification_id,
        "observation_id": observation_id,
        "theme": theme,
        "state": state,
        "source": source,
        "classified_at": classified_at,
    }
    path = applications_path(workspace)

    def apply(data: dict[str, Any]) -> dict[str, Any]:
        application = _find_application(data, application_id)
        if not any(one.get("id") == observation_id for one in application["observations"]):
            raise ValueError(f"unknown observation {observation_id!r}")
        existing = next(
            (one for one in application["classifications"] if one.get("id") == classification_id),
            None,
        )
        if existing is not None:
            if existing != classification:
                raise ValueError(
                    f"classification id {classification_id!r} already exists with different data"
                )
            return data
        application["classifications"].append(classification)
        return data

    data = _mutate_store(path, apply)
    return next(
        one for one in _find_application(data, application_id)["classifications"]
        if one["id"] == classification_id
    )


def _match_snapshot(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    if not entry:
        return None
    snapshot = {
        "decision_status": entry.get("decision_status"),
        "match_model_version": entry.get("match_model_version"),
        "required_gaps": copy.deepcopy(entry.get("match_required_gaps") or []),
        "unknowns": copy.deepcopy(entry.get("match_unknowns") or []),
        "conflicts": copy.deepcopy(entry.get("match_conflicts") or []),
        "jd_digest": entry.get("jd_digest"),
        "jd_requirements": copy.deepcopy(entry.get("jd_requirements") or []),
    }
    if not any(
        snapshot.get(key)
        for key in (
            "decision_status", "match_model_version", "required_gaps", "unknowns", "conflicts",
            "jd_digest", "jd_requirements",
        )
    ):
        return None
    return snapshot


def close_application(
    *,
    workspace: str | Path | None,
    application_id: str,
    closed_reason: str,
    closed_at: str,
    reached_stage: int | None = None,
) -> dict[str, Any]:
    application_id = _nonempty(application_id, "application_id")
    closed_reason = _nonempty(closed_reason, "closed_reason")
    closed_at = _date(closed_at, "closed_at")

    store = load_store(applications_path(workspace))
    application = _find_application(store, application_id)
    company_slug = application["company_slug"]
    pipeline = pipeline_store.load(pipeline_path(workspace))
    pipeline_entry = _current_company_entry(pipeline, company_slug)
    pipeline_stage = pipeline_entry.get("stage") if pipeline_entry else None
    if reached_stage is None:
        reached_stage = _stage(pipeline_stage, "reached_stage")
    else:
        reached_stage = _stage(reached_stage, "reached_stage")
        if isinstance(pipeline_stage, int) and reached_stage < pipeline_stage:
            raise ValueError(
                f"reached_stage {reached_stage} cannot be below current pipeline stage {pipeline_stage}"
            )
    snapshot = _match_snapshot(pipeline_entry)
    path = applications_path(workspace)

    def apply(data: dict[str, Any]) -> dict[str, Any]:
        current = _find_application(data, application_id)
        expected = {
            "closed_at": closed_at,
            "reached_stage": reached_stage,
            "closed_reason": closed_reason,
            "match_snapshot": snapshot,
        }
        if current.get("closed_at") is not None:
            actual = {key: current.get(key) for key in expected}
            if actual != expected:
                raise ValueError(f"application {application_id!r} is already closed with different data")
            return data
        current.update(expected)
        return data

    data = _mutate_store(path, apply)
    _project_close(
        pipeline_path(workspace),
        company_slug=company_slug,
        reached_stage=reached_stage,
        closed_reason=closed_reason,
        closed_at=closed_at,
    )
    return _find_application(data, application_id)


def _theme_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _confirmed_themes(application: dict[str, Any]) -> dict[str, list[str]]:
    """Return effective user-confirmed themes; the latest user decision per theme wins."""
    decisions: dict[tuple[str, str], tuple[str, str]] = {}
    for classification in application.get("classifications") or []:
        if classification.get("source") != "user":
            continue
        state = classification.get("state")
        if state not in {"confirmed", "rejected"}:
            continue
        observation_id = str(classification.get("observation_id") or "")
        theme = str(classification.get("theme") or "").strip()
        if not observation_id or not theme:
            continue
        decisions[(observation_id, _theme_key(theme))] = (state, theme)

    themes: dict[str, list[str]] = defaultdict(list)
    for (observation_id, _), (state, theme) in decisions.items():
        if state == "confirmed":
            themes[observation_id].append(theme)
    return dict(themes)


def _scope(values: set[str]) -> str | list[str]:
    cleaned = sorted(value for value in values if value)
    if not cleaned:
        return "unknown"
    if len(cleaned) == 1:
        return cleaned[0]
    return cleaned


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    validate_store(data)
    closed = [one for one in data["applications"] if one.get("closed_at") is not None]
    direct: dict[str, dict[str, Any]] = {}
    self_observed: dict[str, dict[str, Any]] = {}
    gaps: dict[str, dict[str, Any]] = {}
    no_direct_feedback: list[str] = []
    unclassified_direct_feedback: list[str] = []
    stages: dict[int, int] = defaultdict(int)

    for application in closed:
        app_id = application["id"]
        company_slug = application["company_slug"]
        role_family = application.get("role_family") or "unknown"
        channel = application.get("channel") or "unknown"
        reached_stage = application.get("reached_stage")
        if isinstance(reached_stage, int):
            stages[reached_stage] += 1

        confirmed = _confirmed_themes(application)
        observations = application.get("observations") or []
        direct_observations = [
            one for one in observations if one.get("kind") in DIRECT_FEEDBACK_KINDS
        ]
        if not direct_observations:
            no_direct_feedback.append(app_id)
        elif not any(confirmed.get(str(one.get("id"))) for one in direct_observations):
            unclassified_direct_feedback.append(app_id)

        for observation in observations:
            observation_id = str(observation.get("id") or "")
            themes = confirmed.get(observation_id, [])
            for theme in themes:
                key = _theme_key(theme)
                target = direct if observation.get("kind") in DIRECT_FEEDBACK_KINDS else self_observed
                record = target.setdefault(
                    key,
                    {
                        "theme": theme,
                        "application_ids": set(),
                        "company_slugs": set(),
                        "role_families": set(),
                        "channels": set(),
                        "stages": set(),
                        "observation_ids": set(),
                    },
                )
                record["application_ids"].add(app_id)
                record["company_slugs"].add(company_slug)
                record["role_families"].add(role_family)
                record["channels"].add(channel)
                if isinstance(observation.get("stage"), int):
                    record["stages"].add(observation["stage"])
                elif isinstance(reached_stage, int):
                    record["stages"].add(reached_stage)
                record["observation_ids"].add(observation_id)

        snapshot = application.get("match_snapshot") or {}
        for gap in snapshot.get("required_gaps") or []:
            key = _theme_key(gap)
            record = gaps.setdefault(
                key,
                {
                    "gap": gap,
                    "application_ids": set(),
                    "company_slugs": set(),
                    "role_families": set(),
                    "channels": set(),
                },
            )
            record["application_ids"].add(app_id)
            record["company_slugs"].add(company_slug)
            record["role_families"].add(role_family)
            record["channels"].add(channel)

    direct_rows = []
    for key, record in direct.items():
        employers = sorted(record["company_slugs"])
        if len(employers) < REPEATED_DIRECT_EMPLOYERS:
            continue
        direct_rows.append({
            "theme": record["theme"],
            "distinct_employers": len(employers),
            "applications": sorted(record["application_ids"]),
            "companies": employers,
            "role_scope": _scope(record["role_families"]),
            "channel_scope": _scope(record["channels"]),
            "stages": sorted(record["stages"]),
            "observation_ids": sorted(record["observation_ids"]),
            "eligible_for_review": True,
            "meaning": "repeated direct feedback; not a permanent candidate trait",
        })
    direct_rows.sort(key=lambda row: (-row["distinct_employers"], row["theme"].casefold()))

    self_rows = []
    for record in self_observed.values():
        applications = sorted(record["application_ids"])
        if len(applications) < REPEATED_SELF_APPLICATIONS:
            continue
        self_rows.append({
            "theme": record["theme"],
            "applications": applications,
            "companies": sorted(record["company_slugs"]),
            "role_scope": _scope(record["role_families"]),
            "stages": sorted(record["stages"]),
            "eligible_for_review": True,
            "meaning": "repeated candidate self-observation; employer confirmation is separate",
        })
    self_rows.sort(key=lambda row: (-len(row["applications"]), row["theme"].casefold()))

    gap_rows = []
    for key, record in gaps.items():
        applications = sorted(record["application_ids"])
        if len(applications) < RECURRING_GAP_APPLICATIONS:
            continue
        direct_support = direct.get(key)
        supporting_apps = sorted(direct_support["application_ids"]) if direct_support else []
        gap_rows.append({
            "gap": record["gap"],
            "applications": applications,
            "companies": sorted(record["company_slugs"]),
            "role_scope": _scope(record["role_families"]),
            "channel_scope": _scope(record["channels"]),
            "direct_feedback_support_applications": supporting_apps,
            "eligible_for_review": True,
            "causal_conclusion": "unknown",
            "meaning": "recurring pre-application diagnostic gap; repetition does not prove rejection cause",
        })
    gap_rows.sort(key=lambda row: (-len(row["applications"]), row["gap"].casefold()))

    stage_rows = []
    if len(closed) >= STAGE_OBSERVATION_FLOOR:
        stage_rows = [
            {"reached_stage": stage, "applications": count}
            for stage, count in sorted(stages.items())
        ]

    return {
        "model_version": MODEL_VERSION,
        "applications_analyzed": len(closed),
        "open_applications_ignored": sum(1 for one in data["applications"] if one.get("closed_at") is None),
        "repeated_direct_feedback": direct_rows,
        "recurring_diagnostic_gaps": gap_rows,
        "repeated_self_observations": self_rows,
        "stage_observations": stage_rows,
        "unknowns": {
            "no_direct_feedback": sorted(no_direct_feedback),
            "direct_feedback_without_user_confirmed_theme": sorted(unclassified_direct_feedback),
        },
        "automatic_rule_promotion": False,
    }


def render_report(result: dict[str, Any]) -> str:
    lines = [
        f"Job Search Learning Loop — {result['applications_analyzed']} closed applications",
        "Evidence classes stay separate; no hiring probability or automatic root-cause inference.",
        "",
        "Repeated direct feedback",
    ]
    if result["repeated_direct_feedback"]:
        for row in result["repeated_direct_feedback"]:
            lines.append(
                f"- {row['theme']}: {row['distinct_employers']} distinct employers; "
                f"role_scope={row['role_scope']}; eligible for user review only"
            )
    else:
        lines.append("- none above the 2-distinct-employer evidence threshold")

    lines += ["", "Recurring pre-application diagnostic gaps"]
    if result["recurring_diagnostic_gaps"]:
        for row in result["recurring_diagnostic_gaps"]:
            lines.append(
                f"- {row['gap']}: {len(row['applications'])} applications; "
                f"direct-feedback support={len(row['direct_feedback_support_applications'])}; "
                "rejection cause=Unknown"
            )
    else:
        lines.append("- none repeated across 2+ applications")

    lines += ["", "Repeated candidate self-observations"]
    if result["repeated_self_observations"]:
        for row in result["repeated_self_observations"]:
            lines.append(
                f"- {row['theme']}: {len(row['applications'])} applications; "
                "employer confirmation remains separate"
            )
    else:
        lines.append("- none repeated across 2+ applications")

    lines += ["", "Observed reached stages"]
    if result["stage_observations"]:
        for row in result["stage_observations"]:
            lines.append(f"- stage {row['reached_stage']}: {row['applications']} applications")
    else:
        lines.append(f"- Insufficient Data: need {STAGE_OBSERVATION_FLOOR} closed applications")

    unknowns = result["unknowns"]
    lines += [
        "",
        "Unknown / unclassified",
        f"- no direct feedback: {len(unknowns['no_direct_feedback'])}",
        "- direct feedback without a user-confirmed theme: "
        f"{len(unknowns['direct_feedback_without_user_confirmed_theme'])}",
        "",
        "No pattern is promoted to rules.yml automatically.",
    ]
    return "\n".join(lines)
