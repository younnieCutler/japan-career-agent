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

What that buys, precisely: **no known protected-claim violation reaches a rendered document.** The
rules below are enumerated, so they catch the escalations, invented numbers, unsupported
technologies, misattributed team results and leaked internal names that are on their lists. They
do not prove the absence of every possible semantic drift in Japanese -- a synonym outside
`ESCALATION_TERMS` can still raise the strength of a claim slightly, and no list of substrings
will ever close that. Meaning-level drift is defended by the humanize contract in
`skills/humanize-japanese-career/SKILL.md` and by the user reading the result, which is why the
document is theirs to send and not the system's.

Neither function writes anything. Generating a document a hundred times leaves the ledger
byte-identical: a document is a projection of career facts, never a source of them.
"""

from __future__ import annotations

import re
from typing import Any

from models import EVIDENCE_EVENT_TYPES, CareerError
from projection import (
    contexts_from_events,
    evidence_payload,
    experience_key,
    experiences_from_events,
    projects_from_events,
)
from validation import NUMERIC_CLAIM

# The documents this projection can produce. Distinct from `private_store.DOCUMENT_TYPES`, which
# names the kinds of document a user can import: one is what the system writes, the other is what
# it reads, and they are not the same list.
GENERATED_DOCUMENT_TYPES = {"shokumukeirekisho"}

# Latin-script tokens are how technology names travel: AWS, Terraform, GitHub Actions, CI/CD. The
# gate requires every one appearing in a draft to appear in that slot's evidence, which is what
# stops a JD keyword from arriving as a fact. Japanese-only coinages are not covered and are not
# claimed to be; the escalation and metric rules below catch the strengthening those cause.
LATIN_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+.#/_-]{1,}")
# The same alphabet read as names rather than tokens, so "GitHub Actions" stays one thing in the
# skills list. The gate keeps using the token form: "DevOps" arriving alone must be caught even
# though "DevOps" never appeared as a whole name in the evidence.
LATIN_PHRASE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/_-]{1,}(?:[ ][A-Za-z][A-Za-z0-9+.#/_-]{1,})*")

# Words that attribute an outcome to a group. A team's result may be written in a summary -- it is
# part of the story -- but only while it still reads as the team's. Without one of these, the same
# sentence claims it as the person's own, which is the promotion this gate exists to refuse.
TEAM_ATTRIBUTION_TERMS = ("チーム", "部門", "全社", "共同", "組織全体", "팀", "team", "Team")

# Verbs that raise the strength of a claim. The rule is not that these are forbidden -- someone who
# did lead a design should say so -- but that they may only appear when the evidence already says
# it. Arriving from nowhere, they are the exact failure this gate exists for: 支援 becoming 主導.
#
# It is a list, with a list's limits. It holds the escalations that actually recur in 職務経歴書
# prose; a synonym outside it can still raise a claim's strength by a degree, and enumerating
# Japanese exhaustively is not a thing that finishes. Adding a term here is cheap and is the right
# response to finding one in review.
ESCALATION_TERMS = (
    "主導", "牽引", "統括", "立ち上げ", "責任者", "リード", "全体設計", "意思決定者",
    "総括", "陣頭指揮",
)

# The evidence fields a recruiter-facing sentence may be built from, and what each one claims.
# `team_result` is here so it can be written about; `claim_role` is what keeps it from being
# written about as the person's own doing.
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


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(item) for item in value if str(item).strip()]


def _may_leave_the_vault(payload: dict[str, Any]) -> bool:
    """Whether this evidence may appear in something sent to someone else.

    Absent confidentiality means nothing was flagged. A flag with `external_use` still `unknown`
    means the review has not happened, and "not decided yet" is not permission -- which is the
    entire reason the two are separate values.
    """
    confidentiality = payload.get("confidentiality") or {}
    if not confidentiality.get("contains_confidential"):
        return True
    return confidentiality.get("external_use") == "allowed"


def _protected_claims(event: dict[str, Any], context: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
    """Everything a sentence about this evidence is not allowed to strengthen.

    Passed to the writer as well as to the gate. A humanizer given only text has to guess which
    words carry the facts; given this, it does not have to.
    """
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
        # Literal strings, not parsed quantities. A rounded "약 30%" is a different string from
        # "28.4%", and that is the point: rounding is one of the things the gate refuses.
        "metric": metrics,
        "provenance": list(event.get("evidence") or []),
        "external_label": project.get("external_label") or context.get("external_label"),
        "confidentiality": (payload.get("confidentiality") or {}).get("external_use"),
        # Everything the sentence is allowed to draw on, as one string. The gate reads this rather
        # than re-deriving the union, so writer and checker cannot disagree about the boundary.
        "source_text": source_text,
    }


def _slot(prefix: str, key: str) -> str:
    return f"{prefix}:{key}"


def document_model(
    events: list[dict[str, Any]],
    company: dict[str, Any],
    *,
    document_type: str = "shokumukeirekisho",
    canonical_revision: str | None = None,
) -> dict[str, Any]:
    """Arrange confirmed evidence for one target, without writing a word of it.

    The JD decides what is selected, what leads and what is summarised. It decides nothing about
    what is true: every factual field here comes from the ledger, and running this against a
    different JD moves evidence around without changing any of it.
    """
    if document_type not in GENERATED_DOCUMENT_TYPES:
        raise CareerError(
            f"document_type must be one of: {', '.join(sorted(GENERATED_DOCUMENT_TYPES))}",
            code="UNSUPPORTED_DOCUMENT_TYPE",
        )
    contexts = contexts_from_events(events)
    projects = projects_from_events(events)
    grouped = {item["experience_id"]: item for item in experiences_from_events(events)["experiences"]}
    by_id = {
        event["id"]: event
        for event in events
        if event.get("type") in EVIDENCE_EVENT_TYPES and event.get("status") == "confirmed"
    }

    primary = [str(item) for item in company.get("primary_experience_ids") or []]
    supporting = [str(item) for item in company.get("supporting_experience_ids") or []]
    selected = primary + [item for item in supporting if item not in primary]
    excluded: list[dict[str, str]] = []
    entries: list[dict[str, Any]] = []
    for event_id in selected:
        event = by_id.get(event_id)
        if event is None:
            # Selected but not confirmed evidence. Reported rather than dropped: a JD mapping that
            # points at a draft is a mistake worth seeing, not an empty section to wonder about.
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
                # The recruiter-facing name, which is the external label whenever one exists. The
                # canonical title never has to be softened to make the document safe to send.
                "heading": project.get("external_label") or project.get("title")
                or experience.get("label") or str(event.get("title") or ""),
                "work_date": payload.get("work_date"),
                "fields": fields,
                # Named, not hidden. A blank section reads as "nothing happened"; this reads as
                # "not recorded", which is what it is and what can still be fixed.
                "unknown_fields": unknown_fields,
                "protected_claims": claims,
            }
        )

    used_contexts = {entry["context_id"] for entry in entries if entry["context_id"]}
    employment_history = [
        {
            "context_id": context_id,
            "label": contexts[context_id].get("external_label") or contexts[context_id].get("label"),
            "internal_label": contexts[context_id].get("label"),
            "kind": contexts[context_id].get("kind"),
            "period": contexts[context_id].get("period"),
            "entries": [entry["slot"] for entry in entries if entry["context_id"] == context_id],
        }
        for context_id in sorted(used_contexts)
        if context_id in contexts
    ]
    # A skill is a name plus the evidence that shows it being used. Without the second half it is
    # a keyword list, and a keyword list is the thing a JD would happily fill in for the user.
    skills: dict[str, list[str]] = {}
    for entry in entries:
        for name in entry["protected_claims"]["technology_names"]:
            # A capital, a digit or a punctuation mark is what separates a product name from an
            # ordinary loan word: "GitHub Actions", "AWS", "CI/CD", "Python3" keep one, "runbook"
            # does not. The gate still checks every latin token, capitalised or not; this filter
            # only decides what is worth proposing as a skill, and the writer confirms it.
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
        # Slots a writer fills. `summary` and `self_pr` draw on the whole selection, so their
        # protected claims are the union of every entry's -- they may say less than the evidence,
        # never more.
        "narrative_slots": [_slot("section", "summary"), _slot("section", "self_pr")],
        "skills": [
            {"label": label, "evidence_ids": ids} for label, ids in sorted(skills.items())
        ],
        "employment_history": employment_history,
        "entries": entries,
        "requirements": requirements,
        # Requirements nothing supports stay Unknown. Adjacent experience is never promoted to
        # fill one, which is what would turn a JD into a source of career facts.
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
    """What each writable slot is allowed to draw on.

    A narrative slot gets the union of every entry's claims, because a summary legitimately spans
    them. It gets no more than the union, because a summary is still only allowed to restate.

    A model arriving as a file may be hand-edited or written by an older version, so every claim is
    read with a default rather than indexed. The defaults are empty on purpose: a missing claim
    means nothing supports the wording, so an absent key makes the gate stricter. Failing open here
    would mean a truncated model silently waved a document through.
    """
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
    """Whether written Japanese says exactly what the evidence says, and no more.

    Run twice: once on the evidence-grounded draft, and once on the humanized version with the
    draft passed as `humanized`'s predecessor, so polishing is checked against the evidence *and*
    against what it replaced. A failure is a refusal, not a warning -- the caller does not render.

    Every rule is literal string work on purpose. A semantic judge would catch more subtle
    strengthening and would not be the same judge tomorrow; a check that varies between runs
    cannot be relied on as a gate. The trade is deliberate and it is a trade: passing means no
    *enumerated* violation is present, not that the Japanese is proven faithful. Read
    `protected_claim_violations` as what it is named -- a count of detected rule breaches, not a
    measurement of semantic distance.
    """
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
        # Named for what it counts: breaches of the enumerated protected-claim rules. It was
        # called `factual_drift`, which read as a measurement of how far the wording had moved
        # from the evidence -- and `factual_drift: 0` then said "no drift" when what the gate
        # actually established was "nothing on my lists". No detector score is read or reported.
        "protected_claim_violations": len(violations),
        "ok": not violations,
    }
