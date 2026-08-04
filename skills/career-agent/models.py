"""Stable model/constants surface for the Career Agent runtime split.

The first architecture PR keeps the on-disk and JSON contracts in ``runtime.py``. These explicit
surfaces let later changes extract one responsibility at a time without changing CLI imports.
"""

from runtime import (  # noqa: F401
    CAREER_CONTEXT_FIELDS,
    CAREER_STATUSES,
    CHUTO_STAGES,
    CONTEXT_KINDS,
    EVENT_STATUSES,
    PIPELINE_STAGE,
    REQUIRED_EVENT_FIELDS,
    SHINSOTSU_STAGES,
    TRACKS,
    CareerError,
)
