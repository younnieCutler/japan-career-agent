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
    RULE_IDS,
    UXRegressionError,
    load_registry,
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
        self.assertFalse(report["blocking_ci_ready"])

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
