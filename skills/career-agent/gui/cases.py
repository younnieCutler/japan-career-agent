"""GUI adapter for durable case metadata."""

from __future__ import annotations

from typing import Any

from artifact_store import list_artifacts
from case_store import (
    archive_case,
    case_path,
    create_application,
    create_company,
    delete_case,
    get_case,
    list_cases,
)

__all__ = [
    "archive_case",
    "case_path",
    "create_application",
    "create_company",
    "delete_case",
    "get_case",
    "list_cases",
    "payload",
]


def payload(home: Any) -> dict[str, Any]:
    case_rows = list_cases(home)
    return {
        "mode": "cases",
        "cases": case_rows,
        "artifacts": list_artifacts(home),
        "read_only": False,
        "pipeline_schema_unchanged": True,
        "canonical_write_performed": False,
    }
