"""GUI adapter for durable artifact metadata and body registration."""

from __future__ import annotations

from artifact_store import (
    artifact_path,
    delete_artifact,
    get_artifact,
    list_artifacts,
    register_artifact,
    update_artifact,
)

__all__ = [
    "artifact_path",
    "delete_artifact",
    "get_artifact",
    "list_artifacts",
    "register_artifact",
    "update_artifact",
]
