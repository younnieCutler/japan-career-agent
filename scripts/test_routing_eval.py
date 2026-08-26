#!/usr/bin/env python3
"""Contract tests for the frozen routing benchmark evaluator.

These are the checks that make the benchmark trustworthy as a research target: the fixtures are
frozen by digest, the schema refuses to silently stop checking something, the evaluator separates
a genuinely better candidate from one that only games the metric, and two runs on the same tree
produce the same numbers.
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import routing_eval  # noqa: E402
from routing_eval import (  # noqa: E402
    FIXTURE_PATHS,
    RoutingEvalError,
    digest,
    evaluate_fixture,
    gaming_failures,
    load_fixtures,
    report,
)

# Every frozen benchmark, including retired ones. Changing a fixture must break this test — a
# research candidate editing the corpus it is scored on is the failure mode this pin exists to
# catch. A deliberate benchmark change means a new benchmark_version and a new entry here, never
# an edit to an existing one: v1's recorded results are only reproducible while v1 is untouched.
FROZEN_DIGESTS = {
    ("routing-eval-v1", "dev"): "e74e9d70ced1d91f",
    ("routing-eval-v1", "holdout"): "4190a5fb71c7bdf6",
    ("routing-eval-v2", "dev"): "0d6432e3d89492c9",
    ("routing-eval-v2", "holdout"): "bdf97d5436c297ab",
    ("routing-eval-v3", "dev"): "326546e80644ab6f",
    ("routing-eval-v3", "holdout"): "7dce28c875bbd38d",
}

VALID_FIXTURE = """
benchmark_version: routing-eval-v3
fixtures:
  - id: ROUTE-T-001
    input: {message: "年収交渉の進め方", track: chuto, stage: "内定・条件交渉"}
    expected: {skill: tenshoku-strategy, reference: references/nenshu-koushou.md}
    risk_class: normal
    category: [direct_intent]
"""


def _write(directory: str, body: str) -> Path:
    path = Path(directory) / "fixture.yml"
    path.write_text(body, encoding="utf-8")
    return path


class BenchmarkFreezeTests(unittest.TestCase):
    def test_every_benchmark_version_matches_its_frozen_digests(self) -> None:
        recorded = {
            (version, name) for version, paths in routing_eval.BENCHMARKS.items() for name in paths
        }
        self.assertEqual(recorded, set(FROZEN_DIGESTS))
        for version, paths in routing_eval.BENCHMARKS.items():
            for name, path in paths.items():
                with self.subTest(version=version, name=name):
                    self.assertEqual(digest(path), FROZEN_DIGESTS[(version, name)])

    def test_a_retired_benchmark_still_loads(self) -> None:
        """v1's recorded results stay reproducible only while v1 parses under its own version."""
        for name, path in routing_eval.BENCHMARKS["routing-eval-v1"].items():
            with self.subTest(name=name):
                self.assertTrue(load_fixtures(path, "routing-eval-v1"))

    def test_the_digest_survives_a_windows_checkout(self) -> None:
        # A Windows checkout with core.autocrlf rewrites LF to CRLF on disk. That changes the
        # bytes and not the benchmark, so hashing raw bytes made the pin above fail on Windows
        # only — the frozen digest has to be a content identity, not a byte identity.
        # Normalize to LF before building the CRLF copy: on Windows the checkout is already CRLF,
        # and a bare \n -> \r\n replacement there would produce \r\r\n and test nothing real.
        source = FIXTURE_PATHS["dev"].read_bytes().replace(b"\r\n", b"\n")
        with tempfile.TemporaryDirectory() as directory:
            lf, crlf = Path(directory) / "lf.yml", Path(directory) / "crlf.yml"
            lf.write_bytes(source)
            crlf.write_bytes(source.replace(b"\n", b"\r\n"))
            self.assertNotEqual(lf.read_bytes(), crlf.read_bytes())
            expected = FROZEN_DIGESTS[(routing_eval.BENCHMARK_VERSION, "dev")]
            self.assertEqual(digest(lf), expected)
            self.assertEqual(digest(crlf), expected)

    def test_every_fixture_category_axis_is_represented(self) -> None:
        covered = {
            category
            for path in FIXTURE_PATHS.values()
            for fixture in load_fixtures(path)
            for category in fixture.categories
        }
        self.assertEqual(covered, routing_eval.CATEGORIES)

    def test_the_current_benchmark_is_not_dominated_by_one_language(self) -> None:
        """v1 was 66% Japanese, so a Korean or English regression was largely invisible."""
        fixtures = [f for path in FIXTURE_PATHS.values() for f in load_fixtures(path)]
        korean = re.compile(r"[\uac00-\ud7a3]")
        japanese = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
        counts = {"ko": 0, "ja": 0, "en": 0}
        for fixture in fixtures:
            key = "ko" if korean.search(fixture.message) else "ja" if japanese.search(fixture.message) else "en"
            counts[key] += 1
        self.assertGreaterEqual(min(counts.values()), len(fixtures) // 5, counts)
        self.assertLessEqual(max(counts.values()), len(fixtures) // 2, counts)

    def test_both_sets_carry_critical_and_fallback_fixtures(self) -> None:
        for name, path in FIXTURE_PATHS.items():
            classes = {fixture.risk_class for fixture in load_fixtures(path)}
            with self.subTest(name=name):
                self.assertIn("critical", classes)
                self.assertIn("fallback", classes)


class SchemaTests(unittest.TestCase):
    def test_a_well_formed_fixture_loads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(len(load_fixtures(_write(directory, VALID_FIXTURE))), 1)

    def test_malformed_fixtures_are_rejected(self) -> None:
        malformed = (
            VALID_FIXTURE.replace("benchmark_version: routing-eval-v3", "benchmark_version: v9"),
            VALID_FIXTURE.replace("risk_class: normal", "risk_class: cosmetic"),
            VALID_FIXTURE.replace("category: [direct_intent]", "category: [made_up_axis]"),
            VALID_FIXTURE.replace("category: [direct_intent]", "category: []"),
            VALID_FIXTURE.replace("    risk_class: normal\n", "    surprise_key: true\n"),
            VALID_FIXTURE.replace("expected: {skill", "expected: {made_up"),
            VALID_FIXTURE + VALID_FIXTURE.split("fixtures:")[1],
            "benchmark_version: routing-eval-v3\nfixtures: []\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            for body in malformed:
                with self.subTest(body=body[-60:]):
                    with self.assertRaises(RoutingEvalError):
                        load_fixtures(_write(directory, body))

    def test_must_not_change_stage_requires_a_starting_stage(self) -> None:
        body = VALID_FIXTURE.replace(
            'input: {message: "年収交渉の進め方", track: chuto, stage: "内定・条件交渉"}',
            'input: {message: "年収交渉の進め方", track: chuto}',
        ).replace("risk_class: normal", "constraints: {must_not_change_stage: true}\n    risk_class: normal")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RoutingEvalError):
                load_fixtures(_write(directory, body))


class _FakeSubject:
    """A stand-in routing module, so a candidate shape can be scored without editing production."""

    def __init__(self, *, skill: str, references: list[str], intent: str | None, crash: bool = False):
        self._skill = skill
        self._references = references
        self._intent = intent
        self._crash = crash

    def infer_track(self, message, requested=None):  # noqa: ARG002
        return requested or "chuto"

    def stage_for(self, message, track, current_stage=None):  # noqa: ARG002
        return current_stage or "内定・条件交渉"

    def explicit_stage_alias(self, message):  # noqa: ARG002
        return self._intent

    def skill_context(self, skills_root, stage, message=None, track=None):  # noqa: ARG002
        if self._crash:
            raise RuntimeError("candidate blew up")
        return {"skill": self._skill, "available": True, "references": list(self._references)}


class CandidateDiscriminationTests(unittest.TestCase):
    """A benchmark that cannot tell these four candidates apart is not worth optimizing against."""

    def setUp(self) -> None:
        self.fixture = load_fixtures(FIXTURE_PATHS["dev"])[0]  # ROUTE-DEV-DIRECT-001

    def test_a_correct_candidate_produces_no_failures(self) -> None:
        subject = _FakeSubject(
            skill="tenshoku-strategy",
            references=["references/nenshu-koushou.md"],
            intent="offer",
        )
        self.assertEqual(evaluate_fixture(self.fixture, subject), ())

    def test_a_wrong_route_is_caught(self) -> None:
        subject = _FakeSubject(
            skill="tenshoku-strategy",
            references=["references/mensetsu-manner.md"],
            intent="offer",
        )
        self.assertEqual([item.rule for item in evaluate_fixture(self.fixture, subject)], ["reference"])

    def test_a_crashing_candidate_is_a_critical_failure_not_an_exception(self) -> None:
        failures = evaluate_fixture(self.fixture, _FakeSubject(skill="x", references=[], intent=None, crash=True))
        self.assertEqual([item.rule for item in failures], ["subject_crash"])
        self.assertTrue(failures[0].critical)

    def test_universal_fallback_loses_the_routed_fixtures(self) -> None:
        """AG-1: routing everything to the stage fallback must not read as an improvement."""
        subject = _FakeSubject(skill="jiko-bunseki", references=[], intent=None)
        routed = [
            fixture
            for fixture in load_fixtures(FIXTURE_PATHS["dev"])
            if fixture.expected.get("reference") not in (None, routing_eval.FALLBACK)
        ]
        self.assertTrue(all(evaluate_fixture(fixture, subject) for fixture in routed))

    def test_universal_specific_route_trips_the_non_capture_fixtures(self) -> None:
        """AG-2: capturing every message with one popular route must trip a forbidden reference."""
        subject = _FakeSubject(
            skill="tenshoku-strategy",
            references=["references/mensetsu-manner.md"],
            intent="interview",
        )
        non_capture = [
            fixture
            for fixture in load_fixtures(FIXTURE_PATHS["dev"])
            if "references/mensetsu-manner.md" in fixture.forbidden_references
        ]
        self.assertTrue(non_capture)
        for fixture in non_capture:
            with self.subTest(fixture=fixture.fixture_id):
                failures = evaluate_fixture(fixture, subject)
                self.assertTrue(any(item.critical for item in failures))

    def test_forcing_an_intent_onto_an_ambiguous_message_is_critical(self) -> None:
        ambiguous = next(
            fixture
            for fixture in load_fixtures(FIXTURE_PATHS["dev"])
            if fixture.expected.get("explicit_intent", "unset") is None
        )
        subject = _FakeSubject(skill="jiko-bunseki", references=[], intent="documents")
        failures = evaluate_fixture(ambiguous, subject)
        self.assertTrue(any(item.rule == "explicit_intent" and item.critical for item in failures))


class AntiGamingTests(unittest.TestCase):
    def test_quoting_a_whole_benchmark_utterance_is_detected(self) -> None:
        fixtures = load_fixtures(FIXTURE_PATHS["dev"])
        original = routing_eval.SUBJECT_PATHS
        with tempfile.TemporaryDirectory() as directory:
            planted = Path(directory) / "routing.yml"
            planted.write_text(f'terms: ["{fixtures[0].message}"]\n', encoding="utf-8")
            routing_eval.SUBJECT_PATHS = (planted,)
            try:
                problems = gaming_failures(fixtures)
            finally:
                routing_eval.SUBJECT_PATHS = original
        self.assertTrue(any(fixtures[0].fixture_id in problem for problem in problems))

    def test_the_shipped_subject_is_clean(self) -> None:
        fixtures = tuple(
            fixture for path in FIXTURE_PATHS.values() for fixture in load_fixtures(path)
        )
        self.assertEqual(gaming_failures(fixtures), ())


class ReproducibilityTests(unittest.TestCase):
    def test_two_runs_on_the_same_tree_agree(self) -> None:
        first, second = report(), report()
        self.assertEqual(first, second)

    def test_the_report_carries_the_identity_needed_to_replay_it(self) -> None:
        identity = report()["identity"]
        self.assertEqual(set(identity), {"python", "os", "evaluator", "fixtures", "subject"})
        self.assertEqual(set(identity["fixtures"]), set(FIXTURE_PATHS))
        self.assertEqual(set(identity["subject"]), {"routing.yml", "routing.py"})

    def test_holdout_detail_is_withheld_unless_explicitly_revealed(self) -> None:
        self.assertNotIn("failures", report()["holdout"])
        self.assertIn("failures", report(reveal=True)["holdout"])


class GateTests(unittest.TestCase):
    """`--gate` is what stops the benchmark from being a number nobody has to act on."""

    def _exit_code(self, summary: dict[str, object]) -> int:
        with unittest.mock.patch.object(routing_eval, "report", return_value=summary):
            with contextlib.redirect_stdout(io.StringIO()):
                return routing_eval.main()

    def _summary(self, **overrides: int) -> dict[str, object]:
        counts = {"dev_critical": 0, "holdout_critical": 0, "gaming": 0, **overrides}
        empty = {"total": 1, "correct": 1, "philosophy_failures": 0, "fallback_failures": 0}
        return {
            "benchmark": "routing-eval-v3",
            "evaluator_version": 2,
            "dev": {**empty, "critical_failures": counts["dev_critical"], "failures": []},
            "holdout": {**empty, "critical_failures": counts["holdout_critical"]},
            "gaming_failures": counts["gaming"],
            "gaming_detail": [],
            "routing_terms": 1,
        }

    def test_the_gate_fails_on_a_critical_or_gaming_failure_from_either_set(self) -> None:
        for field in ("dev_critical", "holdout_critical", "gaming"):
            with self.subTest(field=field):
                with unittest.mock.patch.object(sys, "argv", ["routing_eval.py", "--gate"]):
                    self.assertEqual(self._exit_code(self._summary(**{field: 1})), 1)

    def test_the_gate_passes_a_clean_tree_and_ignores_paraphrase_misses(self) -> None:
        # Overall accuracy is the autoresearch loop's target, not a build condition: failing on a
        # paraphrase the benchmark scores as a miss would block every unrelated change.
        summary = self._summary()
        summary["dev"] = {**summary["dev"], "total": 36, "correct": 30}
        with unittest.mock.patch.object(sys, "argv", ["routing_eval.py", "--gate"]):
            self.assertEqual(self._exit_code(summary), 0)

    def test_without_the_flag_a_critical_failure_still_reports_success(self) -> None:
        # The autoresearch runner reads the report of a candidate that is allowed to be worse.
        with unittest.mock.patch.object(sys, "argv", ["routing_eval.py"]):
            self.assertEqual(self._exit_code(self._summary(holdout_critical=3)), 0)

    def test_the_current_tree_passes_the_gate(self) -> None:
        summary = report()
        self.assertEqual(summary["dev"]["critical_failures"], 0)
        self.assertEqual(summary["holdout"]["critical_failures"], 0)
        self.assertEqual(summary["gaming_failures"], 0)


if __name__ == "__main__":
    result = unittest.main(exit=False)
    if result.result.wasSuccessful():
        print(f"OK: {result.result.testsRun} routing eval tests passed")
    raise SystemExit(0 if result.result.wasSuccessful() else 1)
