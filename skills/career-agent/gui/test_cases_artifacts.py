"""Contract tests for durable GUI cases and artifact metadata."""

from __future__ import annotations

import json
import http.client
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

import artifact_store  # noqa: E402
from gui import artifacts, cases  # noqa: E402
from gui.server import create_server  # noqa: E402
from gui.templates import static_asset  # noqa: E402
from persistence import read_jsonl  # noqa: E402
from vault import CareerVault, initialize_vault  # noqa: E402
from models import CareerError  # noqa: E402


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

        with self.assertRaisesRegex(Exception, "archive active child"):
            cases.archive_case(self.home, company["case_id"])
        self.assertEqual(cases.archive_case(self.home, application["case_id"])["status"], "archived")
        self.assertEqual(cases.archive_case(self.home, company["case_id"])["status"], "archived")
        self.assertEqual(cases.delete_case(self.home, application["case_id"])["status"], "deleted")
        self.assertEqual(before, self._canonical_bytes())
        self.assertFalse(self.home.events.exists())

    def test_an_artifact_body_can_be_opened_and_a_hand_edit_is_reported(self) -> None:
        """Grouping documents by case is only useful if one of them can be read.

        A metadata list tells the user a 職務経歴書 exists; it does not let them look at it.
        """
        company = cases.create_company(self.home, "Acme", pipeline_slug="acme")
        artifact = artifacts.register_artifact(
            self.home, case_ref=company["case_id"], kind="company_research", body="調査メモ",
        )

        opened = artifacts.artifact_body(self.home, artifact["artifact_id"])
        self.assertEqual(opened["body"], "調査メモ")
        self.assertTrue(opened["matches_record"])

        (self.home.path / artifact["body_ref"]).write_text("손으로 고친 내용", encoding="utf-8")
        edited = artifacts.artifact_body(self.home, artifact["artifact_id"])
        self.assertEqual(edited["body"], "손으로 고친 내용")
        self.assertFalse(edited["matches_record"])

        self.assertIsNone(artifacts.artifact_body(self.home, "art-" + "0" * 16))

    def test_archived_application_rejects_new_research_without_losing_existing_work(self) -> None:
        company = cases.create_company(self.home, "Acme")
        application = cases.create_application(self.home, company["case_id"], "Backend")
        existing = artifacts.register_artifact(
            self.home,
            case_ref=application["case_id"],
            kind="company_research",
            body="Existing research",
        )
        cases.archive_case(
            self.home,
            application["case_id"],
            expected_updated_at=application["updated_at"],
        )

        with self.assertRaises(CareerError) as inactive:
            artifacts.register_artifact(
                self.home,
                case_ref=application["case_id"],
                kind="company_research",
                body="New research",
            )

        self.assertEqual(inactive.exception.code, "INVALID_RELATIONSHIP")
        self.assertEqual(artifacts.artifact_body(self.home, existing["artifact_id"])["body"], "Existing research")

    def test_a_crash_mid_update_never_leaves_a_kind_without_a_current_artifact(self) -> None:
        """Each file write is atomic; the transition across several files is not.

        Demoting the old version before the new one exists opens a window where a kill leaves the
        case with no current artifact at all — the user's document gone from the screen while both
        the old body and the old metadata are still on disk.
        """
        company = cases.create_company(self.home, "Acme", pipeline_slug="acme")
        application = cases.create_application(self.home, company["case_id"], "Backend")
        first = artifacts.register_artifact(
            self.home, case_ref=application["case_id"], kind="interview_script", body="v1 body",
        )

        with patch.object(artifact_store, "_write_body", side_effect=OSError("killed")):
            with self.assertRaises(OSError):
                artifacts.update_artifact(self.home, first["artifact_id"], body="v2 body")

        current = [
            item
            for item in artifacts.list_artifacts(self.home, case_ref=application["case_id"])
            if item["status"] == "current"
        ]
        self.assertEqual([item["artifact_id"] for item in current], [first["artifact_id"]])
        self.assertEqual(artifacts.get_artifact(self.home, first["artifact_id"])["status"], "current")

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
        script = static_asset("screens.js").decode("utf-8")
        self.assertIn("/api/career", script)
        self.assertIn("/api/applications", script)
        self.assertIn("/api/applications/documents", script)
        self.assertIn("/api/artifact-body?artifact_ref=", script)
        self.assertIn("career.new_experience_confirm", script)
        self.assertIn("action.archive", script)
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
            company = json.loads(response.read())
            self.assertEqual(company["label"], "Protected")

            connection.request(
                "POST",
                "/api/applications/positions",
                body=json.dumps({
                    "company_ref": company["ref"],
                    "label": "Backend",
                    "evidence_refs": ["claim-confirmed"],
                }),
                headers={
                    "Cookie": cookie,
                    "Content-Type": "application/json",
                    "X-CSRF-Token": session["csrf_token"],
                },
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            application = json.loads(response.read())

            connection.request(
                "POST",
                "/api/applications/documents",
                body=json.dumps({
                    "case_ref": application["ref"],
                    "document_type": "resume",
                    "body": "Reviewed application draft",
                }),
                headers={
                    "Cookie": cookie,
                    "Content-Type": "application/json",
                    "X-CSRF-Token": session["csrf_token"],
                },
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertTrue(json.loads(response.read())["saved"])
            document = artifacts.list_artifacts(self.home, case_ref=application["ref"])[0]
            self.assertEqual(document["evidence_refs"], ["claim-confirmed"])

            connection.request(
                "GET",
                "/api/artifact-body?artifact_ref=" + document["artifact_id"],
                headers={"Cookie": cookie},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())["body"], "Reviewed application draft")
            connection.close()
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
