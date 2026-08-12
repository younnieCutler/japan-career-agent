"""GUI contract tests for the semantic-state 棚卸し vertical slice."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

from gui import tanaoroshi  # noqa: E402
from gui.templates import render_shell, static_asset  # noqa: E402
from vault import CareerVault, initialize_vault  # noqa: E402


class TanaoroshiGuiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.tempdir.name) / "vault"
        initialize_vault(self.vault_path)
        self.home = CareerVault(self.vault_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_every_api_path_the_client_calls_is_served(self) -> None:
        """A route the client calls but the server does not answer is a 404 only a browser sees.

        The same shape as the CSP gap: each side is self-consistent, and nothing compares them.
        """
        script = static_asset("bootstrap.js").decode("utf-8")
        called = set(re.findall(r'["\'`](/api/[a-z/-]+)', script))
        source = Path(__file__).with_name("server.py").read_text(encoding="utf-8")
        served = set(re.findall(r'"(/api/[a-z/-]+)"', source))

        self.assertIn("/api/sessions", called)
        self.assertEqual(called - served, set())

    def test_the_screen_is_written_in_the_language_the_shell_declares(self) -> None:
        """The shell sends `<html lang="ko">`, so its sentences have to be Korean.

        The 棚卸し screen had a Japanese heading and lede sitting above Korean field labels. A
        screen reader announces the whole document with the declared language, so it read those
        two lines as Korean; a reader who does not know Japanese simply could not use them.

        The product's own terms are removed first and whatever kana is left is a sentence. That
        order matters: 棚卸し carries a し, so testing for kana alone would flag the term this
        product is named after, which the Korean README prints as it is.
        """
        shell = render_shell()
        script = static_asset("bootstrap.js").decode("utf-8")
        kana = re.compile(r"[぀-ゟ゠-ヿ]")
        offenders = []
        for line in script.splitlines():
            without_terms = line
            for term in ("棚卸し", "職務経歴書", "履歴書", "自己PR"):
                without_terms = without_terms.replace(term, "")
            if kana.search(without_terms):
                offenders.append(line.strip())

        self.assertIn('lang="ko"', shell)
        self.assertEqual(offenders, [], "Japanese sentences in a ko-declared screen")

    def test_resuming_does_not_depend_on_client_side_memory(self) -> None:
        script = static_asset("bootstrap.js").decode("utf-8")
        self.assertNotIn("localStorage.getItem", script)
        self.assertNotIn("localStorage.setItem", script)

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
