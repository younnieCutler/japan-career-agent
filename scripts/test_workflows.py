"""Semantic regression tests for the three PR2 executable workflows."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import run_workflows  # noqa: E402


class WorkflowContractTests(unittest.TestCase):
    def test_first_10_minutes(self) -> None:
        result = run_workflows.run_workflow("first-10-minutes")
        self.assertTrue(result["ok"])
        self.assertTrue(result["invariants"]["confirmed_projection"])

    def test_real_application(self) -> None:
        result = run_workflows.run_workflow("real-application")
        self.assertTrue(result["ok"])
        self.assertTrue(result["invariants"]["matched"])
        self.assertTrue(result["invariants"]["missing"])
        self.assertTrue(result["invariants"]["unknown"])
        self.assertTrue(result["invariants"]["conflict"])
        self.assertTrue(result["invariants"]["interview_transition"])

    def test_recovery(self) -> None:
        result = run_workflows.run_workflow("recovery")
        self.assertTrue(result["ok"])
        self.assertTrue(result["invariants"]["canonical_state_unchanged_on_blockers"])
        self.assertTrue(result["invariants"]["restore_is_snapshot_only"])


if __name__ == "__main__":
    unittest.main()
