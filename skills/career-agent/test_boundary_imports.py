#!/usr/bin/env python3
"""Smoke-test the public boundary modules introduced by the architecture split."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


BOUNDARY_SYMBOLS = {
    "models": ("TRACKS", "CareerError"),
    "routing": ("infer_track", "stage_for", "flow_phase_for"),
    "persistence": ("read_json", "write_json", "read_toml"),
    "vault": ("CareerVault", "initialize_vault"),
    "proposals": ("run_chat", "list_proposals", "propose_fact"),
    "projection": ("pipeline_file", "upsert_pipeline_entry"),
    "lifecycle": ("approve", "restore_state", "vault_lock", "preflight_confirmation"),
    "personal_timeline": (
        "project", "timeline", "derive_intervals", "document_states",
        "select_personal_context", "historical_comparison", "candidate_profile_values",
    ),
    "private_store": (
        "resolve_private_home", "import_document", "private_doctor", "stray_documents",
        "resolve_document",
    ),
    "diagnostics": ("doctor",),
    "onboarding": ("setup", "set_profile_axis", "complete_onboarding", "DEFAULT_VAULT_PATH"),
    "ingest": ("run_heartbeat", "run_discover", "run_index", "read_stdin_utf8"),
    "experiences": ("add_project", "add_context", "work_events", "list_experiences"),
    "documents": ("build_document_model", "check_document", "render_document"),
    "views": ("status", "readiness", "evidence_pool", "maintenance_check", "weekly_review"),
    "approvals": ("approve", "recover_approval"),
    "guided_flow": ("run_guided",),
    "dispatch": ("run_command", "run_private_command"),
    "command_line": ("build_parser", "main"),
    # The facade is listed by the surface it must keep, not by what it contains: these are the
    # names that outlive any future move, because integrations and tests bind to them.
    "runtime": ("main", "build_parser", "approve", "pipeline_file", "doctor", "os"),
}


class BoundaryImportTest(unittest.TestCase):
    def test_boundary_modules_import_and_expose_contract_symbols(self) -> None:
        for module_name, symbols in BOUNDARY_SYMBOLS.items():
            with self.subTest(module=module_name):
                module = importlib.import_module(module_name)
                for symbol in symbols:
                    self.assertTrue(
                        hasattr(module, symbol),
                        f"{module_name} must expose {symbol}",
                    )


if __name__ == "__main__":
    unittest.main()
