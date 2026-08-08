#!/usr/bin/env python3
"""Frozen routing benchmark evaluator for the Routing Autoresearch loop.

This module is the evaluator. A research candidate may not modify it, the fixtures it reads, or
the KEEP/DISCARD semantics below; `scripts/routing_autoresearch.py` enforces that structurally by
refusing any candidate whose diff touches these paths.

Fixture text is untrusted data. It is only ever compared as a string against subject output — a
fixture cannot supply a regex, a command, a path outside the fixture file, or a callback.

Holdout isolation: `report()` returns aggregate counts for the holdout set. Per-fixture holdout
detail is only produced when `reveal=True`, which the autoresearch runner never passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAREER_ROOT = ROOT / "skills" / "career-agent"
SKILLS_ROOT = ROOT / "skills"
FIXTURE_DIR = CAREER_ROOT / "tests" / "fixtures"

EVALUATOR_VERSION = 1

# A frozen benchmark is never edited; a corrected or extended one is a new version, and the old
# one stays readable so its recorded results remain reproducible.
BENCHMARKS = {
    "routing-eval-v1": {
        "dev": FIXTURE_DIR / "routing_eval_v1_dev.yml",
        "holdout": FIXTURE_DIR / "routing_eval_v1_holdout.yml",
    },
    "routing-eval-v2": {
        "dev": FIXTURE_DIR / "routing_eval_v2_dev.yml",
        "holdout": FIXTURE_DIR / "routing_eval_v2_holdout.yml",
    },
}
BENCHMARK_VERSION = "routing-eval-v2"
FIXTURE_PATHS = BENCHMARKS[BENCHMARK_VERSION]

# The production surface a candidate is allowed to mutate. Everything the evaluator reads to make
# a judgement lives outside it.
SUBJECT_PATHS = (
    CAREER_ROOT / "references" / "routing.yml",
    CAREER_ROOT / "routing.py",
)

FALLBACK = "fallback"

RISK_CLASSES = frozenset({"critical", "fallback", "normal"})
CATEGORIES = frozenset({
    "direct_intent",
    "paraphrase",
    "multilingual",
    "negation",
    "mixed_intent",
    "precedence",
    "ambiguous",
    "unmatched",
    "generic_interview",
    "generic_research",
    "document_intent",
    "shinsotsu_boundary",
    "chuto_boundary",
})
_EXPECTED_KEYS = frozenset({"track", "stage", "skill", "reference", "explicit_intent"})
_INPUT_KEYS = frozenset({"message", "track", "stage"})
_CONSTRAINT_KEYS = frozenset({"forbidden_references", "must_not_change_stage"})
_FIXTURE_KEYS = frozenset({"id", "input", "expected", "constraints", "risk_class", "category"})

# AG-3: a production rule that names a fixture, quotes a whole benchmark utterance, or reaches
# into the evaluator has memorized the benchmark instead of generalizing.
_EVALUATOR_TOKENS = ("routing_eval", "routing_autoresearch", "routing_eval_v1")

# Gate 0 rules. These are not accuracy: inventing an intent the user never stated, or moving the
# lifecycle stage to make a route fire, breaks the decision philosophy no matter what it does to
# the score, so the runner reads them before it looks at anything else.
_PHILOSOPHY_RULES = frozenset({"explicit_intent", "stage_mutated"})


class RoutingEvalError(ValueError):
    """Raised when the benchmark, a fixture, or the subject contract is malformed."""


@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    message: str
    track_in: str | None
    stage_in: str | None
    expected: dict[str, Any]
    forbidden_references: tuple[str, ...]
    must_not_change_stage: bool
    risk_class: str
    categories: tuple[str, ...]


@dataclass(frozen=True)
class Failure:
    fixture_id: str
    rule: str
    detail: str
    critical: bool


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RoutingEvalError(message)


def _string_list(value: Any, where: str) -> tuple[str, ...]:
    _require(isinstance(value, list), f"{where}: expected a list")
    _require(
        all(isinstance(item, str) and item for item in value),
        f"{where}: expected non-empty strings",
    )
    return tuple(value)


def load_fixtures(path: Path, benchmark: str = BENCHMARK_VERSION) -> tuple[Fixture, ...]:
    """Parse and strictly validate one benchmark file.

    Strict rather than lenient on purpose: an unknown key is how an expectation silently stops
    being checked, and a benchmark that quietly checks less is worse than one that fails loudly.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _require(isinstance(data, dict), f"{path.name}: expected a mapping")
    _require(
        data.get("benchmark_version") == benchmark,
        f"{path.name}: benchmark_version must be {benchmark}",
    )
    raw = data.get("fixtures")
    _require(isinstance(raw, list) and bool(raw), f"{path.name}: fixtures must be a non-empty list")

    fixtures: list[Fixture] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        where = f"{path.name}[{index}]"
        _require(isinstance(item, dict), f"{where}: expected a mapping")
        _require(not set(item) - _FIXTURE_KEYS, f"{where}: unknown keys {sorted(set(item) - _FIXTURE_KEYS)}")

        fixture_id = item.get("id")
        _require(isinstance(fixture_id, str) and fixture_id.startswith("ROUTE-"), f"{where}: bad id")
        _require(fixture_id not in seen, f"{where}: duplicate id {fixture_id}")
        seen.add(fixture_id)

        payload = item.get("input")
        _require(isinstance(payload, dict), f"{where}: input must be a mapping")
        _require(not set(payload) - _INPUT_KEYS, f"{where}: unknown input keys")
        message = payload.get("message")
        _require(isinstance(message, str) and message.strip(), f"{where}: input.message required")
        track_in = payload.get("track")
        _require(track_in is None or track_in in {"chuto", "shinsotsu"}, f"{where}: bad input.track")
        stage_in = payload.get("stage")
        _require(stage_in is None or isinstance(stage_in, str), f"{where}: bad input.stage")

        expected = item.get("expected")
        _require(isinstance(expected, dict) and bool(expected), f"{where}: expected required")
        _require(not set(expected) - _EXPECTED_KEYS, f"{where}: unknown expected keys")

        constraints = item.get("constraints") or {}
        _require(isinstance(constraints, dict), f"{where}: constraints must be a mapping")
        _require(not set(constraints) - _CONSTRAINT_KEYS, f"{where}: unknown constraint keys")
        forbidden = constraints.get("forbidden_references", [])
        forbidden_references = _string_list(forbidden, f"{where}.forbidden_references") if forbidden else ()
        must_not_change_stage = bool(constraints.get("must_not_change_stage", False))
        _require(
            not must_not_change_stage or stage_in is not None,
            f"{where}: must_not_change_stage needs input.stage",
        )

        risk_class = item.get("risk_class", "normal")
        _require(risk_class in RISK_CLASSES, f"{where}: risk_class must be one of {sorted(RISK_CLASSES)}")
        categories = _string_list(item.get("category", []), f"{where}.category")
        _require(bool(categories), f"{where}: at least one category required")
        unknown = sorted(set(categories) - CATEGORIES)
        _require(not unknown, f"{where}: unknown categories {unknown}")

        fixtures.append(
            Fixture(
                fixture_id=fixture_id,
                message=message,
                track_in=track_in,
                stage_in=stage_in,
                expected=dict(expected),
                forbidden_references=forbidden_references,
                must_not_change_stage=must_not_change_stage,
                risk_class=risk_class,
                categories=categories,
            )
        )
    return tuple(fixtures)


def _ensure_subject_path() -> None:
    if str(CAREER_ROOT) not in sys.path:
        sys.path.insert(0, str(CAREER_ROOT))


def _import_subject() -> Any:
    _ensure_subject_path()
    import routing  # noqa: PLC0415 — imported late so a candidate's edit is picked up per run

    return routing


def _stage_fallback(stage: str, skill: str | None) -> list[str]:
    _ensure_subject_path()
    from models import REFERENCE_BY_STAGE  # noqa: PLC0415

    if not skill:
        return []
    return [
        name
        for name in REFERENCE_BY_STAGE.get(stage, ())
        if (SKILLS_ROOT / skill / name).exists()
    ]


def evaluate_fixture(fixture: Fixture, routing: Any) -> tuple[Failure, ...]:
    """Run the routing subject on one fixture and return every contract violation it produced."""
    failures: list[Failure] = []
    critical_by_class = fixture.risk_class == "critical"

    def fail(rule: str, detail: str, *, critical: bool) -> None:
        failures.append(Failure(fixture.fixture_id, rule, detail, critical))

    try:
        track = routing.infer_track(fixture.message, fixture.track_in)
        stage = routing.stage_for(fixture.message, track or "chuto", fixture.stage_in)
        intent = routing.explicit_stage_alias(fixture.message)
        context = routing.skill_context(SKILLS_ROOT, stage, fixture.message, track)
    except Exception as exc:  # noqa: BLE001 — any subject error is a candidate crash, not a raise
        fail("subject_crash", f"{type(exc).__name__}: {exc}", critical=True)
        return tuple(failures)

    references = list(context.get("references", []))
    skill = context.get("skill")

    # Constraint violations are critical whatever the fixture's risk class: they are the contract,
    # not the accuracy target.
    for forbidden in fixture.forbidden_references:
        if forbidden in references:
            fail("forbidden_reference", f"selected {forbidden}", critical=True)
    if fixture.must_not_change_stage and stage != fixture.stage_in:
        fail("stage_mutated", f"{fixture.stage_in!r} -> {stage!r}", critical=True)

    if "track" in fixture.expected and track != fixture.expected["track"]:
        fail("track", f"expected {fixture.expected['track']!r}, got {track!r}", critical=True)
    if "explicit_intent" in fixture.expected and intent != fixture.expected["explicit_intent"]:
        # Forcing an intent onto a message that states none is how ambiguity gets silently
        # resolved, so this is critical regardless of the fixture's risk class.
        fail(
            "explicit_intent",
            f"expected {fixture.expected['explicit_intent']!r}, got {intent!r}",
            critical=True,
        )
    if "stage" in fixture.expected and stage != fixture.expected["stage"]:
        fail("stage", f"expected {fixture.expected['stage']!r}, got {stage!r}", critical=critical_by_class)
    if "skill" in fixture.expected and skill != fixture.expected["skill"]:
        fail("skill", f"expected {fixture.expected['skill']!r}, got {skill!r}", critical=critical_by_class)
    if "reference" in fixture.expected:
        wanted = fixture.expected["reference"]
        if wanted == FALLBACK:
            expected_references = _stage_fallback(stage, skill)
        else:
            expected_references = [wanted]
        if references != expected_references:
            fail(
                "reference",
                f"expected {expected_references!r}, got {references!r}",
                critical=critical_by_class,
            )
    return tuple(failures)


def gaming_failures(fixtures: tuple[Fixture, ...]) -> tuple[str, ...]:
    """AG-3: production rules that name the benchmark instead of generalizing over language."""
    source = "\n".join(path.read_text(encoding="utf-8") for path in SUBJECT_PATHS)
    lowered = source.lower()
    problems: list[str] = []
    for token in _EVALUATOR_TOKENS:
        if token in lowered:
            problems.append(f"subject references the evaluator: {token}")
    for fixture in fixtures:
        if fixture.fixture_id.lower() in lowered:
            problems.append(f"subject names fixture id {fixture.fixture_id}")
        message = fixture.message.strip()
        if len(message) >= 8 and message.lower() in lowered:
            problems.append(f"subject quotes the whole utterance of {fixture.fixture_id}")
    return tuple(dict.fromkeys(problems))


def routing_term_count() -> int:
    """AG-6 complexity signal: how many literal terms the lexicon carries."""
    data = yaml.safe_load((CAREER_ROOT / "references" / "routing.yml").read_text(encoding="utf-8"))
    total = sum(len(terms) for terms in data["track"].values())
    total += sum(len(route["terms"]) for route in data["message_context"])
    total += sum(len(group["terms"]) for group in data["stage_alias"])
    total += sum(len(signal["terms"]) for phases in data["flow_phase"].values() for signal in phases)
    return total


def digest(path: Path) -> str:
    """A content identity for a text file, stable across platforms.

    Line endings are normalized before hashing: a Windows checkout with `core.autocrlf` rewrites
    LF to CRLF on disk, which changes every byte in the file and none of the benchmark. Hashing
    raw bytes made the frozen-digest pin fail on Windows and only on Windows.
    """
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


def fingerprint(fixture_id: str) -> str:
    """A stable, non-reversing handle for one failing fixture.

    The runner has to answer "is this a failure the best candidate already had, or a new one?",
    which a count cannot answer: trading one critical failure for a different one leaves the count
    unchanged. It needs failure identity — but printing holdout fixture ids into a log the research
    agent reads would hand back exactly the per-fixture holdout detail `report()` withholds. A
    hashed id supports the set comparison and carries nothing back.
    """
    return hashlib.sha256(fixture_id.encode("utf-8")).hexdigest()[:8]


def report(*, reveal: bool = False, benchmark: str = BENCHMARK_VERSION) -> dict[str, Any]:
    """The full deterministic benchmark result for the current working tree."""
    _require(benchmark in BENCHMARKS, f"unknown benchmark: {benchmark}")
    fixture_paths = BENCHMARKS[benchmark]
    routing = _import_subject()
    sets: dict[str, Any] = {}
    all_fixtures: list[Fixture] = []
    critical_ids: list[str] = []
    fallback_ids: list[str] = []
    for name, path in fixture_paths.items():
        fixtures = load_fixtures(path, benchmark)
        all_fixtures.extend(fixtures)
        results = {fixture.fixture_id: evaluate_fixture(fixture, routing) for fixture in fixtures}
        critical = sum(any(item.critical for item in failures) for failures in results.values())
        fallback = sum(
            bool(results[fixture.fixture_id]) for fixture in fixtures if fixture.risk_class == "fallback"
        )
        critical_ids.extend(
            fixture_id for fixture_id, failures in results.items() if any(item.critical for item in failures)
        )
        fallback_ids.extend(
            fixture.fixture_id
            for fixture in fixtures
            if fixture.risk_class == "fallback" and results[fixture.fixture_id]
        )
        summary: dict[str, Any] = {
            "total": len(fixtures),
            "correct": sum(not failures for failures in results.values()),
            "philosophy_failures": sum(
                any(item.rule in _PHILOSOPHY_RULES for item in failures) for failures in results.values()
            ),
            "critical_failures": critical,
            "fallback_failures": fallback,
        }
        if reveal or name == "dev":
            summary["failures"] = [
                {"id": item.fixture_id, "rule": item.rule, "detail": item.detail, "critical": item.critical}
                for failures in results.values()
                for item in failures
            ]
        sets[name] = summary

    gaming = gaming_failures(tuple(all_fixtures))
    return {
        "benchmark": benchmark,
        "evaluator_version": EVALUATOR_VERSION,
        "dev": sets["dev"],
        "holdout": sets["holdout"],
        "gaming_failures": len(gaming),
        "gaming_detail": list(gaming),
        "routing_terms": routing_term_count(),
        # Failure identity across both sets, for the runner's subset gates.
        "critical_fingerprint": " ".join(sorted(fingerprint(item) for item in critical_ids)),
        "fallback_fingerprint": " ".join(sorted(fingerprint(item) for item in fallback_ids)),
        "identity": {
            "python": platform.python_version(),
            "os": platform.system(),
            "evaluator": digest(Path(__file__)),
            "fixtures": {name: digest(path) for name, path in fixture_paths.items()},
            "subject": {path.name: digest(path) for path in SUBJECT_PATHS},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen routing benchmark.")
    parser.add_argument(
        "--reveal-holdout",
        action="store_true",
        help="Include per-fixture holdout failures. For human benchmark design only — the "
        "autoresearch runner must never pass it.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON.")
    parser.add_argument(
        "--benchmark",
        default=BENCHMARK_VERSION,
        choices=sorted(BENCHMARKS),
        help="Which frozen benchmark to score against.",
    )
    arguments = parser.parse_args()

    result = report(reveal=arguments.reveal_holdout, benchmark=arguments.benchmark)
    if arguments.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    dev, holdout = result["dev"], result["holdout"]
    print(f"benchmark: {result['benchmark']} (evaluator v{result['evaluator_version']})")
    print(f"dev:     {dev['correct']}/{dev['total']} correct, {dev['critical_failures']} critical")
    print(
        f"holdout: {holdout['correct']}/{holdout['total']} correct, "
        f"{holdout['critical_failures']} critical, {holdout['fallback_failures']} fallback"
    )
    print(f"gaming failures: {result['gaming_failures']}  routing terms: {result['routing_terms']}")
    for problem in result["gaming_detail"]:
        print(f"  ! {problem}")
    for failure in dev.get("failures", []):
        print(f"  dev {failure['id']}: {failure['rule']} — {failure['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
