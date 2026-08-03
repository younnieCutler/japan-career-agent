import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml

import pipeline


class PipelineCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "data" / "pipeline.yml"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_cli(self, *args: str) -> str:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(pipeline.main(["--path", str(self.path), *args]), 0)
        return out.getvalue()

    def load(self) -> dict:
        return yaml.safe_load(self.path.read_text(encoding="utf-8"))

    def run_cli_failing(self, *args: str) -> int:
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = pipeline.main(["--path", str(self.path), *args])
        self.last_error = err.getvalue()
        return code

    def test_upsert_update_history_and_close_share_one_store(self) -> None:
        self.run_cli("upsert", "gao", "--json", json.dumps({"name": "GAO", "stage": 4}))
        self.run_cli("update", "gao", "--json",
                     json.dumps({"stage": 2, "match_model_version": "evidence_based_v3",
                                 "decision_status": "review"}),
                     "--history", "scored")
        self.run_cli("history", "gao", "--event", "interview prep")
        self.run_cli("close", "gao", "--reason", "内定辞退", "--reached-stage", "4")
        company = self.load()["companies"][0]
        self.assertEqual(company["stage"], 4)
        self.assertEqual(company["decision_status"], "review")
        self.assertEqual(company["match_model_version"], "evidence_based_v3")
        self.assertTrue(company["closed"])
        self.assertEqual(company["closed_reason"], "内定辞退")
        self.assertEqual(len(company["history"]), 3)

    def test_legacy_match_score_is_preserved_but_never_rewritten(self) -> None:
        """Existing legacy_v1 values survive; the CLI refuses to write a new one."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump({"companies": [{"slug": "old", "name": "Old", "match_score": 78,
                                           "predicted_tier": "B", "closed": False, "history": []}]},
                           allow_unicode=True, sort_keys=False),
            encoding="utf-8")
        self.run_cli("update", "old", "--json", json.dumps({"decision_status": "conflict"}))
        company = self.load()["companies"][0]
        self.assertEqual(company["match_score"], 78, "legacy history must not be destroyed")
        self.assertEqual(company["predicted_tier"], "B")
        self.assertEqual(company["decision_status"], "conflict")

        self.assertEqual(self.run_cli_failing("update", "old", "--json", json.dumps({"match_score": 90})), 2)
        self.assertIn("legacy_v1", self.last_error)
        self.assertEqual(self.load()["companies"][0]["match_score"], 78)

    def test_interest_level_range_is_enforced(self) -> None:
        self.run_cli("upsert", "gao", "--json", json.dumps({"name": "GAO"}))
        self.run_cli("update", "gao", "--json", json.dumps({"interest_level": 5,
                                                            "interest_reason": "説明会で印象が変わった"}))
        self.assertEqual(self.load()["companies"][0]["interest_level"], 5)
        self.assertEqual(self.run_cli_failing("update", "gao", "--json", json.dumps({"interest_level": 6})), 2)
        self.assertEqual(self.run_cli_failing("update", "gao", "--json",
                                              json.dumps({"decision_status": "proceed_maybe"})), 2)

    def test_interest_history_is_appended_on_change(self) -> None:
        self.run_cli("upsert", "gao", "--json", json.dumps({"name": "GAO", "interest_level": 2,
                                                             "interest_reason": "まだ微妙"}))
        self.run_cli("update", "gao", "--json", json.dumps({"interest_level": 5,
                                                             "interest_reason": "説明会で印象が変わった"}))
        company = self.load()["companies"][0]
        self.assertEqual(company["interest_level"], 5)
        self.assertEqual(company["interest_reason"], "説明会で印象が変わった")
        self.assertEqual(len(company["interest_history"]), 1)
        snapshot = company["interest_history"][0]
        self.assertEqual(snapshot["interest_level"], 2)
        self.assertEqual(snapshot["interest_reason"], "まだ微妙")
        self.assertIn("changed_at", snapshot)

    def test_interest_history_unaffected_by_json_field_order(self) -> None:
        """Field order in JSON payload must not pollute the snapshot with new values."""
        self.run_cli("upsert", "gao", "--json", json.dumps({"name": "GAO", "interest_level": 2,
                                                             "interest_reason": "old_reason"}))
        # Note: interest_reason comes BEFORE interest_level in JSON string
        payload = '{"interest_reason":"new_reason","interest_level":5}'
        self.run_cli("update", "gao", "--json", payload)
        company = self.load()["companies"][0]
        self.assertEqual(company["interest_level"], 5)
        self.assertEqual(company["interest_reason"], "new_reason")
        self.assertEqual(len(company["interest_history"]), 1)
        snapshot = company["interest_history"][0]
        self.assertEqual(snapshot["interest_level"], 2)
        self.assertEqual(snapshot["interest_reason"], "old_reason")


if __name__ == "__main__":

    unittest.main()
