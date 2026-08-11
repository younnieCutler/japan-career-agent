"""GUI contract tests for the semantic-state 棚卸し vertical slice."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

from gui import tanaoroshi  # noqa: E402
from gui.templates import static_asset  # noqa: E402
from vault import CareerVault, initialize_vault  # noqa: E402


class TanaoroshiGuiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.tempdir.name) / "vault"
        initialize_vault(self.vault_path)
        self.home = CareerVault(self.vault_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_adapter_exposes_semantic_state_and_explicit_unknowns(self) -> None:
        payload = tanaoroshi.start(self.home)

        self.assertEqual(payload["session"]["workflow"], "tanaoroshi")
        self.assertEqual(payload["session"]["stage"], "experience_evidence")
        self.assertIn("individual_contribution", payload["missing_fields"])
        self.assertNotIn("page", payload["session"])

    def test_form_contract_uses_debounced_draft_and_explicit_non_work_flag(self) -> None:
        script = static_asset("bootstrap.js").decode("utf-8")

        self.assertIn("/api/draft", script)
        self.assertIn("800", script)
        self.assertIn("non_work", script)
        self.assertIn("experience_evidence", script)
        self.assertNotIn("window.fetch('/api/approve'", script)

    def test_incomplete_browser_controls_are_saved_as_unknown(self) -> None:
        created = tanaoroshi.start(self.home)
        result = tanaoroshi.autosave(
            self.home,
            created["session"]["session_id"],
            {
                "summary": "",
                "role": "",
                "individual_contribution": "",
                "direct_actions": [],
                "metrics": [],
                "evidence": [],
                "non_work": False,
                "confidentiality": {"contains_confidential": False, "external_use": "unknown"},
            },
        )
        self.assertIn("individual_contribution", result["missing_fields"])


if __name__ == "__main__":
    unittest.main()
