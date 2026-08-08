#!/usr/bin/env python3
"""Contract tests for the Routing Autoresearch runner's gate logic.

The runner decides what counts as an improvement, so its own rules need the same scrutiny as the
evaluator's: a subset test that silently degrades into a count comparison, or a judging file that
is recorded but never checked, would let a candidate through that should have been rejected.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import routing_autoresearch as runner  # noqa: E402
import routing_eval  # noqa: E402


class FailureSubsetTests(unittest.TestCase):
    def test_a_traded_failure_is_new_even_though_the_count_is_unchanged(self) -> None:
        # The reason this gate is a subset test and not `count > best`: fixing one critical
        # failure while introducing a different one leaves the number identical.
        best, candidate = "aaaa1111 bbbb2222", "aaaa1111 cccc3333"
        self.assertEqual(len(best.split()), len(candidate.split()))
        self.assertEqual(runner.new_failures(candidate, best), ["cccc3333"])

    def test_fixing_a_failure_without_adding_one_passes(self) -> None:
        self.assertEqual(runner.new_failures("aaaa1111", "aaaa1111 bbbb2222"), [])

    def test_an_empty_baseline_treats_every_failure_as_new(self) -> None:
        self.assertEqual(runner.new_failures("aaaa1111", ""), ["aaaa1111"])

    def test_a_clean_candidate_against_an_empty_baseline_passes(self) -> None:
        self.assertEqual(runner.new_failures("", ""), [])


class FingerprintTests(unittest.TestCase):
    def test_the_log_never_carries_a_holdout_fixture_id(self) -> None:
        """Aggregate-only holdout results are pointless if the log names the failing fixtures."""
        report = routing_eval.report()
        recorded = report["critical_fingerprint"] + " " + report["fallback_fingerprint"]
        holdout = routing_eval.load_fixtures(routing_eval.FIXTURE_PATHS["holdout"])
        self.assertTrue(holdout)
        for fixture in holdout:
            with self.subTest(fixture=fixture.fixture_id):
                self.assertNotIn(fixture.fixture_id, recorded)

    def test_fingerprints_are_stable_and_distinct(self) -> None:
        self.assertEqual(routing_eval.fingerprint("ROUTE-X-001"), routing_eval.fingerprint("ROUTE-X-001"))
        self.assertNotEqual(routing_eval.fingerprint("ROUTE-X-001"), routing_eval.fingerprint("ROUTE-X-002"))


class JudgingFileTests(unittest.TestCase):
    def test_every_judging_file_is_a_results_column(self) -> None:
        for column in runner.JUDGING_FILES:
            with self.subTest(column=column):
                self.assertIn(column, runner.COLUMNS)

    def test_the_runner_and_its_contract_tests_are_judging_files(self) -> None:
        """The gate logic and the frozen-digest pin decide verdicts, so both must be pinned too."""
        paths = {path.name for group in runner.JUDGING_FILES.values() for path in group}
        self.assertEqual(
            paths,
            {
                "routing_eval.py",
                "routing_autoresearch.py",
                "test_routing_eval.py",
                "test_routing_autoresearch.py",
            },
        )
        for group in runner.JUDGING_FILES.values():
            for path in group:
                with self.subTest(path=path.name):
                    self.assertTrue(path.is_file())

    def test_an_unchanged_harness_passes(self) -> None:
        result = routing_eval.report()
        runner.enforce_judging_files(result, runner.harness_digests(result))

    def test_a_changed_judging_file_makes_the_candidate_invalid(self) -> None:
        result = routing_eval.report()
        digests = runner.harness_digests(result)
        for column in (*runner.JUDGING_FILES, "fixture_digest"):
            best = dict(digests)
            best[column] = "deadbeefdeadbeef"
            with self.subTest(column=column):
                with self.assertRaises(runner.ExperimentError) as caught:
                    runner.enforce_judging_files(result, best)
                self.assertIn(column, str(caught.exception))


class SimplicityTieBreakTests(unittest.TestCase):
    """Gate 7: equal routing behaviour, fewer terms, is an improvement — not a DISCARD."""

    def test_the_bare_form_subsumes_its_own_compounds(self) -> None:
        # The tie-break is only sound when the simpler lexicon really does route identically.
        # Every compound the collapse removed still matches through the bare term.
        subject = routing_eval._import_subject()
        lowered = "面接後のお礼メールを送りたい"
        for compound in ("面接のお礼", "面接後のお礼", "お礼メール"):
            with self.subTest(compound=compound):
                self.assertTrue(subject.term_present("お礼", compound.lower()))
        self.assertTrue(subject.term_present("お礼", lowered))


class LogSchemaTests(unittest.TestCase):
    def test_the_current_header_is_accepted(self) -> None:
        runner.assert_schema(runner.COLUMNS)

    def test_an_older_header_is_refused_rather_than_silently_misread(self) -> None:
        # This is how the log actually broke: columns were added, the existing file kept its old
        # header, and every appended field landed under the wrong name — the runner then read the
        # baseline commit out of a neighbouring column and blamed the candidate for it.
        older = tuple(column for column in runner.COLUMNS if column != "critical_fingerprint")
        with self.assertRaises(runner.ExperimentError) as caught:
            runner.assert_schema(older)
        self.assertIn("critical_fingerprint", str(caught.exception))

    def test_a_reordered_header_is_refused(self) -> None:
        with self.assertRaises(runner.ExperimentError):
            runner.assert_schema(tuple(reversed(runner.COLUMNS)))

    def test_the_tracked_log_matches_the_current_schema(self) -> None:
        if runner.RESULTS.is_file():
            runner.read_rows()


class StatusTests(unittest.TestCase):
    def test_a_provisional_keep_still_becomes_the_thing_to_beat(self) -> None:
        rows = [
            {"status": "baseline", "heldout_correct": "43"},
            {"status": "provisional_keep", "heldout_correct": "44"},
            {"status": "discard", "heldout_correct": "41"},
        ]
        self.assertEqual(runner.current_best(rows)["heldout_correct"], "44")

    def test_a_discard_never_becomes_the_thing_to_beat(self) -> None:
        rows = [{"status": "baseline", "heldout_correct": "43"}, {"status": "discard", "heldout_correct": "50"}]
        self.assertEqual(runner.current_best(rows)["heldout_correct"], "43")

    def test_no_rows_means_no_best(self) -> None:
        self.assertIsNone(runner.current_best([]))


if __name__ == "__main__":
    result = unittest.main(exit=False)
    if result.result.wasSuccessful():
        print(f"OK: {result.result.testsRun} routing autoresearch runner tests passed")
    raise SystemExit(0 if result.result.wasSuccessful() else 1)
