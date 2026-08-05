"""Personal fact timeline and the current personal-profile projection.

Implements docs/PRIVATE_CAREER_DATA_PRD.md phase 3 (sections 8, 8.1, 9, 10, 11, 11.1, 12.3, 12.4).

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

from models import CareerError
from validation import iso_date, validate_event

# Section 12.1: the personal path is capped the same way Vault context already is. An uncapped
# "current facts only" projection is how a privacy boundary quietly grows into the whole profile.
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
    by_id = {fact["fact_id"]: fact for fact in derived}
    for fact in derived:
        fact.setdefault("effective_to", None)
        fact.setdefault("superseded_by", None)
        fact.setdefault("conflicts_from", None)

    # Sorted by id so the error raised for a broken chain does not depend on ledger order either.
    successors = sorted(
        (fact for fact in derived if fact.get("supersedes")), key=lambda fact: fact["fact_id"]
    )
    claimed: dict[str, list[str]] = {}
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
        predecessor["superseded_by"] = successor["fact_id"]
        if successor["effective_from"] is not None:
            predecessor["effective_to"] = successor["effective_from"] - dt.timedelta(days=1)
        else:
            # Unresolvable ordering: report it, do not pick a winner.
            marker = predecessor["effective_from"]
            predecessor["conflicts_from"] = marker
            successor["conflicts_from"] = marker

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
