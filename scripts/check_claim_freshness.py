#!/usr/bin/env python3
"""Validate the dated external-claim registry without inventing market facts."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAIMS = ROOT / "_shared" / "career_claims.yml"
REQUIRED = {
    "id", "claim", "source_url", "publisher", "published_at", "observed_at",
    "claim_type", "confidence", "expires_on", "allowed_usage",
}
CLAIM_TYPES = {"official", "marketing_claim", "survey", "third_party"}
UNKNOWN_PUBLISHED_AT = {"unknown", "unavailable", "not_published"}


def load_claims(path: Path = CLAIMS) -> list[dict]:
    import yaml

    if not path.is_file():
        raise ValueError(f"claim registry not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        raise ValueError("career_claims.yml must contain a claims list")
    claims = []
    for index, claim in enumerate(data["claims"]):
        if not isinstance(claim, dict):
            raise ValueError(f"claims[{index}] must be an object")
        missing = sorted(REQUIRED - set(claim))
        if missing:
            raise ValueError(f"claims[{index}] missing fields: {', '.join(missing)}")
        if claim["claim_type"] not in CLAIM_TYPES:
            raise ValueError(f"claims[{index}].claim_type is invalid")
        for field in ("published_at", "observed_at", "expires_on"):
            if field == "published_at" and str(claim[field]).lower() in UNKNOWN_PUBLISHED_AT:
                continue
            try:
                dt.date.fromisoformat(str(claim[field]))
            except ValueError as exc:
                raise ValueError(f"claims[{index}].{field} must be YYYY-MM-DD") from exc
        claims.append(claim)
    return claims


def check(as_of: dt.date | None = None, path: Path = CLAIMS) -> list[str]:
    today = as_of or dt.date.today()
    warnings = []
    for claim in load_claims(path):
        expires = dt.date.fromisoformat(str(claim["expires_on"]))
        if expires < today:
            warnings.append(f"stale external claim: {claim['id']} expired {expires}")
    return warnings


def main() -> int:
    try:
        warnings = check()
    except (ValueError, ImportError) as exc:
        print(f"claim freshness error: {exc}", file=sys.stderr)
        return 2
    for warning in warnings:
        print(f"WARNING: {warning}")
    print(f"claim freshness: {len(warnings)} stale claim(s)")
    return 1 if warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
