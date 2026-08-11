"""Contract tests for durable GUI cases and artifact metadata."""

from __future__ import annotations

import json
import http.client
import sys
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

from gui import artifacts, cases  # noqa: E402
from gui.server import create_server  # noqa: E402
from gui.templates import static_asset  # noqa: E402
from persistence import read_jsonl  # noqa: E402
from vault import CareerVault, initialize_vault  # noqa: E402


class CaseArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.tempdir.name) / "vault"
        initialize_vault(self.vault_path)
        self.home = CareerVault(self.vault_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _canonical_bytes(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.home.path).as_posix(): path.read_bytes()
            for path in self.home.state_dir.iterdir()
            if path.is_file()
        }

    def test_cases_are_durable_and_archive_delete_do_not_touch_canonical_evidence(self) -> None:
        before = self._canonical_bytes()
        company = cases.create_company(self.home, "Acme", pipeline_slug="acme")
        application = cases.create_application(
            self.home,
            company["case_id"],
            "Backend Engineer",
            jd={"source": "user-pasted", "requirements": ["Python"]},
        )

        self.assertEqual(company["kind"], "company")
        self.assertEqual(application["kind"], "application")
        self.assertEqual(application["parent_ref"], company["case_id"])
        relative_case_path = cases.case_path(self.home, company["case_id"]).relative_to(self.home.path)
        self.assertEqual(
            relative_case_path.as_posix(),
            "03-active/gui/cases/" + company["case_id"] + ".json",
        )
        self.assertNotIn("01-capture", str(cases.case_path(self.home, company["case_id"])))
        self.assertNotIn("02-state", str(cases.case_path(self.home, company["case_id"])))

        self.assertEqual(cases.archive_case(self.home, company["case_id"])["status"], "archived")
        self.assertEqual(cases.delete_case(self.home, application["case_id"])["status"], "deleted")
        self.assertEqual(before, self._canonical_bytes())
        self.assertFalse(self.home.events.exists())

    def test_application_artifacts_are_scoped_to_their_application_case(self) -> None:
        company = cases.create_company(self.home, "Acme", pipeline_slug="acme")
        application_a = cases.create_application(self.home, company["case_id"], "Backend A")
        application_b = cases.create_application(self.home, company["case_id"], "Backend B")
        artifact_a = artifacts.register_artifact(
            self.home,
            case_ref=application_a["case_id"],
            kind="interview_script",
            body="A only",
            evidence_refs=["evt-a"],
        )
        artifacts.register_artifact(
            self.home,
            case_ref=application_b["case_id"],
            kind="interview_script",
            body="B only",
            evidence_refs=["evt-b"],
        )

        visible_to_a = artifacts.list_artifacts(self.home, case_ref=application_a["case_id"])
        self.assertEqual([item["artifact_id"] for item in visible_to_a], [artifact_a["artifact_id"]])
        self.assertEqual(visible_to_a[0]["evidence_refs"], ["evt-a"])
        self.assertNotIn("B only", json.dumps(visible_to_a, ensure_ascii=False))

    def test_artifact_versions_use_digest_names_and_never_overwrite_prior_body(self) -> None:
        company = cases.create_company(self.home, "Acme", pipeline_slug="acme")
        application = cases.create_application(self.home, company["case_id"], "Backend")
        first = artifacts.register_artifact(
            self.home,
            case_ref=application["case_id"],
            kind="company_research",
            body="first version",
        )
        second = artifacts.update_artifact(self.home, first["artifact_id"], body="second version")

        first_body = self.home.path / first["body_ref"]
        second_body = self.home.path / second["body_ref"]
        self.assertNotEqual(first["body_ref"], second["body_ref"])
        self.assertIn("company_research-", Path(first["body_ref"]).name)
        self.assertEqual(first_body.read_text(encoding="utf-8"), "first version")
        self.assertEqual(second_body.read_text(encoding="utf-8"), "second version")
        self.assertEqual(first["version"], 1)
        self.assertEqual(second["version"], 2)
        self.assertEqual(artifacts.get_artifact(self.home, first["artifact_id"])["status"], "superseded")

    def test_artifact_delete_preserves_evidence_refs_and_cli_source_metadata(self) -> None:
        company = cases.create_company(self.home, "Acme", pipeline_slug="acme")
        artifact = artifacts.register_artifact(
            self.home,
            case_ref=company["case_id"],
            kind="company_research",
            body="CLI result",
            evidence_refs=["evt-1"],
            source_refs=["official:acme.example"],
            generated_by={"entrypoint": "cli", "workflow": "company_research"},
        )
        before_events = read_jsonl(self.home.events)

        deleted = artifacts.delete_artifact(self.home, artifact["artifact_id"])

        self.assertEqual(deleted["status"], "deleted")
        self.assertEqual(deleted["evidence_refs"], ["evt-1"])
        self.assertEqual(deleted["source_refs"], ["official:acme.example"])
        self.assertEqual(deleted["generated_by"], {"entrypoint": "cli", "workflow": "company_research"})
        self.assertEqual(read_jsonl(self.home.events), before_events)
        self.assertTrue((self.home.path / artifact["body_ref"]).exists())

    def test_browser_case_screen_uses_get_read_and_csrf_protected_writes(self) -> None:
        script = static_asset("bootstrap.js").decode("utf-8")
        self.assertIn("/api/cases", script)
        self.assertIn("/api/artifacts", script)
        self.assertIn("Archive case", script)
        self.assertIn("textContent", script)
        self.assertNotIn("innerHTML", script)

        try:
            server = create_server(port=0, home=self.home)
        except PermissionError as exc:
            raise unittest.SkipTest(f"loopback bind unavailable in this execution sandbox: {exc}") from exc
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
            connection.request(
                "POST",
                "/session",
                body=json.dumps({"token": server.bootstrap_token}),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            cookie = response.getheader("Set-Cookie")
            session = json.loads(response.read())

            connection.request("GET", "/api/cases", headers={"Cookie": cookie})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())["mode"], "cases")

            connection.request(
                "POST",
                "/api/cases",
                body=json.dumps({"kind": "company", "label": "No CSRF"}),
                headers={"Cookie": cookie, "Content-Type": "application/json"},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()

            connection.request(
                "POST",
                "/api/cases",
                body=json.dumps({"kind": "company", "label": "Protected"}),
                headers={
                    "Cookie": cookie,
                    "Content-Type": "application/json",
                    "X-CSRF-Token": session["csrf_token"],
                },
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())["label"], "Protected")
            connection.close()
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
