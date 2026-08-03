#!/usr/bin/env python3
"""Report observed workflow patterns without turning them into hiring forecasts.

    python scripts/calibrate.py            # workflow observations
    python scripts/calibrate.py rules      # repeated feedback causes
    python scripts/calibrate.py rules --approve <root_cause> --text "..."

The default report deliberately excludes legacy numeric tiers. Historical legacy fields can be read
only through ``scripts/legacy_calibrate.py --legacy-experimental``; they are never mixed with v3
Decision Status or used as an outcome rate.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from status_bar import closed_companies  # noqa: E402

PIPELINE = Path("data/pipeline.yml")
RULES = Path("data/rules.yml")
MIN_SAMPLE = 3
PROMOTION_THRESHOLD = 2


def load(path: Path, required: bool = True) -> dict:
    import yaml

    if not path.is_file():
        if required:
            raise SystemExit(f"not found: {path.resolve()}\nRun this from the directory holding data/.")
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def scored_entries(pipeline: dict) -> list[dict]:
    """Return closed entries with an observed reached stage, not a forecast sample."""
    return [c for c in closed_companies(pipeline) if c.get("reached_stage") is not None]


def route_table(entries: list[dict]) -> list[str]:
    by_route: dict[str, list[dict]] = {}
    for entry in entries:
        by_route.setdefault(str(entry.get("channel") or "unknown"), []).append(entry)
    lines = ["", "Observed feedback by application route"]
    for route, group in sorted(by_route.items()):
        feedback = sum(1 for entry in group if entry.get("feedback_obtained"))
        lines.append(f"  {route}: {feedback}/{len(group)} entries supplied usable feedback")
    return lines


def override_table(entries: list[dict]) -> list[str]:
    overridden = [entry for entry in entries if entry.get("gate_override")]
    if not overridden:
        return ["", "User overrides: none recorded; no override observation to review yet."]
    reached_interview = sum(1 for entry in overridden if (entry.get("reached_stage") or 0) >= 4)
    return [
        "",
        f"User overrides: {len(overridden)} recorded; {reached_interview} reached interview stage 4+",
        "  This is an observation, not evidence that the gate was right or wrong.",
    ]


def prep_table(entries: list[dict]) -> list[str]:
    with_lines = [entry for entry in entries if isinstance(entry.get("prep_lines"), int)]
    if len(with_lines) < MIN_SAMPLE:
        return []
    lines = ["", "Recorded preparation volume by reached stage"]
    for entry in sorted(with_lines, key=lambda item: -item["prep_lines"]):
        lines.append(
            f"  {str(entry.get('name') or entry.get('slug'))[:24]:<25} "
            f"{entry['prep_lines']:>5} lines -> stage {entry.get('reached_stage')}"
        )
    return lines


def report(pipeline: dict) -> int:
    entries = scored_entries(pipeline)
    if len(entries) < MIN_SAMPLE:
        print(
            f"workflow observations: {len(entries)} closed entries with a reached stage; "
            f"need {MIN_SAMPLE} for the report.\n"
            "No comparison is printed. A small sample should remain descriptive rather than predictive."
        )
        return 0
    out = [f"workflow observations ({len(entries)} closed entries with reached stage)"]
    out += route_table(entries)
    out += override_table(entries)
    out += prep_table(entries)
    out += ["", f"n={len(entries)}. These are dated events and workflow observations, not rates or forecasts."]
    print("\n".join(out))
    return 0


def rule_candidates(pipeline: dict) -> tuple[Counter, dict[str, list[str]]]:
    counts: Counter = Counter()
    slugs: dict[str, list[str]] = {}
    for entry in closed_companies(pipeline):
        cause = entry.get("root_cause")
        if not cause:
            continue
        counts[cause] += 1
        slugs.setdefault(cause, []).append(str(entry.get("slug")))
    return counts, slugs


def rules_report(pipeline: dict, rules: dict) -> int:
    counts, slugs = rule_candidates(pipeline)
    if not counts:
        print("no root_cause recorded on any closed entry yet.")
        return 0
    existing = {rule.get("id") for rule in rules.get("rules") or []}
    ready, waiting = [], []
    for cause, count in counts.most_common():
        (ready if count >= PROMOTION_THRESHOLD else waiting).append((cause, count))
    out = ["Repeated observed feedback causes", ""]
    for cause, count in ready:
        mark = " (already a rule)" if cause in existing else ""
        out.append(f"  READY {cause} - {count} entries [{', '.join(slugs[cause])}]{mark}")
    for cause, count in waiting:
        out.append(
            f"  WAIT {cause} - {count} entries [{', '.join(slugs[cause])}] - "
            f"needs {PROMOTION_THRESHOLD - count} more before promotion"
        )
    if ready:
        out += ["", "Promote a user-written reminder only after reviewing the source entries:",
                f'  python scripts/calibrate.py rules --approve "{ready[0][0]}" --text "..."']
    out += ["", "A repeated cause is an observation about the route and role, not a stable candidate trait."]
    print("\n".join(out))
    return 0


def approve_rule(pipeline: dict, rules: dict, cause: str, text: str) -> int:
    counts, slugs = rule_candidates(pipeline)
    if counts[cause] < PROMOTION_THRESHOLD:
        raise SystemExit(
            f"{cause!r} has {counts[cause]} supporting entries; {PROMOTION_THRESHOLD} required.\n"
            "One company's feedback is that company's observation, not a candidate diagnosis."
        )
    entries = rules.setdefault("rules", [])
    if any(rule.get("id") == cause for rule in entries):
        raise SystemExit(f"a rule for {cause!r} already exists in {RULES}")
    import datetime as dt
    import yaml

    entries.append({
        "id": cause, "text": text, "status": "active", "source": "observed_workflow",
        "supported_by": slugs[cause], "created": dt.date.today().isoformat(),
    })
    RULES.parent.mkdir(parents=True, exist_ok=True)
    RULES.write_text(yaml.safe_dump(rules, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")
    print(f"rule added: {text}")
    print(RULES.resolve())
    return 0


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    pipeline = load(PIPELINE)
    if not argv:
        return report(pipeline)
    if argv[0] != "rules":
        raise SystemExit("usage: calibrate.py [rules [--approve <root_cause> --text <rule>]]")
    rules = load(RULES, required=False)
    if "--approve" in argv:
        try:
            cause = argv[argv.index("--approve") + 1]
            text = argv[argv.index("--text") + 1]
        except (ValueError, IndexError):
            raise SystemExit('usage: calibrate.py rules --approve <root_cause> --text "<rule>"')
        return approve_rule(pipeline, rules, cause, text)
    return rules_report(pipeline, rules)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
