"""Read-only SELF_ANALYSIS_PROFILE projection and user-owned handoff."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_SHARED_ROOT = Path(__file__).resolve().parents[2] / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))

import self_analysis_profile  # noqa: E402
from models import CareerError  # noqa: E402
from projection import workspace_path  # noqa: E402


PROFILE_RELATIVE_PATH = "data/self_analysis_profile.yml"
DISPLAY_FIELDS = (
    "interest_hypotheses",
    "behavior_tendencies",
    "evidence_episodes",
    "career_self_efficacy",
    "perceived_barriers",
    "perceived_supports",
    "environment_preferences",
    "value_candidates",
    "avoid_candidates",
)
_PRIVATE_KEYS = frozenset({"id", "episode_ref", "evidence_episode_refs"})


def profile_path(workspace: str | Path | None = None) -> Path:
    """Resolve the existing workspace profile without creating or selecting another store."""
    return workspace_path(workspace) / PROFILE_RELATIVE_PATH


def _public(value: Any) -> Any:
    """Remove internal episode references before a profile reaches the browser."""
    if isinstance(value, Mapping):
        return {
            str(key): _public(child)
            for key, child in value.items()
            if str(key) not in _PRIVATE_KEYS
        }
    if isinstance(value, list):
        return [_public(child) for child in value]
    if isinstance(value, tuple):
        return [_public(child) for child in value]
    return value


def _status(value: Any) -> str:
    if value is None:
        return "Unknown"
    if isinstance(value, list) and not value:
        return "Reviewed empty"
    if isinstance(value, Mapping) and value and all(_status(child) == "Unknown" for child in value.values()):
        return "Unknown"
    return "Reviewed"


def _field_status(profile: Mapping[str, Any] | None) -> list[dict[str, str]]:
    return [
        {
            "field": field,
            "status": _status(profile.get(field) if profile is not None else None),
        }
        for field in DISPLAY_FIELDS
    ]


def _handoff(*, available: bool) -> dict[str, Any]:
    if not available:
        return {
            "skill": "jiko-bunseki",
            "available": False,
            "approval_required": False,
            "canonical_write_performed": False,
            "instruction": "Run the user-led jiko-bunseki flow and review its profile before returning here.",
        }
    return {
        "skill": "career-agent",
        "available": True,
        "approval_required": True,
        "canonical_write_performed": False,
        "command": (
            'python skills/career-agent/career_agent.py propose-context '
            '--vault "$CAREER_VAULT" --source data/self_analysis_profile.yml'
        ),
        "instruction": (
            "Review the profile first. This command creates an approval-gated proposal; "
            "it does not write canonical context by itself."
        ),
    }


def _invalid_payload(base: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **base,
        "state": "invalid",
        "reason": "invalid canonical profile",
        "profile": None,
        "field_status": _field_status(None),
        "handoff": _handoff(available=False),
    }


def profile_payload(workspace: str | Path | None = None) -> dict[str, Any]:
    """Return a safe projection of the canonical v2 profile, never a write or a score."""
    path = profile_path(workspace)
    base = {
        "mode": "self-analysis",
        "source": PROFILE_RELATIVE_PATH,
        "read_only": True,
        "no_total_by_design": True,
    }
    if not path.is_file():
        return {
            **base,
            "state": "unknown",
            "profile": None,
            "field_status": _field_status(None),
            "handoff": _handoff(available=False),
        }
    try:
        import yaml
    except ImportError:
        return _invalid_payload(base)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return _invalid_payload(base)
    if not isinstance(raw, dict):
        return _invalid_payload(base)
    try:
        self_analysis_profile.validate_self_analysis_profile(raw)
    except self_analysis_profile.ProfileValidationError:
        return _invalid_payload(base)
    return {
        **base,
        "state": "available",
        "profile": _public(raw),
        "field_status": _field_status(raw),
        "handoff": _handoff(available=True),
    }


def workflow_profile(workspace: str | Path | None = None) -> dict[str, Any]:
    """Load the same reviewed profile for the shared workflow, without a second schema."""
    path = profile_path(workspace)
    if not path.is_file():
        raise CareerError("no reviewed self-analysis profile is available", code="PROFILE_NOT_FOUND")
    try:
        import yaml
    except ImportError as exc:
        raise CareerError("PyYAML is required to read self-analysis", code="READ_FAILED") from exc
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        self_analysis_profile.validate_self_analysis_profile(raw)
    except (OSError, UnicodeError, yaml.YAMLError, self_analysis_profile.ProfileValidationError) as exc:
        raise CareerError("the reviewed self-analysis profile is invalid", code="PROFILE_INVALID") from exc
    assert isinstance(raw, dict)
    return raw
