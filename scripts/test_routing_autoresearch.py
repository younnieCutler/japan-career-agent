#!/usr/bin/env python3
"""Contract tests for the Routing Autoresearch runner's gate logic.

The runner decides what counts as an improvement, so its own rules need the same scrutiny as the
evaluator's: a subset test that silently degrades into a count comparison, or a judging file that
is recorded but never checked, would let a candidate through that should have been rejected.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path, PurePosixPath

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


def _harness_files() -> list[Path]:
    """Every file the harness reads to produce or judge a result.

    Derived from the runner's own declarations rather than listed here, so a file added to the
    harness is covered by the portability checks below without anyone remembering to add it.
    """
    return sorted(
        {
            *(path for group in runner.JUDGING_FILES.values() for path in group),
            *routing_eval.FIXTURE_PATHS.values(),
            *routing_eval.SUBJECT_PATHS,
        }
    )


class WindowsCheckoutTests(unittest.TestCase):
    """The harness is authored on macOS and runs in CI on Windows.

    Three Windows-only defects reached CI before these existed, and all three were the same
    mistake in different clothes: assuming the authoring platform's convention. Byte-hashing a
    file that `core.autocrlf` rewrites, and comparing native-separator paths against git output
    that is always POSIX. Neither is visible locally, so both need a check that simulates the
    difference rather than a reviewer who remembers to think about it.

    These iterate over the harness's declared file lists, so they cover new files automatically.
    """

    def test_every_digested_file_hashes_the_same_under_crlf(self) -> None:
        files = _harness_files()
        self.assertGreaterEqual(len(files), 6)
        with tempfile.TemporaryDirectory() as directory:
            for source in files:
                lf = source.read_bytes().replace(b"\r\n", b"\n")
                copy = Path(directory) / f"{source.name}.crlf"
                copy.write_bytes(lf.replace(b"\n", b"\r\n"))
                with self.subTest(file=source.name):
                    self.assertIn(b"\r\n", copy.read_bytes())
                    self.assertEqual(routing_eval.digest(copy), routing_eval.digest(source))

    def test_the_benchmark_parses_identically_under_crlf(self) -> None:
        """A digest that survives CRLF is not enough if the parsed fixtures differ."""
        with tempfile.TemporaryDirectory() as directory:
            for name, source in routing_eval.FIXTURE_PATHS.items():
                lf = source.read_bytes().replace(b"\r\n", b"\n")
                copy = Path(directory) / f"{name}.yml"
                copy.write_bytes(lf.replace(b"\n", b"\r\n"))
                with self.subTest(name=name):
                    self.assertEqual(routing_eval.load_fixtures(copy), routing_eval.load_fixtures(source))

    def test_no_path_set_uses_a_native_separator(self) -> None:
        for name, paths in (("MUTABLE", runner.MUTABLE), ("HARNESS_PATHS", runner.HARNESS_PATHS)):
            for path in paths:
                with self.subTest(name=name, path=path):
                    self.assertNotIn("\\", path)
                    self.assertEqual(path, PurePosixPath(path).as_posix())

    def test_the_mutation_surface_matches_what_git_would_report(self) -> None:
        tracked = set(runner.git("ls-files").splitlines())
        for path in runner.MUTABLE:
            with self.subTest(path=path):
                self.assertIn(path, tracked)

    def test_every_harness_path_is_declared_relative_to_the_repository(self) -> None:
        for path in _harness_files():
            with self.subTest(path=path.name):
                self.assertTrue(path.is_absolute())
                self.assertTrue(path.is_file())
                path.relative_to(runner.ROOT)  # raises if the harness reaches outside the repo

    def test_no_module_stringifies_a_relative_path(self) -> None:
        """The separator defect cannot be caught by running on POSIX, so ban its shape instead.

        Wrapping a `relative_to()` result in `str()` yields backslashes on Windows and forward
        slashes here, and those strings are compared against git output that is POSIX everywhere.
        Running the code locally proves nothing; the only local signal is the expression itself.
        Use `.as_posix()`.
        """
        offender = re.compile(r"str\([^()]*\.relative_to\(")
        for path in _harness_files():
            if path.suffix != ".py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                with self.subTest(file=path.name, line=number):
                    self.assertIsNone(offender.search(line), f"{path.name}:{number}: use .as_posix()")

    def test_every_text_read_declares_its_encoding(self) -> None:
        """Windows defaults to the locale codepage, and every fixture here is JA/KO text."""
        # Lines that already declare an encoding are skipped, so anything still matching is bare.
        offender = re.compile(r"(?<![.\w])open\(|\.read_text\(|\.write_text\(")
        for path in _harness_files():
            if path.suffix != ".py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "encoding=" in line or line.lstrip().startswith("#"):
                    continue
                with self.subTest(file=path.name, line=number):
                    self.assertIsNone(offender.search(line), f"{path.name}:{number}: pass encoding=")

    def test_the_log_writer_emits_one_line_ending_on_every_platform(self) -> None:
        """csv appends \\r\\n on Windows unless both newline="" and lineterminator are set.

        What is on disk after a checkout is git's business — a tracked text file arrives CRLF on
        Windows and that is not a defect. What the writer produces is this runner's business, and
        it must be the same everywhere or the log's line endings depend on who ran the experiment.
        """
        row = {column: "x" for column in runner.COLUMNS}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "results.tsv"
            with mock.patch.object(runner, "RESULTS", target):
                runner.append_row(row)
                runner.append_row(row)
                rows = runner.read_rows()
            self.assertNotIn(b"\r", target.read_bytes())
        self.assertEqual(len(rows), 2)

    def test_the_log_reader_accepts_a_crlf_checkout(self) -> None:
        """The other half: on Windows the log the reader opens will have CRLF endings."""
        if not runner.RESULTS.is_file():
            self.skipTest("no results log in this tree")
        source = runner.RESULTS.read_bytes().replace(b"\r\n", b"\n")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "results.tsv"
            target.write_bytes(source.replace(b"\n", b"\r\n"))
            with mock.patch.object(runner, "RESULTS", target):
                crlf_rows = runner.read_rows()
                crlf_best = runner.current_best(crlf_rows)
        self.assertEqual(crlf_rows, runner.read_rows())
        self.assertEqual(crlf_best, runner.current_best(runner.read_rows()))


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


class ProgramTests(unittest.TestCase):
    """The research program is the agent's whole picture of the harness, so it must stay true.

    A capsule that has drifted is worse than none: the agent trusts it instead of reading the
    code, so a stale budget or a renamed path becomes a wrong action rather than a lookup miss.
    """

    PROGRAM = runner.ROOT / "docs" / "routing-autoresearch-program.md"

    def setUp(self) -> None:
        self.text = self.PROGRAM.read_text(encoding="utf-8")

    def test_it_names_the_real_mutation_surface_and_nothing_else(self) -> None:
        for path in runner.MUTABLE:
            with self.subTest(path=path):
                self.assertIn(path, self.text)
        self.assertIn("routing-autoresearch-results.tsv", runner.RESULTS.name)
        for group in runner.JUDGING_FILES.values():
            for path in group:
                relative = path.relative_to(runner.ROOT).as_posix()
                with self.subTest(path=relative):
                    self.assertNotIn(f"edit {relative}", self.text)

    def test_the_quoted_budgets_match_the_runner(self) -> None:
        self.assertIn(f"{runner.DEFAULT_LOC_BUDGET} changed production lines", self.text)
        self.assertIn(f"{runner.DEFAULT_TERM_BUDGET} added routing terms", self.text)

    def test_every_verdict_the_runner_can_emit_is_documented(self) -> None:
        for verdict in ("provisional_keep", "discard", "infra_error", "INVALID", "CRASH"):
            with self.subTest(verdict=verdict):
                self.assertIn(verdict, self.text)

    def test_it_stays_a_capsule(self) -> None:
        # It exists to replace ~90 KB of source reading per trial. Past roughly 10 KB it stops
        # paying for itself and the agent may as well read the code.
        self.assertLess(len(self.text.encode("utf-8")), 10_000)


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

    def test_a_best_from_another_benchmark_version_is_not_the_thing_to_beat(self) -> None:
        # v1 counts 56 held-out cases over one corpus and v2 counts 134 over another. Comparing a
        # candidate's score against the other version's best is not weaker, it is meaningless —
        # and it would read as a large improvement or regression for no reason.
        rows = [
            {"status": "baseline", "benchmark": "routing-eval-v1", "heldout_correct": "45"},
            {"status": "baseline", "benchmark": "routing-eval-v2", "heldout_correct": "108"},
        ]
        self.assertEqual(runner.current_best(rows, "routing-eval-v1")["heldout_correct"], "45")
        self.assertEqual(runner.current_best(rows, "routing-eval-v2")["heldout_correct"], "108")
        self.assertIsNone(runner.current_best(rows, "routing-eval-v3"))

    def test_every_benchmark_version_is_runnable(self) -> None:
        for version in routing_eval.BENCHMARKS:
            with self.subTest(version=version):
                result = routing_eval.report(benchmark=version)
                self.assertEqual(result["benchmark"], version)
                self.assertGreater(result["holdout"]["total"], 0)

    def test_an_infra_error_never_becomes_the_thing_to_beat(self) -> None:
        # Gates 0-5 passed, but Gate 6 could not be judged. An incomplete verdict must not be
        # promoted to the reference the next candidate is measured against; re-run it instead.
        rows = [
            {"status": "baseline", "heldout_correct": "44"},
            {"status": "infra_error", "heldout_correct": "45"},
        ]
        self.assertEqual(runner.current_best(rows)["heldout_correct"], "44")
        self.assertNotIn("infra_error", runner.BEST_STATUSES)

    def test_local_pollution_only_reports_scratch_paths(self) -> None:
        for path in runner.local_pollution():
            with self.subTest(path=path):
                self.assertTrue(any(part in runner._SCRATCH_DIRECTORIES for part in Path(path).parts))


if __name__ == "__main__":
    result = unittest.main(exit=False)
    if result.result.wasSuccessful():
        print(f"OK: {result.result.testsRun} routing autoresearch runner tests passed")
    raise SystemExit(0 if result.result.wasSuccessful() else 1)
