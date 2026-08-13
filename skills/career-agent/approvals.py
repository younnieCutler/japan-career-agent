#!/usr/bin/env python3
"""Bind the runtime's writers to the lifecycle's approval transaction.

The approval rules themselves live in `lifecycle`; this module only injects the pipeline writer
and the state projector so the same approval can be replayed after an interruption. It is also
the module whose `pipeline_file` binding integration tests patch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from lifecycle import approve as _lifecycle_approve, read_approval_transaction, recover_pending
from models import job_search_of
from projection import apply_event_to_state, pipeline_file, upsert_pipeline_entry
from vault import CareerVault


def _pipeline_writer_for(home: CareerVault, workspace: str | Path | None = None):
    def pipeline_writer(event: dict[str, Any]) -> Path | None:
        transaction = read_approval_transaction(home)
        transaction_workspace = transaction.get("workspace") if transaction else None
        target_workspace = transaction_workspace or workspace
        return upsert_pipeline_entry(
            event,
            path=pipeline_file(target_workspace),
            workspace=target_workspace,
        )

    return pipeline_writer


def _state_projector_for(home: CareerVault):
    """Bind the user's declared job-search intent to the state projector.

    The profile is the only place that answer lives, and the projector must not go read it: that
    would make a pure (state, event) function depend on a file. Reading it once here keeps the
    single write path for `job_search` intact while still letting the projector refuse to promote
    anyone into `active_search` they never asked for.
    """
    job_search = job_search_of(home.load_profile())

    def state_projector(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        return apply_event_to_state(state, event, job_search=job_search)

    return state_projector


def approve(
    home: CareerVault,
    proposal_id: str,
    evidence: list[str] | None = None,
    deadline: str | None = None,
    company: str | None = None,
    compensation: float | None = None,
    currency: str | None = None,
    workspace: str | Path | None = None,
    next_action: str | None = None,
    *,
    precondition: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Compatibility facade injecting the runtime-owned projection callbacks."""
    return _lifecycle_approve(
        home,
        proposal_id,
        evidence=evidence,
        deadline=deadline,
        company=company,
        compensation=compensation,
        currency=currency,
        workspace=workspace,
        next_action=next_action,
        pipeline_writer=_pipeline_writer_for(home, workspace),
        state_projector=_state_projector_for(home),
        precondition=precondition,
    )


def recover_approval(home: CareerVault, workspace: str | Path | None = None) -> dict[str, Any] | None:
    """Replay an interrupted approval using the workspace recorded in its journal."""
    return recover_pending(
        home,
        pipeline_writer=_pipeline_writer_for(home, workspace),
        state_projector=_state_projector_for(home),
    )
