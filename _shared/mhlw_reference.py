#!/usr/bin/env python3
"""MHLW 標準職務・職位プロファイル reference data interface (versioned).

The MHLW ポータブルスキル見える化ツール compares a candidate's 29-point 持ち味 allocation
against 114 standard job/position profiles. This module is the ONLY door to that dataset.

The dataset itself is NOT bundled. Its redistributable form and licence were not
established (PRD §15 open issue), so this repo ships the interface and refuses to
substitute anything for the data:

  - no LLM-generated approximation of the 114 profiles
  - no partial dataset silently treated as the full one
  - no fallback ranking against "similar enough" invented profiles

When the file is absent, `load()` returns status ``unavailable`` and every caller
must surface that verbatim. `_shared/matching_v3.py` does.

To supply the dataset, write a YAML file to `_shared/mhlw_role_profiles.yml`
(or point $MHLW_ROLE_PROFILES at one):

    dataset_version: "2023-04"       # required
    source: "https://www.mhlw.go.jp/content/11800000/000935264.pdf"   # required
    licence: "…"                     # required — record the actual terms
    profiles:
      - id: "kikaku-tantousha"
        label: "企画・立案 / 担当者"
        allocation:                  # 9 integers >= 1, summing to exactly 29
          current_state_assessment: 5
          ...

Validation is strict on purpose: a profile whose allocation does not satisfy the
MHLW rules is a data error, not something to round off.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# `matching_v3` is a sibling; make it importable however this module was loaded.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_PATH = Path(__file__).resolve().parent / "mhlw_role_profiles.yml"
PATH_ENV = "MHLW_ROLE_PROFILES"

# The official tool ranks against 114 profiles. A file with a different count is usable
# but must not be presented as "rank N / 114" — `expected_count_mismatch` says so.
EXPECTED_PROFILE_COUNT = 114

UNAVAILABLE_REASON = (
    "MHLW 114-profile reference dataset is not present in this installation. "
    "Its redistributable form and licence are unconfirmed, and generating the profiles "
    "would fabricate the very reference the diagnosis is measured against. "
    "Per-JD composition distance is still available when a mapping is supplied; "
    "the 114-profile ranking is not."
)


def dataset_path() -> Path:
    override = os.environ.get(PATH_ENV)
    return Path(override).expanduser() if override else DEFAULT_PATH


def _validate_profiles(raw: Any) -> list[dict[str, Any]]:
    from matching_v3 import validate_allocation  # local import: avoids a cycle at import time

    if not isinstance(raw, list) or not raw:
        raise ValueError("mhlw reference data: `profiles` must be a non-empty list")
    seen: set[str] = set()
    profiles = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"mhlw reference data: profile #{index} is not a mapping")
        profile_id = item.get("id")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError(f"mhlw reference data: profile #{index} has no `id`")
        if profile_id in seen:
            raise ValueError(f"mhlw reference data: duplicate profile id {profile_id!r}")
        seen.add(profile_id)
        profiles.append(
            {
                "id": profile_id,
                "label": item.get("label") or profile_id,
                "allocation": validate_allocation(item.get("allocation"), label=f"profile {profile_id}"),
            }
        )
    return profiles


def load(path: Path | None = None) -> dict[str, Any]:
    """Return the reference dataset, or an explicit `unavailable` record.

    Never raises for a missing file — absence is a reportable state, not an error.
    A present-but-invalid file DOES raise: silently degrading corrupt reference data
    to "unavailable" would hide a fixable problem behind an expected one.
    """
    target = path or dataset_path()
    if not target.is_file():
        return {
            "status": "unavailable",
            "reason": UNAVAILABLE_REASON,
            "expected_path": str(target),
            "dataset_version": None,
            "source": None,
            "licence": None,
            "profiles": [],
            "profile_count": 0,
            "expected_count_mismatch": None,
        }

    import yaml

    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    for field in ("dataset_version", "source", "licence"):
        if not data.get(field):
            raise ValueError(
                f"mhlw reference data at {target}: `{field}` is required. "
                "Unversioned or unsourced reference data cannot back a reproducible result."
            )
    profiles = _validate_profiles(data.get("profiles"))
    return {
        "status": "available",
        "reason": None,
        "expected_path": str(target),
        "dataset_version": str(data["dataset_version"]),
        "source": str(data["source"]),
        "licence": str(data["licence"]),
        "profiles": profiles,
        "profile_count": len(profiles),
        "expected_count_mismatch": (
            None if len(profiles) == EXPECTED_PROFILE_COUNT
            else f"{len(profiles)} profiles loaded, official tool uses {EXPECTED_PROFILE_COUNT}"
        ),
    }
