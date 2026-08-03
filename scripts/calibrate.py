#!/usr/bin/env python3
"""Score past predictions against what actually happened, and propose rules.

    python3 scripts/calibrate.py            # predicted tier vs stage reached
    python3 scripts/calibrate.py rules      # which rejection causes recur
    python3 scripts/calibrate.py rules --approve <root_cause> --text "..."

The offline half of the loop. Skills record evidence while a search is running; this
reads the closed entries afterwards and reports what they show. It never edits a skill,
a score, or a threshold.

Two guards, both against reading a pattern into too little data:

  - below MIN_SAMPLE closed outcomes, no table is printed at all. A three-row table
    invites an explanation, and an explanation of noise is worse than silence.
  - a rejection cause becomes a rule only after two separate companies produce it.
    One company's rejection reason describes what that company measured, not the
    candidate. Optimising against a single measurement teaches the wrong axis.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from status_bar import STAGE_LABELS, closed_companies  # noqa: E402

PIPELINE = Path("data/pipeline.yml")
RULES = Path("data/rules.yml")

MIN_SAMPLE = 3
PROMOTION_THRESHOLD = 2

# Printed with every rules report. The one finding in the source records that the numbers
# alone cannot show: the recorded causes came only from companies that tested one axis, so
# the axis the candidate won on never appears in this table at all.
MEASUREMENT_CAVEAT = """
⚠️ This is a distribution of what the companies you applied to chose to measure —
   not a distribution of your ability. If a 選考 evaluated something you were good at,
   and you passed it, that axis produces no row here at all.
   Before acting: which axis have you actually won on, and how many of your recent
   applications even had a slot for it? (`demo_slot` in data/pipeline.yml)
"""


def load(path: Path, required: bool = True):
    import yaml

    if not path.is_file():
        if required:
            sys.exit(f"not found: {path.resolve()}\nRun this from the directory holding data/.")
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def scored_entries(pipeline: dict) -> list[dict]:
    return [c for c in closed_companies(pipeline) if c.get("reached_stage") is not None]


def tier_table(entries: list[dict]) -> list[str]:
    """Predicted tier against the stage actually reached — legacy_v1 entries ONLY.

    `predicted_tier` came from the legacy 0-100 match_score. evidence_based_v3 produces no
    tier and no probability, so there is deliberately nothing to calibrate on its side: it
    is a diagnostic of what is confirmed, missing, or in conflict, not a forecast. Scoring a
    Decision Status against a hiring outcome would turn it back into the pass-probability
    estimate v3 exists to stop, so this table simply skips those entries.
    """
    legacy = [e for e in entries if e.get("predicted_tier")]
    if not legacy:
        return [
            "",
            "予測 vs 実際 (legacy_v1): no entry carries a predicted_tier.",
            "  evidence_based_v3 records no predicted grade — by design, there is no forecast to score.",
        ]
    lines = [
        "",
        "予測 vs 実際 (legacy_v1 predicted_tier only — v3 entries excluded)",
        f"{'company':<20} {'predicted':<10} {'reached':<14} {'route':<8} {'feedback':<9} override",
        "-" * 74,
    ]
    entries = legacy
    for entry in sorted(entries, key=lambda e: str(e.get("predicted_tier") or "~")):
        reached = entry.get("reached_stage")
        label = f"{reached} {STAGE_LABELS.get(reached, '')}".strip()
        lines.append(
            f"{str(entry.get('name') or entry.get('slug'))[:19]:<20} "
            f"{str(entry.get('predicted_tier') or '-'):<10} "
            f"{label:<14} "
            f"{str(entry.get('channel') or '-'):<8} "
            f"{('yes' if entry.get('feedback_obtained') else 'no'):<9} "
            f"{'yes' if entry.get('gate_override') else ''}"
        )

    by_tier: dict[str, list[int]] = {}
    for entry in entries:
        by_tier.setdefault(str(entry.get("predicted_tier") or "-"), []).append(
            entry["reached_stage"]
        )
    lines += ["", "tier ごとの平均到達ステージ (legacy_v1)"]
    for tier, stages in sorted(by_tier.items()):
        avg = sum(stages) / len(stages)
        lines.append(f"  {tier}: {avg:.1f} (n={len(stages)})")
    lines.append(
        "  → A tier averaging no higher than C means the grade labels are not"
        " informative for you. Stop reading them as a ranking."
    )
    lines.append(
        "  ⚠️ legacy_v1: these grades came from an uncalibrated heuristic that was never an"
        " official Recruit/Persol model. They are scored here because they were recorded, not"
        " because they were valid."
    )
    return lines


def route_table(entries: list[dict]) -> list[str]:
    """Which application routes actually returned a usable rejection reason."""
    by_route: dict[str, list[dict]] = {}
    for entry in entries:
        by_route.setdefault(str(entry.get("channel") or "unknown"), []).append(entry)
    lines = ["", "経路ごとのフィードバック取得率"]
    for route, group in sorted(by_route.items()):
        got = sum(1 for e in group if e.get("feedback_obtained"))
        lines.append(f"  {route}: {got}/{len(group)}")
    lines.append("  → A route at 0/n teaches you nothing when it rejects you.")
    return lines


def override_table(entries: list[dict]) -> list[str]:
    """Was the gate right? Only overrides can answer that; blocked applications have no outcome."""
    overridden = [e for e in entries if e.get("gate_override")]
    if not overridden:
        return [
            "",
            "ゲート判定: no overrides recorded — nothing to score yet.",
            "  A gate that is never overridden can never be shown to be wrong.",
        ]
    reached_interview = sum(1 for e in overridden if (e.get("reached_stage") or 0) >= 4)
    return [
        "",
        f"ゲート判定: {len(overridden)} overrides, {reached_interview} reached 面接 (stage 4+)",
        "  → If most overrides reached interviews, the gate is costing you applications."
        " If none did, it was reading the situation correctly.",
    ]


def prep_table(entries: list[dict]) -> list[str]:
    """Prep volume against outcome. Recorded, never capped — the user draws the conclusion."""
    with_lines = [e for e in entries if isinstance(e.get("prep_lines"), int)]
    if len(with_lines) < MIN_SAMPLE:
        return []
    lines = ["", "準備量 vs 到達ステージ"]
    for entry in sorted(with_lines, key=lambda e: -e["prep_lines"]):
        lines.append(
            f"  {str(entry.get('name') or entry.get('slug'))[:24]:<25} "
            f"{entry['prep_lines']:>5} lines → stage {entry.get('reached_stage')}"
        )
    return lines


def report(pipeline: dict) -> int:
    entries = scored_entries(pipeline)
    if len(entries) < MIN_SAMPLE:
        print(
            f"標本不足: {len(entries)} scored outcome(s), need {MIN_SAMPLE}.\n"
            "No comparison is printed. A table this small would show a pattern whether or\n"
            "not one exists, and the point of this report is to avoid exactly that.\n\n"
            "Close entries with reached_stage / feedback_obtained / root_cause filled in\n"
            "(tenshoku-strategy STEP 6) and run this again."
        )
        return 0
    out = [f"キャリブレーション ({len(entries)} scored outcomes)"]
    out += tier_table(entries)
    out += route_table(entries)
    out += override_table(entries)
    out += prep_table(entries)
    out += [
        "",
        f"⚠️ n={len(entries)}. Direction only, not a rate. Timing, headcount left, and budget"
        " moved these outcomes too, and none of them are recorded here.",
    ]
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
    existing = {r.get("id") for r in rules.get("rules") or []}
    ready, waiting = [], []
    for cause, count in counts.most_common():
        (ready if count >= PROMOTION_THRESHOLD else waiting).append((cause, count))

    out = ["原因の頻度", ""]
    for cause, count in ready:
        mark = " (already a rule)" if cause in existing else ""
        out.append(f"  ✅ {cause} — {count}件 [{', '.join(slugs[cause])}]{mark}")
    for cause, count in waiting:
        out.append(
            f"  … {cause} — {count}件 [{', '.join(slugs[cause])}] — "
            f"needs {PROMOTION_THRESHOLD - count} more before it becomes a rule"
        )
    if ready:
        out += [
            "",
            "To promote one, write the rule in your own words — the exact sentence you want",
            "put in front of you before the next interview:",
            "",
            f'  python3 scripts/calibrate.py rules --approve "{ready[0][0]}" --text "..."',
        ]
    out.append(MEASUREMENT_CAVEAT)
    print("\n".join(out))
    return 0


def approve_rule(pipeline: dict, rules: dict, cause: str, text: str) -> int:
    import datetime as dt

    # Guards first, writer dependency after: refusing a promotion must not depend on
    # being able to perform one.
    counts, slugs = rule_candidates(pipeline)
    if counts[cause] < PROMOTION_THRESHOLD:
        sys.exit(
            f"{cause!r} has {counts[cause]} supporting entr(y/ies); {PROMOTION_THRESHOLD} required.\n"
            "One company's rejection reason is that company's measurement, not your weakness."
        )
    entries = rules.setdefault("rules", [])
    if any(r.get("id") == cause for r in entries):
        sys.exit(f"a rule for {cause!r} already exists in {RULES}")

    import yaml
    entries.append(
        {
            "id": cause,
            "text": text,
            "status": "active",
            "source": "derived_from_rejections",
            "supported_by": slugs[cause],
            "created": dt.date.today().isoformat(),
        }
    )
    RULES.parent.mkdir(parents=True, exist_ok=True)
    RULES.write_text(
        yaml.safe_dump(rules, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8"
    )
    print(f"rule added: {text}")
    print(RULES.resolve())
    print("It will appear in <career_status> from the next prompt on.")
    return 0


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    pipeline = load(PIPELINE)
    if not argv:
        return report(pipeline)
    if argv[0] != "rules":
        sys.exit("usage: calibrate.py [rules [--approve <root_cause> --text <rule>]]")
    rules = load(RULES, required=False)
    if "--approve" in argv:
        try:
            cause = argv[argv.index("--approve") + 1]
            text = argv[argv.index("--text") + 1]
        except (ValueError, IndexError):
            sys.exit('usage: calibrate.py rules --approve <root_cause> --text "<rule>"')
        return approve_rule(pipeline, rules, cause, text)
    return rules_report(pipeline, rules)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
