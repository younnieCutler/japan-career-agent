#!/usr/bin/env python3
"""Focused tests for the behavior-evaluation schema and registered adapter runner."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import run_behavior_evals as runner


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "_shared" / "behavior_eval_schema.yml"


class BehaviorEvalSchemaTests(unittest.TestCase):
    def test_repository_schema_loads_and_uses_registered_adapters(self) -> None:
        scenarios = runner.load_scenarios(SCHEMA)
        self.assertEqual(len(scenarios), 3)
        self.assertTrue(all(item.adapter in runner.ADAPTERS for item in scenarios))
        self.assertTrue(all(item.execution_mode == "contract_audit" for item in scenarios))

    def test_arbitrary_command_and_absolute_input_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            schema = Path(temporary) / "invalid.yml"
            schema.write_text(
                """
schema_version: 1
contract:
  execution_modes: [contract_audit, behavior_replay, runtime_e2e, live_canary]
  classifications: [contract_audit_pass, contract_audit_fail, behavior_replay_pass, behavior_replay_fail, runtime_e2e_pass, runtime_e2e_fail, not_executable]
  risk_classes: [critical, high, medium, low]
  assertion_types: [exit_code, stdout_contains, stdout_not_contains, stderr_contains, stderr_not_contains, stdout_json_path_equals]
scenarios:
  - id: INVALID-001
    skill: test
    adapter: mock_interviewer_contract
    command: powershell
    execution_mode: contract_audit
    classification: contract_audit_pass
    risk_class: critical
    inputs:
      - C:\\outside\\secret.txt
    assertions:
      - id: exits
        type: exit_code
        expected: 0
""",
                encoding="utf-8",
            )
            with self.assertRaises(runner.BehaviorEvalError):
                runner.load_scenarios(schema)

    def test_result_contract_contains_identity_and_hashes(self) -> None:
        document = runner.run(SCHEMA, {"CONTRACT-MOCK-001"})
        result = document["scenarios"][0]
        self.assertIsNone(document["model_identity"])
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["input_sha256"])
        self.assertTrue(result["output_sha256"])
        self.assertIn("repository_commit", result["runtime_identity"])
        self.assertIn("duration_ms", result)

    def test_failed_behavior_replay_has_its_own_classification(self) -> None:
        scenario = runner.Scenario(
            scenario_id="REPLAY-FAIL-001",
            skill="mock-interviewer",
            adapter="mock_interviewer_contract",
            execution_mode="behavior_replay",
            classification="behavior_replay_pass",
            risk_class="critical",
            inputs=(),
            assertions=({"id": "must-fail", "type": "exit_code", "expected": 99},),
        )
        result = runner.evaluate_scenario(scenario, {})
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["classification"], "behavior_replay_fail")

if __name__ == "__main__":
    unittest.main()
