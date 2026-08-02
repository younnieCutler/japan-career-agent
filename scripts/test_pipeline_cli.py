import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
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

    def test_upsert_update_history_and_close_share_one_store(self) -> None:
        self.run_cli("upsert", "gao", "--json", json.dumps({"name": "GAO", "stage": 4}))
        self.run_cli("update", "gao", "--json", json.dumps({"stage": 2, "match_score": 78}), "--history", "scored")
        self.run_cli("history", "gao", "--event", "interview prep")
        self.run_cli("close", "gao", "--reason", "内定辞退", "--reached-stage", "4")
        company = self.load()["companies"][0]
        self.assertEqual(company["stage"], 4)
        self.assertEqual(company["match_score"], 78)
        self.assertTrue(company["closed"])
        self.assertEqual(company["closed_reason"], "内定辞退")
        self.assertEqual(len(company["history"]), 3)


if __name__ == "__main__":
    unittest.main()
