#!/usr/bin/env python3
"""Enforce deterministic Tier 0 and normal status-bar context budgets."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "_shared" / "context_budget.yml"


def metrics(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    return {"bytes": len(text.encode("utf-8")), "chars": len(text), "lines": len(text.splitlines())}


def fail(errors: list[str]) -> int:
    print("context budget errors:")
    print("\n".join(f"- {error}" for error in errors))
    return 1


def main() -> int:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    errors: list[str] = []
    if config.get("schema_version") != "1.0":
        errors.append("unsupported context budget schema_version")

    loaded = config.get("always_loaded") or {}
    current: dict[str, dict[str, int]] = {}
    for relative, limits in loaded.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing always-loaded file: {relative}")
            continue
        current[relative] = metrics(path)
        for configured_metric, limit in limits.items():
            metric = configured_metric.removeprefix("max_")
            if current[relative][metric] > limit:
                errors.append(f"{relative} {metric}={current[relative][metric]} exceeds {limit}")

    baseline = config.get("baseline") or {}
    tier0 = {
        "bytes": sum(item["bytes"] for item in current.values()),
        "chars": sum(item["chars"] for item in current.values()),
        "lines": sum(item["lines"] for item in current.values()),
    }
    for metric in tier0:
        if tier0[metric] > baseline.get(f"tier0_{metric}", tier0[metric]):
            errors.append(f"Tier 0 {metric}={tier0[metric]} exceeds v1.6.0 baseline")

    for marker in (config.get("tier0") or {}).get("required_markers", []):
        if not any(
            marker in (ROOT / relative).read_text(encoding="utf-8")
            for relative in current
        ):
            errors.append(f"Tier 0 marker missing: {marker}")

    sys.path.insert(0, str(ROOT / "scripts"))
    import status_bar  # noqa: E402

    status_config = config.get("status_bar") or {}
    if status_bar.ACTION_CONTEXT_LIMIT != status_config.get("action_preview_limit"):
        errors.append("status bar action preview limit differs from context budget")
    if status_bar.RULE_CONTEXT_LIMIT != status_config.get("rule_preview_limit"):
        errors.append("status bar rule preview limit differs from context budget")
    if not status_config.get("blockers_unbounded"):
        errors.append("status bar blockers must remain unbounded")
    normal = status_bar.build_status(
        {"companies": [{"slug": "budget-probe", "stage": 4, "closed": False}]},
        {},
        dt.date(2026, 8, 3),
    )
    if len(normal) > status_config.get("normal_max_chars", 0):
        errors.append(
            f"status bar normal chars={len(normal)} exceeds {status_config['normal_max_chars']}"
        )

    for relative in (config.get("lazy_context") or {}).get("required_paths", []):
        if not (ROOT / relative).is_file():
            errors.append(f"missing lazy context path: {relative}")

    if errors:
        return fail(errors)
    print(
        "context budget: clean "
        f"(Tier 0 {tier0['bytes']} bytes/{tier0['chars']} chars/{tier0['lines']} lines; "
        f"normal status {len(normal)} chars)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
