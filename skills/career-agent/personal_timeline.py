"""Personal fact timeline and the current personal-profile projection.

Implements docs/PRIVATE_CAREER_DATA_PRD.md phases 3 and 4 (sections 8, 8.1, 9, 10, 11, 11.1, 12.1,
12.2, 12.3, 12.4).

**Facts live in the existing career event ledger.** Section 24 resolves this explicitly: rather than
adding a second canonical state store, an event may carry a `fact` object, and the ledger's already
declared but never written `superseded` status finally means something. The ledger already stores
`compensation`, `currency`, `company`, `evidence`, and `occurred_at`; a parallel fact ledger would
have duplicated those fields and then needed reconciling at every consumer.

Two rules govern everything here:

- **`as_of` is a required parameter and nothing in this module reads a clock.** The default is
  injected once, at the CLI boundary. Without this, AC-15 is untestable and the projection changes
  at midnight with no change to canonical history. The repository already made this call for
  evidence staleness in matching.
- **Intervals are derived from supersession links, never hand-authored** (section 8.1). The forward
  `supersedes` link is what the ledger stores; `effective_to`, currency, and the `superseded` status
  are computed. This is the same reason phase 2 stopped stamping supersession at import time: a
  derived value cannot go stale against the links it came from, and one append cannot half-apply.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from models import UNTRUSTED_DATA_MARKER, CareerError
from validation import iso_date, validate_event

# How many conflicting records a `conflict` field lists. Not the context cap -- that is
# `MAX_CONTEXT_FACTS`, further down, and the two answer different questions.
MAX_CANDIDATES = 5

UNKNOWN_NO_FACT = "no confirmed fact effective at as_of"
UNKNOWN_EXPIRED = "the only confirmed fact expired before as_of"
UNKNOWN_NOT_YET = "the only confirmed fact becomes effective after as_of"
UNKNOWN_NO_EFFECTIVE_DATE = "a confirmed fact exists but its effective_from is Unknown"
UNKNOWN_RECORDED = "the confirmed fact records the value as explicitly Unknown"


def _date(value: str | None, field: str) -> dt.date | None:
    text = iso_date(value, field)
    return dt.date.fromisoformat(text) if text else None


def facts_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract personal facts from the career event ledger.

    Only `confirmed` events carry facts into the timeline (section 12.1 rule 1). A `draft` event is
    a proposal the user has not accepted, and an explicitly `superseded` event was retired by hand.
    """
    facts: list[dict[str, Any]] = []
    for event in events:
        fact = event.get("fact")
        if not isinstance(fact, dict):
            continue
        # Revalidate on read, fail closed. The ledger is a plain file a user can hand-edit, and
        # `career_context` already re-validates what it reads for the same reason. Without this a
        # row that no writer would have accepted -- a confirmed fact with no evidence, say -- still
        # reaches the projection, and since this output crosses into agent context that is a trust
        # boundary, not an internal robustness detail.
        validate_event(event)
        event_id = str(event["id"])
        facts.append(
            {
                "fact_id": event_id,
                "category": fact.get("category"),
                "key": fact.get("key"),
                "value": fact.get("value"),
                # Falling back to `occurred_at` would silently turn "when we recorded it" into
                # "when it became true" -- exactly what section 7.1 forbids. Absent means Unknown.
                "effective_from": _date(fact.get("effective_from"), "fact.effective_from"),
                "expires_on": _date(fact.get("expires_on"), "fact.expires_on"),
                "supersedes": fact.get("supersedes") or None,
                "status": event.get("status"),
                "evidence": list(event.get("evidence") or []),
                "observed_at": event.get("occurred_at"),
            }
        )
    return facts


def _key_of(fact: dict[str, Any]) -> tuple[str, str]:
    return (str(fact["category"]), str(fact["key"]))


def _grouped(facts: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for fact in facts:
        groups.setdefault(_key_of(fact), []).append(fact)
    return groups


def _assert_acyclic(edges: dict[str, str]) -> None:
    """Reject a supersession cycle. The chain must be a DAG (PRD section 8.1).

    `A supersedes B` and `B supersedes A` passes every per-node check: each has one successor, one
    predecessor, and one key. It still derives `effective_to` values that precede their own
    `effective_from`, and the projection then reports an ordinary `Unknown` for what is actually
    corrupt history. Phase 3 is the canonical temporal layer, so it fails closed instead.

    Each fact has at most one outgoing `supersedes` edge, so a plain walk finds any cycle; no
    general graph algorithm is needed.
    """
    settled: set[str] = set()
    for start in sorted(edges):
        if start in settled:
            continue
        path: list[str] = []
        seen: set[str] = set()
        node: str | None = start
        while node is not None and node not in settled:
            if node in seen:
                cycle = path[path.index(node):]
                raise CareerError(
                    "supersession cycle: " + " -> ".join(sorted(cycle))
                    + "; a fact key's version chain must not loop"
                )
            seen.add(node)
            path.append(node)
            node = edges.get(node)
        settled.update(path)


def derive_intervals(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply section 8.1's single interval rule and mark the unresolvable case.

    When B supersedes A and `B.effective_from` is known, `A.effective_to` becomes the day before it.
    When `B.effective_from` is Unknown, `A.effective_to` stays open and both records are marked as
    conflicting from `A.effective_from` onward -- newest-wins is forbidden (section 19.1), because
    a record with no effective date has no defensible position in the chain.

    Superseding never deletes: A keeps its record, its evidence, and its own `effective_from`.
    """
    derived = [dict(fact) for fact in facts]
    # A fact id must identify exactly one record. `validate_event` only checks that each row has a
    # non-empty id, so a hand-edited ledger can repeat one; `supersedes` would then resolve to
    # whichever copy happened to come last, making the projection depend on ledger order.
    by_id: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for fact in derived:
        fact_id = str(fact["fact_id"])
        if fact_id in by_id:
            duplicates.add(fact_id)
        by_id[fact_id] = fact
    if duplicates:
        # Sorted so the message does not depend on ledger order either.
        raise CareerError(
            "duplicate fact ids: "
            + ", ".join(sorted(duplicates))
            + "; a fact id must identify exactly one record"
        )
    for fact in derived:
        fact.setdefault("effective_to", None)
        fact.setdefault("superseded_by", None)
        fact.setdefault("conflicts_from", None)

    # Sorted by id so the error raised for a broken chain does not depend on ledger order either.
    successors = sorted(
        (fact for fact in derived if fact.get("supersedes")), key=lambda fact: fact["fact_id"]
    )
    # Topology is settled before any date is read. A cycle contains a backwards edge by
    # construction, so deriving first would report the strictly-later violation and never name the
    # loop that caused it -- the less useful of two true statements.
    claimed: dict[str, list[str]] = {}
    edges: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for successor in successors:
        if successor["status"] != "confirmed":
            # An unapproved draft must not retire a confirmed fact. Letting it close the interval
            # would route a state change around the approval gate: proposing a correction would
            # blank the current value before the user ever accepted it.
            continue
        target = str(successor["supersedes"])
        predecessor = by_id.get(target)
        if predecessor is None:
            raise CareerError(f"{successor['fact_id']} supersedes an unknown fact: {target}")
        if predecessor is successor:
            raise CareerError(f"{successor['fact_id']} cannot supersede itself")
        if predecessor["status"] != "confirmed":
            # Only confirmed facts take part in supersession -- on BOTH ends of the link. Checking
            # the successor alone let an unapproved draft reach the projection through the back
            # door: a confirmed successor with an Unknown `effective_from` would mark itself
            # `conflicts_from` against a draft predecessor, and the field it belongs to would report
            # a conflict caused entirely by a record that is not supposed to be visible yet.
            raise CareerError(
                f"{successor['fact_id']} cannot supersede {target}: a superseded fact must be "
                f"confirmed, not {predecessor['status']}"
            )
        if _key_of(predecessor) != _key_of(successor):
            # A version chain is scoped to one logical fact key. Without this, a JLPT record could
            # close a compensation record's interval and silently blank the salary.
            raise CareerError(
                f"{successor['fact_id']} ({'/'.join(_key_of(successor))}) cannot supersede "
                f"{target} ({'/'.join(_key_of(predecessor))}): supersession stays within one "
                f"category and key"
            )
        claimed.setdefault(target, []).append(successor["fact_id"])
        edges.append((successor, predecessor))

    _assert_acyclic({fact["fact_id"]: str(fact["supersedes"]) for fact in successors
                     if fact["status"] == "confirmed"})

    for target, ids in sorted(claimed.items()):
        if len(ids) > 1:
            # A fork is not a value ambiguity, it is a broken chain: each successor would derive a
            # different `effective_to` for the same predecessor, so the last one processed would
            # win and the projection would depend on ledger order (AC-15). Rejected the same way
            # the other two topology errors above are, rather than being papered over as a
            # conflict, because the data itself has to be corrected.
            raise CareerError(
                f"{target} is superseded by more than one confirmed fact: {', '.join(sorted(ids))}; "
                f"a fact key has a single version chain"
            )

    for successor, predecessor in edges:
        predecessor["superseded_by"] = successor["fact_id"]
        if successor["effective_from"] is None:
            # Unresolvable ordering: report it, do not pick a winner.
            marker = predecessor["effective_from"]
            predecessor["conflicts_from"] = marker
            successor["conflicts_from"] = marker
            continue
        if (
            predecessor["effective_from"] is not None
            and successor["effective_from"] <= predecessor["effective_from"]
        ):
            # A successor must begin strictly after what it replaces. Otherwise the rule below
            # derives an `effective_to` at or before the predecessor's own `effective_from` -- an
            # interval that ends before it starts, which no reader can render. Backdating a
            # correction is a real need, but it is a different operation with a different meaning
            # (replace the interval, not close it), so it gets its own semantics rather than
            # arriving disguised as an ordinary supersession.
            raise CareerError(
                f"{successor['fact_id']} cannot supersede {predecessor['fact_id']}: a successor "
                f"must be effective after its predecessor "
                f"({successor['effective_from']} <= {predecessor['effective_from']})"
            )
        predecessor["effective_to"] = successor["effective_from"] - dt.timedelta(days=1)
    return derived


def _covers(fact: dict[str, Any], as_of: dt.date) -> bool:
    if fact["effective_from"] is None or fact["effective_from"] > as_of:
        return False
    if fact["effective_to"] is not None and fact["effective_to"] < as_of:
        return False
    # Section 10: an expired qualification stays in history but is never currently valid.
    return not (fact["expires_on"] is not None and fact["expires_on"] < as_of)


def _unknown_reason(facts: list[dict[str, Any]], as_of: dt.date) -> str:
    if any(fact["effective_from"] is None for fact in facts):
        return UNKNOWN_NO_EFFECTIVE_DATE
    if any(fact["expires_on"] is not None and fact["expires_on"] < as_of for fact in facts):
        return UNKNOWN_EXPIRED
    if all(fact["effective_from"] > as_of for fact in facts):
        return UNKNOWN_NOT_YET
    return UNKNOWN_NO_FACT


def _serialize(fact: dict[str, Any]) -> dict[str, Any]:
    return {
        "value": fact["value"],
        "effective_from": fact["effective_from"].isoformat() if fact["effective_from"] else None,
        "evidence": fact["evidence"],
    }


def _candidates(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order before capping. A cap applied to unordered input makes the *visible* subset depend on
    ledger order, so the conflict report would differ run to run even though the conflict does not.
    `fact_id` breaks ties because two candidates can share an effective date -- that is often the
    reason they conflict."""
    ordered = sorted(
        facts, key=lambda fact: (fact["effective_from"] or dt.date.min, fact["fact_id"])
    )
    return [_serialize(fact) for fact in ordered[:MAX_CANDIDATES]]


def _field(facts: list[dict[str, Any]], as_of: dt.date) -> dict[str, Any]:
    """One projected field in the section 11.1 shape: state first, value only when unambiguous."""
    confirmed = [fact for fact in facts if fact["status"] == "confirmed"]
    conflicting = [
        fact for fact in confirmed
        if fact["conflicts_from"] is not None and fact["conflicts_from"] <= as_of
    ]
    if conflicting:
        return {
            "state": "conflict",
            "value": None,
            "reason": "supersession without an effective date cannot be ordered",
            "candidates": _candidates(conflicting),
        }

    covering = [fact for fact in confirmed if _covers(fact, as_of)]
    if len({repr(fact["value"]) for fact in covering}) > 1:
        return {
            "state": "conflict",
            "value": None,
            "reason": "more than one confirmed value is effective at as_of",
            "candidates": _candidates(covering),
        }
    if covering:
        # Identical values recorded more than once are one value, not a conflict; evidence merges.
        newest = max(covering, key=lambda fact: fact["effective_from"])
        field = _serialize(newest)
        field["evidence"] = sorted({item for fact in covering for item in fact["evidence"]})
        if newest["value"] is None:
            # A confirmed fact whose value is an explicit null says "we asked and it is not known".
            # That is `unknown`, not `confirmed` with a null payload: section 11.1 gives `Unknown`
            # exactly one serialized shape, and a second spelling of it is one every consumer would
            # have to learn. A null value colliding with a real one is caught by the distinct-value
            # check above and reported as a conflict.
            return {
                "state": "unknown",
                "value": None,
                "reason": UNKNOWN_RECORDED,
                "evidence": field["evidence"],
                "history_available": True,
            }
        return {"state": "confirmed", **field}

    return {
        "state": "unknown",
        "value": None,
        "reason": _unknown_reason(confirmed, as_of) if confirmed else UNKNOWN_NO_FACT,
        # Section 12.3: say that history exists without leaking the stale value into `value`.
        "history_available": bool(facts),
    }


def project(events: list[dict[str, Any]], as_of: str) -> dict[str, Any]:
    """Build the current personal-profile projection for an explicit date (sections 11, 12.4)."""
    day = _date(as_of, "as_of")
    if day is None:
        raise CareerError("as_of is required; the projection never consults a wall clock")
    facts = derive_intervals(facts_from_events(events))
    projection: dict[str, Any] = {"as_of": day.isoformat()}
    for (category, key), group in sorted(_grouped(facts).items()):
        projection.setdefault(category, {})[key] = _field(group, day)
    return projection


DOCUMENT_KEY_FIELDS = ("type", "company", "purpose", "language")


def document_states(records: list[dict[str, Any]], as_of: str) -> list[dict[str, Any]]:
    """Derive current/superseded state for phase 2's document registry (sections 12.4, 24).

    Phase 2 deliberately stores every document as `observed` and leaves currency undecided, because
    deciding it at import means arrival order decides it. This is where that decision is made, from
    `effective_from` and an explicit `as_of` -- the same rule the fact timeline uses, so a document
    and a fact never disagree about what "current" means.

    A document with no `effective_from` is never current: section 19.3 says an unknown effective
    date must not be promoted, and here it has no defensible position in the chain either.
    """
    day = _date(as_of, "as_of")
    if day is None:
        raise CareerError("as_of is required; document currency never consults a wall clock")

    groups: dict[tuple, list[dict[str, Any]]] = {}
    for record in records:
        key = tuple(str(record.get("logical_key", {}).get(field) or "") for field in DOCUMENT_KEY_FIELDS)
        groups.setdefault(key, []).append(record)

    result: list[dict[str, Any]] = []
    for key in sorted(groups):
        group = groups[key]
        dated = sorted(
            (
                (_date(record.get("effective_from"), "effective_from"), record)
                for record in group
                if record.get("effective_from")
            ),
            key=lambda pair: (pair[0], pair[1]["document_id"]),
        )
        effective_at_or_before = [pair for pair in dated if pair[0] <= day]
        latest = effective_at_or_before[-1][0] if effective_at_or_before else None
        # Two documents sharing the newest effective date cannot be ordered, so neither is current.
        contested = latest is not None and sum(1 for date, _ in dated if date == latest) > 1

        for index, (date, record) in enumerate(dated):
            # The next STRICTLY LATER date, not simply the next row. Documents sharing an effective
            # date cannot be ordered against each other, so treating one as the other's successor
            # would derive an `effective_to` a day before its own `effective_from`.
            successor = next((later for later, _ in dated[index + 1:] if later > date), None)
            if date > day:
                status = "not_yet_effective"
            elif date != latest:
                status = "superseded"
            else:
                status = "conflict" if contested else "current"
            result.append(_document_state(record, date, successor, status))
        for record in sorted(
            (item for item in group if not item.get("effective_from")),
            key=lambda item: item["document_id"],
        ):
            result.append(_document_state(record, None, None, "unknown_effective_date"))
    return result


def _document_state(
    record: dict[str, Any], date: dt.date | None, successor: dt.date | None, status: str,
) -> dict[str, Any]:
    return {
        "document_id": record["document_id"],
        "document_type": record["document_type"],
        "logical_key": record["logical_key"],
        "effective_from": date.isoformat() if date else None,
        # Derived exactly as fact intervals are: the day before the next version begins.
        "effective_to": (successor - dt.timedelta(days=1)).isoformat() if successor else None,
        "status": status,
        "sha256": record["sha256"],
        "verified_by_user": record.get("verified_by_user", False),
    }


# Section 12.1 rule 4: relevance must be a mechanical match, because "relevant" as an undefined word
# is the one condition in that list a reader can quietly skip. It is deliberately *not* the recording
# event's track: a fact describes the person, not the search, so a JLPT result recorded during a
# shinsotsu search is still true during a chuto one, and filtering by the recording track would drop
# facts that are currently true -- the mirror image of the stale-context bug this whole feature
# exists to prevent. The question that is both mechanical and meaningful is which categories the
# stage actually needs. An empty set is a real answer, not a gap: company research and an aptitude
# test need nothing about the person, and sending it anyway spends privacy for nothing.
STAGE_CATEGORIES: dict[str, frozenset[str]] = {
    "自己分析・就活軸": frozenset({"education", "skill", "portfolio"}),
    "学チカ・自己PR素材": frozenset({"education", "skill", "portfolio"}),
    "業界研究・企業研究": frozenset(),
    "ES・履歴書": frozenset({"education", "certification", "language", "skill", "portfolio"}),
    "適性検査（SPI3）": frozenset(),
    "書類選考・面接": frozenset(
        {"education", "certification", "language", "skill", "portfolio", "role", "employment"}
    ),
    "内々定・内定・入社準備": frozenset({"compensation", "employment"}),
    "自己分析・転職軸": frozenset({"employment", "role", "skill"}),
    "職務経歴書・自己PR": frozenset(
        {"employment", "role", "skill", "portfolio", "certification", "language", "education"}
    ),
    "応募・書類選考": frozenset(
        {"employment", "role", "skill", "portfolio", "certification", "language", "education"}
    ),
    "面接": frozenset(
        {"employment", "role", "skill", "portfolio", "certification", "language", "education"}
    ),
    "内定・条件交渉": frozenset({"compensation", "employment"}),
    "退職・入社準備": frozenset({"employment", "compensation"}),
}

# Section 12.1: the personal path is capped exactly as the Vault path is. An uncapped "current facts
# only" selection is how a privacy boundary quietly becomes the whole profile.
MAX_CONTEXT_FACTS = 5


def select_personal_context(
    events: list[dict[str, Any]],
    stage: str | None,
    as_of: str,
) -> dict[str, Any]:
    """Section 12.1: current, stage-relevant, capped, trust-marked personal context.

    Only `confirmed` fields are carried (rule 1), so a conflict or an Unknown never travels as a
    value. They are *counted* rather than dropped in silence: a model told nothing about salary
    would conclude there is no salary, when the truth may be that two records disagree.

    **No documents.** Default context carries selected facts and nothing else. Document metadata --
    type, company, purpose, effective dates, digest -- is personal data that neither the stage
    relevance map nor the cap applies to, so including it would let a stage that needs nothing
    about the person still receive the shape of every document they own. `private-list` and
    `personal-context --historical` are the explicit paths.
    """
    if stage is not None and stage not in STAGE_CATEGORIES:
        # Fail closed here, not only at the CLI. A missing map entry would otherwise mean "no
        # category filter", so an unrecognized stage widens the selection to the whole profile --
        # and this function is a public boundary symbol, reachable without going through argparse.
        raise CareerError(f"personal context stage is not recognized: {stage!r}")
    projection = project(events, as_of)
    allowed = STAGE_CATEGORIES[stage] if stage else frozenset()
    facts: list[dict[str, Any]] = []
    withheld = {"conflict": 0, "unknown": 0}
    for category, keys in projection.items():
        if category == "as_of" or category not in allowed:
            continue
        for key, field in sorted(keys.items()):
            if field["state"] != "confirmed":
                withheld[field["state"]] = withheld.get(field["state"], 0) + 1
                continue
            facts.append({"category": category, "key": key, **field})

    # Ordered before capping, newest effective date first, ties broken by name. A cap over unordered
    # input makes the visible subset depend on ledger order even when the selection does not.
    facts.sort(key=lambda fact: (fact["category"], fact["key"]))
    facts.sort(key=lambda fact: fact["effective_from"] or "", reverse=True)
    return {
        "as_of": projection["as_of"],
        "selected_for": {"stage": stage},
        "facts": facts[:MAX_CONTEXT_FACTS],
        "withheld": withheld,
        "capped_at": MAX_CONTEXT_FACTS,
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "documents_included": False,
    }


def _matches(
    document: dict[str, Any],
    document_type: str | None,
    company: str | None,
    document_ids: tuple[str, ...],
) -> bool:
    key = document["logical_key"]
    if document_type is not None and key.get("type") != document_type:
        return False
    if company is not None and key.get("company") != company:
        return False
    return not document_ids or document["document_id"] in document_ids


def historical_comparison(
    records: list[dict[str, Any]],
    as_of: str,
    *,
    document_type: str | None = None,
    company: str | None = None,
    document_ids: tuple[str, ...] = (),
    all_documents: bool = False,
) -> dict[str, Any]:
    """Section 12.2 / AC-09: the opt-in mode, for the requested versions, every role labelled.

    Superseded documents are reachable *only* here, and each side says which it is. An unlabelled
    historical value is the failure this mode exists to avoid: it looks exactly like a current one.

    **A request must name what it is asking for.** "Compare my 2024 resume with my current resume"
    is a question about resumes; returning every certificate and every company's ES beside them
    discloses personal data nobody asked for. An unfiltered sweep is still available, but only
    through `all_documents`, so it is a decision rather than the default. `document_ids` narrows to
    exact versions when the two being compared are already known -- `private-list` produces them.

    Metadata only, in this mode too. Extracting document text is a v1 non-goal (section 4), so
    there is no body to select -- the user opens the file themselves from the private store.
    """
    if not all_documents and document_type is None and company is None and not document_ids:
        raise CareerError(
            "a historical comparison must name what it is asking for: pass a document type, a "
            "company, or document ids. Use all_documents to sweep the whole store deliberately."
        )
    documents = [
        document for document in document_states(records, as_of)
        if _matches(document, document_type, company, document_ids)
    ]
    return {
        "context_mode": "historical-comparison",
        "as_of": as_of,
        "requested": {
            "type": document_type,
            "company": company,
            "document_ids": list(document_ids),
            "all_documents": all_documents,
        },
        "current": [document for document in documents if document["status"] == "current"],
        "historical": [document for document in documents if document["status"] == "superseded"],
        # Everything else -- contested dates, not yet effective, no effective date at all. Dropping
        # these would make a document the user explicitly asked about vanish with no explanation,
        # which in an explicit historical query is worse than showing an awkward state.
        "unresolved": [
            document for document in documents
            if document["status"] not in ("current", "superseded")
        ],
        "note": "Historical values are not treated as current facts.",
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
        "document_bodies_included": False,
    }


# The minimal downstream read path (section 24, phase 4). Maps confirmed personal facts onto the
# CANDIDATE_PROFILE field names in _shared/schemas.yml so the job-seeker skill has something exact
# to quote. It returns values, never writes: `data/candidate_profile.yml` is written by a skill
# following Markdown instructions, with the user confirming, and that stays true.
#   field: (category, key, permitted values or None for any non-empty string)
# The domains are the ones _shared/schemas.yml states for CANDIDATE_PROFILE. A fact's `value` is
# otherwise unconstrained -- `validate_fact` checks that the key exists, not what belongs in it --
# and the job-seeker skill is told to quote these values exactly, so an unchecked `N9` would become
# a schema violation two skills downstream.
CANDIDATE_PROFILE_FIELDS: dict[str, tuple[str, str, frozenset[str] | None]] = {
    "jlpt_level": ("language", "jlpt", frozenset({"native", "N1", "N2", "N3", "N4", "None"})),
    "target_role": ("role", "target", None),
    "segment": (
        "employment", "segment",
        frozenset({"dai2_shinsotsu", "standard", "senior_ic", "management"}),
    ),
    "visa_status": (
        "employment", "visa_status", frozenset({"PR", "Engineer/Specialist", "Student"}),
    ),
}
INVALID_FOR_SCHEMA = "the confirmed value is not permitted by the CANDIDATE_PROFILE schema"


def _withheld_field(state: str, reason: str, entry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Report a field that must not be quoted -- without shipping the value anyway.

    `value: null` alone is not enough here. A conflict projection carries its `candidates`, each
    with the value that caused the conflict, so passing the entry through would hand the consumer
    exactly the personal values the state says it may not use. Default context already withholds
    the value and sends only a count (section 12.1); this boundary must not be the exception.
    """
    field = {"state": state, "value": None, "reason": reason}
    if entry is not None and entry.get("candidates"):
        field["candidate_count"] = len(entry["candidates"])
    if entry is not None and entry.get("history_available"):
        field["history_available"] = True
    return field


def _schema_checked(field: str, entry: dict[str, Any], domain: frozenset[str] | None) -> dict[str, Any]:
    """Refuse to hand a downstream schema a value it does not accept."""
    value = entry["value"]
    if domain is None:
        valid = isinstance(value, str) and bool(value.strip())
    else:
        valid = value in domain
    if valid:
        return entry
    # The offending value stays out of the message. Naming the field is enough to find the record;
    # echoing the value would smuggle the personal data back into the payload through the reason.
    return _withheld_field("invalid", f"{INVALID_FOR_SCHEMA}: {field}")


def candidate_profile_values(events: list[dict[str, Any]], as_of: str) -> dict[str, Any]:
    """Confirmed personal facts in CANDIDATE_PROFILE terms, with Unknown said out loud."""
    projection = project(events, as_of)
    values: dict[str, Any] = {}
    for field, (category, key, domain) in sorted(CANDIDATE_PROFILE_FIELDS.items()):
        entry = projection.get(category, {}).get(key)
        if entry is None:
            values[field] = _withheld_field("unknown", UNKNOWN_NO_FACT)
        elif entry["state"] != "confirmed":
            # A conflict or an Unknown is reported as such. Quoting either as a value is exactly the
            # silent-stale-fallback section 12.3 forbids, one layer further downstream -- and the
            # values behind it do not travel either.
            values[field] = _withheld_field(entry["state"], entry["reason"], entry)
        else:
            values[field] = _schema_checked(field, entry, domain)
    return {
        "as_of": projection["as_of"],
        "schema": "CANDIDATE_PROFILE",
        "fields": values,
        "written_by_this_tool": False,
        "data_trust": UNTRUSTED_DATA_MARKER,
        "instruction_authority": "none",
    }


def timeline(events: list[dict[str, Any]], category: str, key: str) -> list[dict[str, Any]]:
    """Full history for one logical fact key, oldest first. Superseded records stay visible."""
    facts = derive_intervals(facts_from_events(events))
    group = _grouped(facts).get((category, key), [])
    group.sort(
        key=lambda fact: (
            fact["effective_from"] is None, fact["effective_from"] or dt.date.min, fact["fact_id"],
        )
    )
    return [
        {
            "fact_id": fact["fact_id"],
            "value": fact["value"],
            "effective_from": fact["effective_from"].isoformat() if fact["effective_from"] else None,
            "effective_to": fact["effective_to"].isoformat() if fact["effective_to"] else None,
            "expires_on": fact["expires_on"].isoformat() if fact["expires_on"] else None,
            # Derived, not stored: the ledger holds the forward link and this reads it backwards.
            "status": "superseded" if fact["superseded_by"] else fact["status"],
            "superseded_by": fact["superseded_by"],
            "evidence": fact["evidence"],
        }
        for fact in group
    ]
