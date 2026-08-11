#!/usr/bin/env python3
"""Focused tests for the staged Career Agent architecture guard."""

from __future__ import annotations

import ast
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
        self.assertEqual(boundaries.OWNED_SYMBOLS["build_parser"], "command_line")
        self.assertEqual(boundaries.OWNED_SYMBOLS["doctor"], "diagnostics")
        self.assertEqual(boundaries.OWNED_SYMBOLS["readiness"], "views")
        self.assertTrue(boundaries._is_thin_facade(boundaries._module_tree("approvals"), "approve"))

    def test_the_facade_defines_nothing(self) -> None:
        """The executable form of 'a new command needs no change to runtime.py'."""
        tree = boundaries._module_tree(boundaries.FACADE_MODULE)
        defined = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        self.assertEqual(defined, [])

    def test_the_facade_still_re_exports_the_historical_surface(self) -> None:
        tree = boundaries._module_tree(boundaries.FACADE_MODULE)
        exported = {
            alias.asname or alias.name
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        # The four surfaces outside this package that bind to `runtime`/`career_agent` by name.
        for symbol in ("main", "build_parser", "pipeline_file", "PIPELINE_STAGE",
                       "upsert_pipeline_entry", "select_context", "os"):
            self.assertIn(symbol, exported)

    def test_owners_do_not_import_the_cli_layer(self) -> None:
        for module in sorted(boundaries.APPLICATION_MODULES):
            with self.subTest(module=module):
                imports = boundaries._imports(boundaries._module_tree(module))
                self.assertEqual(imports & boundaries.CLI_MODULES, set())

    def test_a_definition_reappearing_in_the_facade_is_reported(self) -> None:
        """Guard the guard: the façade rule must fail on a real definition, not just pass today."""
        tree = ast.parse("import os\n\n\ndef doctor():\n    return {}\n")
        original = boundaries._module_tree
        boundaries._module_tree = lambda module: tree if module == boundaries.FACADE_MODULE else original(module)
        try:
            errors = boundaries.validate()
        finally:
            boundaries._module_tree = original
        self.assertTrue(any("must only re-export" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
