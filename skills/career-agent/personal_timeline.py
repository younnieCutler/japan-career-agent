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
from validation import iso_date

# Section 12.1: the personal path is capped the same way Vault context already is. An uncapped
# "current facts only" projection is how a privacy boundary quietly grows into the whole profile.
MAX_CANDIDATES = 5

UNKNOWN_NO_FACT = "no confirmed fact effective at as_of"
UNKNOWN_EXPIRED = "the only confirmed fact expired before as_of"
UNKNOWN_NOT_YET = "the only confirmed fact becomes effective after as_of"
UNKNOWN_NO_EFFECTIVE_DATE = "a confirmed fact exists but its effective_from is Unknown"


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
        event_id = str(event.get("id") or "")
        if not event_id:
            raise CareerError("an event carrying a fact must have an id")
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
