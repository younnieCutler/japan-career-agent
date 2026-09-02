"""Deterministic interaction policy for review and consequential human judgment.

The policy is application-owned and host-independent.  A browser, CLI caller, or LLM host may
request an operation, but it cannot choose the interaction level itself.  Unknown operations fail
closed so a new write path cannot silently bypass review by omitting a classification rule.
"""

from __future__ import annotations

from typing import Any

from models import CareerError


IMPACT_LEVELS = ("l0", "l1", "l2", "l3")

# Keep the public operation vocabulary small.  Product-specific callers map their semantic action to
# one of these operations instead of inventing a risk score.  The interaction is deterministic and
# never depends on model output.
_OPERATION_POLICIES: dict[str, dict[str, Any]] = {
    "read_only": {
        "impact": "l0",
        "interaction": "execute",
        "requires_human_judgment": False,
        "requires_approval": False,
        "reversible": True,
    },
    "recoverable_local_write": {
        "impact": "l1",
        "interaction": "execute_recoverable",
        "requires_human_judgment": False,
        "requires_approval": False,
        "reversible": True,
    },
    "canonical_career_change": {
        "impact": "l2",
        "interaction": "review_and_approve",
        "requires_human_judgment": False,
        "requires_approval": True,
        "reversible": False,
    },
    "consequential_decision": {
        "impact": "l3",
        "interaction": "human_first",
        "requires_human_judgment": True,
        "requires_approval": False,
        "reversible": True,
    },
}

# Judgment subjects are the domain vocabulary already persisted by judgments.py.  Every one maps
# to the same L3 interaction today; keeping the mapping explicit makes a future downgrade an
# intentional, testable product decision instead of a caller-controlled string.
_JUDGMENT_OPERATIONS = {
    "company_fit": "consequential_decision",
    "application": "consequential_decision",
    "career_direction": "consequential_decision",
    "role_fit": "consequential_decision",
    "offer": "consequential_decision",
    "strategy": "consequential_decision",
    "other": "consequential_decision",
}


def policy_for(operation: str) -> dict[str, Any]:
    """Return one immutable-by-convention policy projection for a semantic operation."""
    key = str(operation or "").strip()
    try:
        policy = _OPERATION_POLICIES[key]
    except KeyError as exc:
        raise CareerError(
            "review policy is not defined for this operation",
            code="REVIEW_POLICY_UNKNOWN",
            details={"operation": key or None},
        ) from exc
    return {"operation": key, **policy}


def judgment_policy(subject: str) -> dict[str, Any]:
    """Classify a persisted judgment subject without accepting an impact from the caller."""
    key = str(subject or "").strip()
    try:
        operation = _JUDGMENT_OPERATIONS[key]
    except KeyError as exc:
        raise CareerError(
            "judgment subject has no review policy",
            code="REVIEW_POLICY_UNKNOWN",
            details={"subject": key or None},
        ) from exc
    return {"subject": key, **policy_for(operation)}


def policy_catalog() -> dict[str, dict[str, Any]]:
    """Read-only policy catalog used by diagnostics/tests; callers cannot mutate the owner table."""
    return {name: policy_for(name) for name in _OPERATION_POLICIES}
