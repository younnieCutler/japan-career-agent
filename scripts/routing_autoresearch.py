#!/usr/bin/env python3
"""Routing Autoresearch experiment runner: score one candidate, then KEEP, DISCARD, or CRASH.

The runner is the boundary between a research candidate and the benchmark. It refuses to score a
candidate at all if the diff reaches outside the declared mutation surface, and it evaluates the
gates in lexicographic order — decision philosophy, then safety, then focused regressions, then
held-out accuracy, then fallback preservation, then complexity. A candidate that is more accurate
but breaks an earlier gate is DISCARDed; accuracy never buys back a contract violation.

Usage:
    python scripts/routing_autoresearch.py --baseline            # record the current tree as best
    python scripts/routing_autoresearch.py -m "narrow KO salary paraphrase"
    python scripts/routing_autoresearch.py -m "..." --promote    # + full canonical checks on KEEP
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import routing_eval  # noqa: E402

ROOT = routing_eval.ROOT
# Tracked on purpose. `plan/` is gitignored, and a research log nobody else can read is not a
# record — the point of the append-only contract is that a DISCARD survives the session.
RESULTS = ROOT / "docs" / "routing-autoresearch-results.tsv"

COLUMNS = (
    "timestamp",
    "commit",
    "dirty",
    "benchmark",
    "evaluator",
    "philosophy_failures",
    "critical_failures",
    "regression_failures",
    "heldout_correct",
    "heldout_total",
    "fallback_failures",
    "changed_loc",
    "routing_terms",
    "evaluator_digest",
    "runner_digest",
    "fixture_digest",
    "status",
    "description",
)

# Gate 2. Kept to seconds: the full matrix runs once, on promotion, not once per candidate.
FOCUSED_CHECKS = (
    ("routing eval contract", ("scripts/test_routing_eval.py",)),
    ("career-agent routing", ("skills/career-agent/test_routing.py",)),
    ("career-agent onboarding", ("skills/career-agent/test_onboarding.py",)),
    ("career-agent UX contract", ("skills/career-agent/test_ux.py",)),
    ("reference paths", ("scripts/check_reference_paths.py",)),
)

# Gate 5 defaults. One hypothesis, one owning layer, a diff a reviewer can hold in their head.
DEFAULT_LOC_BUDGET = 25
DEFAULT_TERM_BUDGET = 12

MUTABLE = tuple(str(path.relative_to(ROOT)) for path in routing_eval.SUBJECT_PATHS)

# The harness itself. Listed explicitly so that before it is committed its files do not read as an
# unrelated production change, and after it is committed an edit to any of them still fails the
# digest comparison below. Both directions are covered; neither depends on the other.
HARNESS_PATHS = frozenset(
    {
        "scripts/routing_eval.py",
        "scripts/test_routing_eval.py",
        "scripts/routing_autoresearch.py",
        *(str(path.relative_to(ROOT)) for path in routing_eval.FIXTURE_PATHS.values()),
        str(RESULTS.relative_to(ROOT)),
    }
)


_SCRATCH_DIRECTORIES = frozenset(
    {"__pycache__", ".git", ".pytest_cache", ".ruff_cache", "data", "career-docs", ".agents", ".claude", ".worktrees"}
)


class ExperimentError(RuntimeError):
    """Raised when a candidate cannot be scored at all — an invalid experiment, not a DISCARD."""


def git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=str(ROOT), capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise ExperimentError(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def head_commit() -> str:
    return git("rev-parse", "--short", "HEAD")


def changed_paths(base: str) -> list[str]:
    """Every path that differs from `base`, including uncommitted work.

    Agent/editor scratch directories are excluded for the same reason `check_policy.py` skips
    them: they are local tooling, not this repository's production surface, and flagging them
    would make every experiment INVALID for a reason no candidate caused.
    """
    tracked = git("diff", "--name-only", base).splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(
        path
        for path in {*tracked, *untracked}
        if path and not any(part in _SCRATCH_DIRECTORIES for part in Path(path).parts)
    )


def changed_loc(base: str) -> int:
    total = 0
    for line in git("diff", "--numstat", base, "--", *MUTABLE).splitlines():
        added, removed, _ = line.split("\t", 2)
        total += sum(int(value) for value in (added, removed) if value.isdigit())
    return total


def read_rows() -> list[dict[str, str]]:
    if not RESULTS.is_file():
        return []
    with RESULTS.open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle, delimiter="\t") if row.get("status")]


def current_best(rows: list[dict[str, str]]) -> dict[str, str] | None:
    """The last row that became the thing to beat — a baseline, or a KEEP that replaced it."""
    for row in reversed(rows):
        if row["status"] in {"baseline", "keep"}:
            return row
    return None


def append_row(row: dict[str, Any]) -> None:
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    exists = RESULTS.is_file()
    with RESULTS.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n")
        if not exists:
            writer.writeheader()
        writer.writerow({column: row[column] for column in COLUMNS})


def run_checks(checks: tuple[tuple[str, tuple[str, ...]], ...]) -> list[str]:
    failed: list[str] = []
    for label, command in checks:
        result = subprocess.run(
            [sys.executable, *command], cwd=str(ROOT), capture_output=True, text=True, check=False
        )
        if result.returncode:
            failed.append(label)
            tail = (result.stdout + result.stderr).strip().splitlines()[-6:]
            print(f"  FAIL {label}")
            for line in tail:
                print(f"       {line}")
        else:
            print(f"  ok   {label}")
    return failed


def harness_digests(result: dict[str, Any]) -> tuple[str, str]:
    identity = result["identity"]
    fixtures = "+".join(identity["fixtures"][name] for name in sorted(identity["fixtures"]))
    return identity["evaluator"], fixtures


def enforce_mutation_surface(base: str, result: dict[str, Any], best: dict[str, str]) -> None:
    """A candidate that edits the evaluator, the benchmark, or unrelated production is invalid.

    This runs before any gate is read on purpose. A candidate that could reach the fixtures is not
    a worse candidate — it is an unscoreable one, and printing a number for it would be a lie.
    """
    illegal = [
        path for path in changed_paths(base) if path not in MUTABLE and path not in HARNESS_PATHS
    ]
    if illegal:
        raise ExperimentError(
            "candidate touches paths outside the mutation surface:\n  "
            + "\n  ".join(illegal)
            + f"\nallowed: {', '.join(MUTABLE)}"
        )
    evaluator, fixtures = harness_digests(result)
    if best.get("evaluator_digest") and evaluator != best["evaluator_digest"]:
        raise ExperimentError(
            f"evaluator changed since the baseline ({best['evaluator_digest']} -> {evaluator}); "
            "an evaluator change requires a new benchmark version, not a candidate"
        )
    if best.get("fixture_digest") and fixtures != best["fixture_digest"]:
        raise ExperimentError(
            f"benchmark fixtures changed since the baseline ({best['fixture_digest']} -> {fixtures}); "
            "cut a new benchmark version instead of editing a frozen one"
        )


def _print_identity(result: dict[str, Any], commit: str, dirty: bool) -> None:
    identity = result["identity"]
    print(f"commit {commit}{' (dirty)' if dirty else ''}  python {identity['python']} on {identity['os']}")
    print(f"evaluator {identity['evaluator']}  fixtures {identity['fixtures']}")
    print(f"subject {identity['subject']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Score one Routing Autoresearch candidate.")
    parser.add_argument("-m", "--description", default="", help="What this candidate changed and why.")
    parser.add_argument("--baseline", action="store_true", help="Record this tree as the new baseline.")
    parser.add_argument("--promote", action="store_true", help="Run the full canonical matrix on KEEP.")
    parser.add_argument("--loc-budget", type=int, default=DEFAULT_LOC_BUDGET)
    parser.add_argument("--term-budget", type=int, default=DEFAULT_TERM_BUDGET)
    parser.add_argument(
        "--on-discard",
        choices=("keep", "revert"),
        default="keep",
        help="revert restores the mutation surface from the current best commit.",
    )
    arguments = parser.parse_args()

    if not arguments.baseline and not arguments.description:
        parser.error("-m/--description is required for a candidate run")

    rows = read_rows()
    best = current_best(rows)
    commit = head_commit()
    dirty = bool(git("status", "--porcelain"))

    if arguments.baseline or best is None:
        result = routing_eval.report()
        holdout = result["holdout"]
        evaluator_digest, fixture_digest = harness_digests(result)
        _print_identity(result, commit, dirty)
        append_row(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "commit": commit,
                "dirty": int(dirty),
                "benchmark": result["benchmark"],
                "evaluator": result["evaluator_version"],
                "philosophy_failures": holdout["philosophy_failures"] + result["dev"]["philosophy_failures"],
                "critical_failures": holdout["critical_failures"] + result["dev"]["critical_failures"],
                "regression_failures": 0,
                "heldout_correct": holdout["correct"],
                "heldout_total": holdout["total"],
                "fallback_failures": holdout["fallback_failures"],
                "changed_loc": 0,
                "routing_terms": result["routing_terms"],
                "evaluator_digest": evaluator_digest,
                "runner_digest": routing_eval.digest(Path(__file__)),
                "fixture_digest": fixture_digest,
                "status": "baseline",
                "description": arguments.description or "baseline",
            }
        )
        print(f"BASELINE  heldout {holdout['correct']}/{holdout['total']}  -> {RESULTS.relative_to(ROOT)}")
        return 0

    base_commit = best["commit"]
    try:
        result = routing_eval.report()
    except Exception as exc:  # noqa: BLE001 — a subject that will not load is CRASH, not DISCARD
        print(f"CRASH: {type(exc).__name__}: {exc}")
        return 1

    try:
        enforce_mutation_surface(base_commit, result, best)
    except ExperimentError as exc:
        print(f"INVALID: {exc}")
        return 2

    dev, holdout = result["dev"], result["holdout"]
    philosophy = dev["philosophy_failures"] + holdout["philosophy_failures"]
    critical = dev["critical_failures"] + holdout["critical_failures"]
    loc = changed_loc(base_commit)
    terms = result["routing_terms"]
    _print_identity(result, commit, dirty)
    print(
        f"dev {dev['correct']}/{dev['total']}  holdout {holdout['correct']}/{holdout['total']}  "
        f"(best {best['heldout_correct']}/{best['heldout_total']})  loc +{loc}  terms {terms}"
    )

    reasons: list[str] = []
    regression_failures = 0
    # Gate 0 is absolute: no candidate may invent an intent or move the stage, and the baseline
    # does neither. Gate 1 is monotone against the current best instead — the benchmark starts
    # with known critical failures, and demanding all of them disappear in one candidate would
    # force exactly the multi-hypothesis change Gate 5 exists to prevent. Zero is still required
    # Zero remains the target the benchmark is designed around, not a promotion precondition:
    # blocking an unrelated improvement on pre-existing failures is the same deadlock.
    if philosophy:
        reasons.append(f"gate 0: {philosophy} decision-philosophy failures")
    elif critical > int(best["critical_failures"]):
        reasons.append(f"gate 1: critical failures {critical} > best {best['critical_failures']}")
    elif result["gaming_failures"]:
        reasons.append(f"gate 1: {result['gaming_failures']} anti-gaming failures")
        for problem in result["gaming_detail"]:
            print(f"  ! {problem}")
    else:
        print("focused checks:")
        failed = run_checks(FOCUSED_CHECKS)
        regression_failures = len(failed)
        if failed:
            reasons.append(f"gate 2: {', '.join(failed)}")
        elif holdout["correct"] <= int(best["heldout_correct"]):
            reasons.append(
                f"gate 3: holdout {holdout['correct']} does not beat best {best['heldout_correct']}"
            )
        elif holdout["fallback_failures"] > int(best["fallback_failures"]):
            reasons.append(
                f"gate 4: fallback failures {holdout['fallback_failures']} > {best['fallback_failures']}"
            )
        elif loc > arguments.loc_budget:
            reasons.append(f"gate 5: changed LOC {loc} > budget {arguments.loc_budget}")
        elif terms - int(best["routing_terms"]) > arguments.term_budget:
            reasons.append(
                f"gate 5: +{terms - int(best['routing_terms'])} routing terms > budget {arguments.term_budget}"
            )

    status = "discard" if reasons else "keep"
    if status == "keep" and arguments.promote:
        print("canonical checks:")
        if run_checks((("run_all_checks", ("scripts/run_all_checks.py",)),)):
            status = "discard"
            reasons.append("gate 6: canonical repository checks failed")

    append_row(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "commit": commit,
            "dirty": int(dirty),
            "benchmark": result["benchmark"],
            "evaluator": result["evaluator_version"],
            "philosophy_failures": philosophy,
            "critical_failures": critical + result["gaming_failures"],
            "regression_failures": regression_failures,
            "heldout_correct": holdout["correct"],
            "heldout_total": holdout["total"],
            "fallback_failures": holdout["fallback_failures"],
            "changed_loc": loc,
            "routing_terms": terms,
            "evaluator_digest": harness_digests(result)[0],
            "runner_digest": routing_eval.digest(Path(__file__)),
            "fixture_digest": harness_digests(result)[1],
            "status": status,
            "description": arguments.description,
        }
    )

    if status == "keep":
        print(f"KEEP  {best['heldout_correct']} -> {holdout['correct']} held-out correct")
        return 0

    print("DISCARD  " + "; ".join(reasons))
    if arguments.on_discard == "revert":
        git("checkout", base_commit, "--", *MUTABLE)
        print(f"reverted {', '.join(MUTABLE)} to {base_commit}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExperimentError as error:
        print(f"INVALID: {error}")
        raise SystemExit(2) from error
