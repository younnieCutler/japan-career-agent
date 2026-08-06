"""Deterministic P2 UX regression rubric and calibration tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent / "tests"
sys.path.insert(0, str(TESTS))
from ux_regression_eval import (  # noqa: E402
    BAD_COUNT,
    GOOD_COUNT,
    INJECTION_COUNT,
    JUDGE_RUNS,
    RULE_IDS,
    SUBJECT_RUNS,
    JudgeRun,
    SubjectRun,
    UXRegressionError,
    evaluate_output,
    load_registry,
    run_advisory_calibration,
    run_calibration,
)


class UXRegressionEvalTests(unittest.TestCase):
    def test_registry_has_the_required_rubric_matrix(self) -> None:
        fixtures, injections = load_registry()
        self.assertEqual(len(fixtures), GOOD_COUNT + BAD_COUNT)
        self.assertEqual(sum(item.category == "known_good" for item in fixtures), GOOD_COUNT)
        self.assertEqual(sum(item.category == "known_bad" for item in fixtures), BAD_COUNT)
        self.assertEqual(len(injections), INJECTION_COUNT)
        self.assertEqual(set(RULE_IDS), {rule for item in fixtures for rule in item.checks})
        self.assertTrue(all(item.subject_prompt for item in (*fixtures, *injections)))

    def test_known_good_fixtures_have_no_false_positives(self) -> None:
        report = run_calibration()
        self.assertEqual(report["known_good"]["passed"], GOOD_COUNT)
        self.assertEqual(report["known_good"]["false_positives"], [])

    def test_known_bad_negative_controls_are_all_detected(self) -> None:
        report = run_calibration()
        self.assertEqual(report["known_bad"]["detected"], BAD_COUNT)
        self.assertEqual(report["known_bad"]["missed"], [])
        self.assertEqual(report["negative_control_detection_rate"], 1.0)

    def test_all_five_regression_injections_are_detected(self) -> None:
        report = run_calibration()
        self.assertEqual(report["regression_injections"]["detected"], INJECTION_COUNT)
        self.assertEqual(report["regression_injections"]["missed"], [])

    def test_calibration_is_reproducible_and_live_judge_remains_advisory(self) -> None:
        report = run_calibration()
        self.assertTrue(report["reproducible"])
        self.assertEqual(report["false_positive_count"], 0)
        self.assertEqual(report["false_negative_count"], 0)
        self.assertTrue(report["deterministic_ci_ready"])
        self.assertFalse(report["live_judge_blocking_ready"])

    def test_advisory_calibration_runs_three_by_three_on_actual_subject_output(self) -> None:
        fixtures, injections = load_registry()
        controls = {item.fixture_id: item for item in (*fixtures, *injections)}
        subject_calls: list[tuple[str, int]] = []
        judge_calls: list[tuple[str, int]] = []

        def subject_runner(case, run_number):
            subject_calls.append((case.fixture_id, run_number))
            return SubjectRun(
                output=controls[case.fixture_id].output,
                model="synthetic-subject-v1",
                conditions={"temperature": 0, "seed": 7},
            )

        def judge_runner(case, subject, run_number):
            judge_calls.append((case.fixture_id, run_number))
            control = controls[case.fixture_id]
            results = evaluate_output(control, subject.output)
            failed = tuple(item.rule_id for item in results if not item.passed)
            if control.category == "known_good":
                passed = not failed
            else:
                passed = not control.target_rule or control.target_rule not in failed
            return JudgeRun(
                passed=passed,
                model="synthetic-judge-v1",
                failure_tags=failed,
                conditions={"temperature": 0, "seed": 11},
            )

        report = run_advisory_calibration(
            subject_runner=subject_runner,
            judge_runner=judge_runner,
        )
        expected_subject_calls = (GOOD_COUNT + BAD_COUNT + INJECTION_COUNT) * SUBJECT_RUNS
        expected_judge_calls = expected_subject_calls * JUDGE_RUNS
        self.assertEqual(len(subject_calls), expected_subject_calls)
        self.assertEqual(len(judge_calls), expected_judge_calls)
        self.assertEqual(report["subject_runs_per_fixture"], SUBJECT_RUNS)
        self.assertEqual(report["judge_runs_per_subject"], JUDGE_RUNS)
        self.assertEqual(report["model_identity"]["subject_models"], ["synthetic-subject-v1"])
        self.assertEqual(report["model_identity"]["judge_models"], ["synthetic-judge-v1"])
        self.assertEqual(report["judge"]["false_positive_count"], 0)
        self.assertEqual(report["judge"]["false_negative_count"], 0)
        self.assertTrue(report["variance"]["subject"]["stable"])
        self.assertTrue(report["variance"]["judge"]["stable"])
        self.assertTrue(report["deterministic_ci_ready"])
        self.assertFalse(report["live_judge_blocking_ready"])

    def test_advisory_evaluator_uses_changed_subject_output_and_records_variance(self) -> None:
        fixtures, injections = load_registry()
        controls = {item.fixture_id: item for item in (*fixtures, *injections)}

        def subject_runner(case, run_number):
            output = controls[case.fixture_id].output
            if case.fixture_id == "GOOD-001" and run_number == 2:
                output = "There is no AWS information, so I will use the average candidate level."
            return SubjectRun(output=output, model="synthetic-subject-v1")

        def judge_runner(case, subject, run_number):
            control = controls[case.fixture_id]
            failed = tuple(item.rule_id for item in evaluate_output(control, subject.output) if not item.passed)
            passed = not failed if control.category == "known_good" else (
                not control.target_rule or control.target_rule not in failed
            )
            return JudgeRun(passed=passed, model="synthetic-judge-v1", failure_tags=failed)

        report = run_advisory_calibration(
            subject_runner=subject_runner,
            judge_runner=judge_runner,
        )
        self.assertEqual(report["variance"]["subject"]["unstable_fixtures"], ["GOOD-001"])
        self.assertGreater(report["deterministic"]["known_good"]["false_positive_count"], 0)
        self.assertGreater(report["judge"]["known_good"]["false_positive_count"], 0)
        self.assertEqual(
            report["observations"]["GOOD-001"]["subject_runs"][1]["deterministic"]["failed_rules"],
            ["unknown_preservation"],
        )

    def test_registry_rejects_an_unregistered_rule(self) -> None:
        original = (TESTS / "fixtures" / "ux_regression.yml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.yml"
            path.write_text(original.replace("unknown_preservation", "made_up_rule", 1), encoding="utf-8")
            with self.assertRaises(UXRegressionError):
                load_registry(path)


if __name__ == "__main__":
    result = unittest.main(exit=False)
    if result.result.wasSuccessful():
        print(f"OK: {result.result.testsRun} UX regression eval tests passed")
    raise SystemExit(0 if result.result.wasSuccessful() else 1)
