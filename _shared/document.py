"""JD-specific document projection, and the gate that stops wording from outrunning evidence.

Two things live here, and they are deliberately the same module because they share one vocabulary.

`document_model` selects and arranges confirmed evidence for one target. It writes no prose: what
it produces is the material a recruiter-facing sentence may be built from, slot by slot, with the
evidence ids behind each slot and the claims that sentence is not allowed to strengthen. The
Japanese is written by a skill, because that is a language task; the boundary of what the Japanese
may say is decided here, because that is not.

`fidelity_gate` compares a written draft against those claims. Every check is deterministic and
literal -- the same draft and the same model always produce the same violations -- because an
invariant checked by judgement is not an invariant.

Neither function writes anything. Generating a document a hundred times leaves the evidence source
byte-identical: a document is a projection of career facts, never a source of them.
"""

from __future__ import annotations

import re
from typing import Any


class CareerError(ValueError):
    """A user-correctable document contract or fidelity gate error."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        retryable: bool = True,
        details: dict[str, Any] | None = None,
        state_changed: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.details = details or {}
        self.state_changed = state_changed


NUMERIC_CLAIM = re.compile(
    r"(?<![A-Za-z])[+-]?\d+(?:[.,]\d+)?\s*(?:%|％|명|人|건|件|배|倍|만|万円|원|円)"
)

WORK_EVENT_TYPE = "work_event"
EXPERIENCE_EVENT_TYPE = "experience_event"
EVIDENCE_EVENT_TYPES = {WORK_EVENT_TYPE, EXPERIENCE_EVENT_TYPE}
PROJECT_EVENT_TYPE = "project"
EXPERIENCE_CONTEXT_EVENT_TYPE = "experience_context"
EXPERIENCE_SUPERSESSION_EVENT_TYPE = "experience_supersession"
USER_CONFIRMATION_EVIDENCE = "user_confirmation"

GENERATED_DOCUMENT_TYPES = {"shokumukeirekisho"}

LATIN_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+.#/_-]{1,}")
LATIN_PHRASE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/_-]{1,}(?:[ ][A-Za-z][A-Za-z0-9+.#/_-]{1,})*")

TEAM_ATTRIBUTION_TERMS = ("チーム", "部門", "全社", "共同", "組織全体", "팀", "team", "Team")

ESCALATION_TERMS = (
    "主導", "牽引", "統括", "立ち上げ", "責任者", "リード", "全体設計", "意思決定者",
    "総括", "陣頭指揮",
)

ENTRY_FIELDS = (
    ("role", "individual"),
    ("problem", "context"),
    ("direct_actions", "individual"),
    ("stakeholder_coordination", "individual"),
    ("individual_contribution", "individual"),
    ("improvements", "individual"),
    ("team_result", "team"),
    ("metrics", "metric"),
    ("learning", "individual"),
)

PROJECT_FIELDS = ("title", "external_label", "role", "scope", "summary", "status", "period")
EXPERIENCE_CONTEXT_FIELDS = ("kind", "label", "external_label", "role", "summary", "period")


def _apply_current_fields(current: dict[str, Any], payload: dict[str, Any], fields: tuple[str, ...]) -> None:
    """Project an update: omitted fields preserve, explicit null clears."""
    for field in fields:
        if field not in payload:
            continue
        value = payload[field]
        if field != "period":
            if value is None:
                current.pop(field, None)
            else:
                current[field] = value
            continue
        if value is None:
            current.pop("period", None)
        elif isinstance(value, dict):
            merged = dict(current.get("period") or {})
            for key, item in value.items():
                if item is None:
                    merged.pop(key, None)
                else:
                    merged[key] = item
            if merged:
                current["period"] = merged
            else:
                current.pop("period", None)


def normalize_evidence_records(source: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize either a list of event dicts or a structured `data/evidence.yml` mapping."""
    if isinstance(source, list):
        return [item for item in source if isinstance(item, dict)]
    if not isinstance(source, dict):
        return []
    if isinstance(source.get("events"), list):
        return [item for item in source["events"] if isinstance(item, dict)]
    events: list[dict[str, Any]] = []
    for ctx in source.get("contexts") or []:
        if not isinstance(ctx, dict) or not ctx.get("id"):
            continue
        ctx_id = str(ctx["id"])
        ctx_payload = {
            k: v for k, v in ctx.items() if k in {"id", *EXPERIENCE_CONTEXT_FIELDS}
        }
        if "label" not in ctx_payload and ctx.get("name"):
            ctx_payload["label"] = ctx["name"]
        events.append({
            "id": f"ctx-{ctx_id}",
            "type": EXPERIENCE_CONTEXT_EVENT_TYPE,
            "status": str(ctx.get("status", "confirmed")).lower(),
            "occurred_at": ctx.get("occurred_at", "2026-01-01T00:00:00Z"),
            "title": str(ctx_payload.get("label") or ctx_id),
            "summary": str(ctx.get("summary") or ctx_payload.get("label") or ctx_id),
            "evidence": list(ctx.get("evidence") or ["user"]),
            "experience_context": ctx_payload,
        })
    for prj in source.get("projects") or []:
        if not isinstance(prj, dict) or not prj.get("id"):
            continue
        prj_id = str(prj["id"])
        prj_payload = {
            k: v for k, v in prj.items() if k in {"id", *PROJECT_FIELDS}
        }
        if "title" not in prj_payload and prj.get("name"):
            prj_payload["title"] = prj["name"]
        events.append({
            "id": f"prj-{prj_id}",
            "type": PROJECT_EVENT_TYPE,
            "status": str(prj.get("status_record", "confirmed")).lower(),
            "occurred_at": prj.get("occurred_at", "2026-01-01T00:00:00Z"),
            "title": str(prj_payload.get("title") or prj_id),
            "summary": str(prj.get("summary") or prj_payload.get("title") or prj_id),
            "evidence": list(prj.get("evidence") or ["user"]),
            "project": prj_payload,
        })
    for item in source.get("evidence") or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        if item.get("type") in EVIDENCE_EVENT_TYPES and ("work_event" in item or "experience" in item):
            events.append(item)
            continue
        payload_keys = {
            "role", "scope", "responsibility", "problem", "judgment", "decision_basis",
            "risk_management", "direct_actions", "stakeholder_coordination",
            "organizational_context", "individual_contribution", "team_result",
            "outcome_state", "metrics", "improvements", "learning", "confidentiality",
            "primary_project_id", "related_project_ids", "work_date", "context_id",
            "experience_kind", "experience_ref",
        }
        payload = {k: item[k] for k in payload_keys if k in item}
        if "primary_project_id" not in payload and item.get("project_id"):
            payload["primary_project_id"] = item["project_id"]
        if "confidentiality" not in payload and item.get("external_use"):
            payload["confidentiality"] = {"external_use": item["external_use"]}
        events.append({
            "id": str(item["id"]),
            "type": item.get("type") if item.get("type") in EVIDENCE_EVENT_TYPES else WORK_EVENT_TYPE,
            "status": str(item.get("status", "confirmed")).lower(),
            "occurred_at": item.get("occurred_at", "2026-01-01T00:00:00Z"),
            "title": str(item.get("title") or item["id"]),
            "summary": str(item.get("summary") or item.get("title") or item["id"]),
            "evidence": list(item.get("evidence") or ["user"]),
            "work_event": payload,
        })
    return events


def projects_from_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
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
        _apply_current_fields(current, payload, PROJECT_FIELDS)
        current["updated_at"] = event.get("occurred_at")
    for record in projects.values():
        record.setdefault("status", "unknown")
    return projects


def contexts_from_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
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
        _apply_current_fields(current, payload, EXPERIENCE_CONTEXT_FIELDS)
        current["updated_at"] = event.get("occurred_at")
    return contexts


def evidence_payload(event: dict[str, Any]) -> dict[str, Any]:
    for key in ("work_event", "experience"):
        payload = event.get(key)
        if isinstance(payload, dict):
            return payload
    return {}


def evidence_supersessions(events: list[dict[str, Any]]) -> dict[str, str]:
    by_id = {str(event.get("id")): event for event in events if event.get("id")}
    links: dict[str, str] = {}
    for event in events:
        if event.get("type") != EXPERIENCE_SUPERSESSION_EVENT_TYPE or event.get("status") != "confirmed":
            continue
        link = event.get("supersession") or {}
        predecessor_id = str(link.get("predecessor_event_id") or "")
        replacement_id = str(link.get("replacement_event_id") or "")
        predecessor = by_id.get(predecessor_id)
        replacement = by_id.get(replacement_id)
        if predecessor is None or replacement is None:
            raise CareerError("experience supersession references an unknown event")
        if any(row.get("type") not in EVIDENCE_EVENT_TYPES or row.get("status") != "confirmed"
               for row in (predecessor, replacement)):
            raise CareerError("experience supersession requires confirmed evidence events")
        if predecessor.get("type") != replacement.get("type"):
            raise CareerError("experience supersession must preserve the evidence event type")
        if predecessor_id in links:
            raise CareerError("an experience event may be superseded only once")
        links[predecessor_id] = replacement_id
    return links


def confirmed_evidence_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    retired = set(evidence_supersessions(events))
    return [
        event for event in events
        if event.get("type") in EVIDENCE_EVENT_TYPES
        and event.get("status") == "confirmed"
        and event.get("id") not in retired
    ]


def experience_key(event: dict[str, Any]) -> str | None:
    payload = evidence_payload(event)
    project_id = payload.get("primary_project_id")
    if isinstance(project_id, str) and project_id.strip():
        return f"project:{project_id}"
    reference = payload.get("experience_ref")
    if isinstance(reference, str) and reference.strip():
        return f"ref:{reference}"
    return None


def experiences_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
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
        ]
        detail = {
            field: payload[field]
            for field in (
                "role", "scope", "responsibility", "problem", "judgment", "decision_basis",
                "risk_management", "direct_actions", "stakeholder_coordination",
                "organizational_context", "individual_contribution", "team_result",
                "outcome_state", "metrics", "improvements", "learning",
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


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(item) for item in value if str(item).strip()]


def _may_leave_the_vault(payload: dict[str, Any]) -> bool:
    confidentiality = payload.get("confidentiality") or {}
    if not confidentiality.get("contains_confidential"):
        return True
    return confidentiality.get("external_use") == "allowed"


def _protected_claims(event: dict[str, Any], context: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
    payload = evidence_payload(event)
    text_fields = [
        *_as_list(payload.get("role")),
        *_as_list(payload.get("problem")),
        *_as_list(payload.get("direct_actions")),
        *_as_list(payload.get("stakeholder_coordination")),
        *_as_list(payload.get("individual_contribution")),
        *_as_list(payload.get("improvements")),
        *_as_list(payload.get("learning")),
        str(event.get("summary") or ""),
        str(event.get("title") or ""),
    ]
    metrics = _as_list(payload.get("metrics"))
    source_text = " ".join([*text_fields, *metrics, *_as_list(payload.get("team_result"))])
    return {
        "employer": context.get("external_label") or context.get("label"),
        "period": context.get("period"),
        "role": payload.get("role"),
        "technology": sorted({token for token in LATIN_TOKEN.findall(source_text)}),
        "technology_names": sorted({name.strip() for name in LATIN_PHRASE.findall(source_text)}),
        "responsibility": payload.get("scope"),
        "action": _as_list(payload.get("direct_actions")),
        "decision": _as_list(payload.get("stakeholder_coordination")),
        "individual_contribution": payload.get("individual_contribution"),
        "team_result": payload.get("team_result"),
        "metric": metrics,
        "provenance": list(event.get("evidence") or []),
        "external_label": project.get("external_label") or context.get("external_label"),
        "confidentiality": (payload.get("confidentiality") or {}).get("external_use"),
        "source_text": source_text,
    }


def _employment_order(block: dict[str, Any]) -> tuple:
    period = block.get("period") or {}
    if isinstance(period, dict):
        start = str(period.get("from") or "")
    else:
        start = str(period).split("..", 1)[0].strip()
    return (0 if start else 1, _descending(start), str(block.get("label") or ""))


def _descending(value: str) -> str:
    return "".join(str(9 - int(char)) if char.isdigit() else char for char in value)


def _slot(prefix: str, key: str) -> str:
    return f"{prefix}:{key}"


def document_model(
    events: list[dict[str, Any]] | dict[str, Any],
    company: dict[str, Any],
    *,
    document_type: str = "shokumukeirekisho",
    canonical_revision: str | None = None,
) -> dict[str, Any]:
    """Arrange confirmed evidence for one target, without writing a word of it."""
    if document_type not in GENERATED_DOCUMENT_TYPES:
        raise CareerError(
            f"document_type must be one of: {', '.join(sorted(GENERATED_DOCUMENT_TYPES))}",
            code="UNSUPPORTED_DOCUMENT_TYPE",
        )
    normalized_events = normalize_evidence_records(events)
    contexts = contexts_from_events(normalized_events)
    projects = projects_from_events(normalized_events)
    grouped = {item["experience_id"]: item for item in experiences_from_events(normalized_events)["experiences"]}
    by_id = {
        event["id"]: event
        for event in confirmed_evidence_events(normalized_events)
    }

    primary = [str(item) for item in company.get("primary_experience_ids") or []]
    supporting = [str(item) for item in company.get("supporting_experience_ids") or []]
    selected = primary + [item for item in supporting if item not in primary]
    excluded: list[dict[str, str]] = []
    entries: list[dict[str, Any]] = []
    for event_id in selected:
        event = by_id.get(event_id)
        if event is None:
            excluded.append({"evidence_id": event_id, "reason": "not confirmed evidence"})
            continue
        payload = evidence_payload(event)
        if not _may_leave_the_vault(payload):
            excluded.append({"evidence_id": event_id, "reason": "confidentiality review not cleared"})
            continue
        key = experience_key(event) or ""
        experience = grouped.get(key, {})
        context = contexts.get(str(payload.get("context_id") or ""), {})
        project_id = str(payload.get("primary_project_id") or "")
        project = projects.get(project_id, {})
        claims = _protected_claims(event, context, project)
        fields = {}
        unknown_fields = []
        for name, claim_role in ENTRY_FIELDS:
            values = _as_list(payload.get(name))
            if values:
                fields[name] = {"values": values, "claim_role": claim_role}
            else:
                unknown_fields.append(name)
        entries.append(
            {
                "slot": _slot("entry", event_id),
                "evidence_id": event_id,
                "lead": event_id in primary,
                "context_id": payload.get("context_id"),
                "context_label": claims["employer"],
                "experience_id": key or None,
                "heading": project.get("external_label") or project.get("title")
                or experience.get("label") or str(event.get("title") or ""),
                "work_date": payload.get("work_date"),
                "fields": fields,
                "unknown_fields": unknown_fields,
                "protected_claims": claims,
            }
        )

    used_contexts = {entry["context_id"] for entry in entries if entry["context_id"]}
    employment_history = sorted(
        (
            {
                "context_id": context_id,
                "label": contexts[context_id].get("external_label") or contexts[context_id].get("label"),
                "internal_label": contexts[context_id].get("label"),
                "kind": contexts[context_id].get("kind"),
                "period": contexts[context_id].get("period"),
                "entries": [entry["slot"] for entry in entries if entry["context_id"] == context_id],
            }
            for context_id in used_contexts
            if context_id in contexts
        ),
        key=_employment_order,
    )
    skills: dict[str, list[str]] = {}
    for entry in entries:
        for name in entry["protected_claims"]["technology_names"]:
            if name.lower() == name and not any(char.isdigit() or char in "+.#/" for char in name):
                continue
            skills.setdefault(name, []).append(entry["evidence_id"])
    requirements = [dict(item) for item in company.get("jd_requirements") or []]
    unknowns = [str(item) for item in company.get("unknown_requirements") or []]
    unknowns += [
        str(item.get("text"))
        for item in requirements
        if item.get("status") in {"Missing", "Unknown"} and str(item.get("text") or "").strip()
    ]

    return {
        "mode": "document-model",
        "document_type": document_type,
        "target": {
            "company": company.get("name") or company.get("slug"),
            "slug": company.get("slug"),
            "role": company.get("target_role"),
            "jd_source": company.get("jd_source"),
            "jd_observed_at": company.get("jd_observed_at"),
            "jd_digest": company.get("jd_digest"),
        },
        "canonical_revision": canonical_revision,
        "narrative_slots": [_slot("section", "summary"), _slot("section", "self_pr")],
        "skills": [
            {"label": label, "evidence_ids": ids} for label, ids in sorted(skills.items())
        ],
        "employment_history": employment_history,
        "entries": entries,
        "requirements": requirements,
        "unknowns": sorted(set(unknowns)),
        "excluded": excluded,
        "internal_labels": sorted(
            {
                str(value)
                for context_id in used_contexts
                for value in (contexts.get(context_id, {}).get("label"),)
                if value and contexts.get(context_id, {}).get("external_label")
            }
            | {
                str(record["title"])
                for record in projects.values()
                if record.get("external_label") and record.get("title")
            }
        ),
        "no_total_by_design": True,
        "ok": True,
    }


def _slot_sources(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = model.get("entries") or []
    claims = [entry.get("protected_claims") or {} for entry in entries]
    sources = {entry["slot"]: entry for entry in entries if entry.get("slot")}
    union_text = " ".join(str(claim.get("source_text") or "") for claim in claims)
    union_metrics = [metric for claim in claims for metric in claim.get("metric") or []]
    union_tech = sorted({token for claim in claims for token in claim.get("technology") or []})
    union_team = [claim["team_result"] for claim in claims if claim.get("team_result")]
    for slot in model.get("narrative_slots", []):
        sources[slot] = {
            "slot": slot,
            "unknown_fields": [],
            "protected_claims": {
                "source_text": union_text,
                "metric": union_metrics,
                "technology": union_tech,
                "team_result": None,
                "individual_contribution": None,
            },
            "team_results": union_team,
            "narrative": True,
        }
    return sources


def _numbers(text: str) -> list[str]:
    return NUMERIC_CLAIM.findall(text)


def fidelity_gate(
    model: dict[str, Any], draft: dict[str, Any], *, humanized: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Whether written Japanese says exactly what the evidence says, and no more."""
    sources = _slot_sources(model)
    before = draft.get("slots") or {}
    after = (humanized or {}).get("slots") if humanized else None
    checked = after if after is not None else before
    violations: list[dict[str, str]] = []

    for slot, text in sorted(checked.items()):
        text = str(text or "")
        source = sources.get(slot)
        if source is None:
            violations.append({
                "slot": slot, "rule": "unknown_slot",
                "detail": "the model has no such slot; a document may only fill slots it defines",
            })
            continue
        claims = source.get("protected_claims") or {}
        haystack = str(claims.get("source_text") or "")
        if not text.strip():
            continue

        for number in _numbers(text):
            if not any(number in metric for metric in claims.get("metric") or []) and number not in haystack:
                violations.append({
                    "slot": slot, "rule": "unsupported_metric",
                    "detail": f"{number!r} appears in no confirmed metric for this slot",
                })

        for term in ESCALATION_TERMS:
            if term in text and term not in haystack:
                violations.append({
                    "slot": slot, "rule": "role_escalation",
                    "detail": f"{term!r} is stronger than the evidence, which does not say it",
                })

        for token in LATIN_TOKEN.findall(text):
            if token not in (claims.get("technology") or []):
                violations.append({
                    "slot": slot, "rule": "unsupported_technology",
                    "detail": f"{token!r} is not a technology this evidence records",
                })

        team_result = claims.get("team_result")
        if team_result and str(team_result) in text and not source.get("narrative"):
            fields = source.get("fields") or {}
            if "team_result" not in fields:
                violations.append({
                    "slot": slot, "rule": "team_result_as_individual",
                    "detail": "the team's outcome is written where the person's own doing belongs",
                })
        for team in source.get("team_results") or []:
            if str(team) in text and not any(term in text for term in TEAM_ATTRIBUTION_TERMS):
                violations.append({
                    "slot": slot, "rule": "team_result_as_individual",
                    "detail": "a team outcome is stated here as the person's own; say whose it was",
                })

        for label in model.get("internal_labels", []):
            if label in text:
                violations.append({
                    "slot": slot, "rule": "confidentiality_bypass",
                    "detail": f"{label!r} has an external label; the internal name may not be sent",
                })

    proposed = {item["label"] for item in model.get("skills", [])}
    selected = (humanized or draft).get("skills")
    if selected is not None:
        for label in selected:
            if label not in proposed:
                violations.append({
                    "slot": "skills", "rule": "unsupported_technology",
                    "detail": f"{label!r} is not a technology this evidence records",
                })

    for entry in model.get("entries", []):
        text = str(checked.get(entry["slot"]) or "")
        if not text.strip() or not entry.get("unknown_fields"):
            continue
        if not entry.get("fields"):
            violations.append({
                "slot": entry["slot"], "rule": "unknown_filled",
                "detail": "every field of this evidence is Unknown; there is nothing to state",
            })

    for excluded in model.get("excluded", []):
        slot = _slot("entry", excluded["evidence_id"])
        if str(checked.get(slot) or "").strip():
            violations.append({
                "slot": slot, "rule": "excluded_evidence_used",
                "detail": excluded["reason"],
            })

    if after is not None:
        if set(after) != set(before):
            violations.append({
                "slot": "*", "rule": "structure_changed",
                "detail": "polishing added or removed a slot; structure is preserved, not rewritten",
            })
        for slot in sorted(set(after) & set(before)):
            if str(after[slot]).count("\n") != str(before[slot]).count("\n"):
                violations.append({
                    "slot": slot, "rule": "structure_changed",
                    "detail": "the bullet structure of this slot changed during polishing",
                })

    violations.sort(key=lambda item: (item["slot"], item["rule"], item["detail"]))
    return {
        "mode": "document-check",
        "stage": "humanized" if after is not None else "draft",
        "pass": not violations,
        "checked_slots": len(checked),
        "violations": violations,
        "protected_claim_violations": len(violations),
        "ok": not violations,
    }
