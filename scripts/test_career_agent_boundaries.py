#!/usr/bin/env python3
"""Focused tests for the staged Career Agent architecture guard."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import check_career_agent_boundaries as boundaries  # noqa: E402


class CareerAgentBoundaryTests(unittest.TestCase):
    def test_current_stage_has_no_boundary_errors(self) -> None:
        self.assertEqual(boundaries.validate(), [])

    def test_models_and_validation_are_not_transitional_runtime_importers(self) -> None:
        self.assertNotIn("models", boundaries.TRANSITIONAL_RUNTIME_IMPORTERS)
        self.assertNotIn("validation", boundaries.TRANSITIONAL_RUNTIME_IMPORTERS)

    def test_owner_contract_covers_extracted_symbols(self) -> None:
        self.assertEqual(boundaries.OWNED_SYMBOLS["CareerError"], "models")
        self.assertEqual(boundaries.OWNED_SYMBOLS["validate_event"], "validation")
        self.assertEqual(boundaries.OWNED_SYMBOLS["atomic_write_text"], "persistence")
        self.assertEqual(boundaries.OWNED_SYMBOLS["language_for"], "routing")
        self.assertEqual(boundaries.OWNED_SYMBOLS["approve"], "lifecycle")
        self.assertEqual(boundaries.OWNED_SYMBOLS["upsert_pipeline_entry"], "projection")
        self.assertTrue(boundaries._is_thin_facade(boundaries._module_tree("runtime"), "approve"))


if __name__ == "__main__":
    unittest.main()
