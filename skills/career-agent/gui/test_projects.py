"""Contract tests for the read-only Projects / 재직 중 GUI slice."""

from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from unittest.mock import patch


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

import persistence  # noqa: E402
import sessions  # noqa: E402
from gui import artifacts, cases, tanaoroshi  # noqa: E402
from models import CareerError  # noqa: E402
from vault import CareerVault, initialize_vault  # noqa: E402


def _sample_reads() -> dict:
    return {
        "status": {
            "profile": {
                "career_status": "active",
                "employment_status": "employed",
                "job_search": "off",
                "target_role": "LLMOps Engineer",
            }
        },
        "projects": {
            "projects": [{
                "id": "prj-1",
                "title": "Migration",
                "status": "active",
                "role": "owner",
                "scope": "payment batch",
                "summary": "Runbook and alert redesign",
                "period": {"from": "2025-01", "to": None},
                "confirmed_work_events": 2,
            }]
        },
        "timeline": {
            "timeline": [{
                "event_id": "evt-1",
                "title": "Runbook",
                "date": "2025-02",
                "dated": True,
            }]
        },
    }


class ProjectsPayloadTests(unittest.TestCase):
    def test_projects_payload_reuses_read_models_and_preserves_declared_employment(self) -> None:
        views = import_module("gui.views_read")
        reads = _sample_reads()
        home = object()
        with (
            patch.object(views, "status", return_value=reads["status"]) as status,
            patch.object(views, "list_projects", return_value=reads["projects"]) as projects,
            patch.object(views, "show_project_timeline", return_value=reads["timeline"]) as timeline,
        ):
            result = views.projects_payload(home)

        status.assert_called_once()
        projects.assert_called_once()
        timeline.assert_called_once_with(home, "prj-1")
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertEqual(result["mode"], "projects")
        self.assertEqual(result["employment"]["employment_status"], "employed")
        self.assertEqual(result["employment"]["target_role"], "LLMOps Engineer")
        self.assertEqual(result["projects"][0]["title"], "Migration")
        self.assertEqual(result["projects"][0]["timeline"][0]["title"], "Runbook")
        self.assertNotIn("prj-1", encoded)
        self.assertNotIn("evt-1", encoded)
        self.assertNotIn("percentage", encoded.casefold())
        self.assertNotIn("recommend", encoded.casefold())
        self.assertTrue(result["read_only"])
        self.assertTrue(result["no_total_by_design"])

    def test_projects_payload_does_not_write_an_empty_vault(self) -> None:
        from vault import CareerVault, initialize_vault

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "vault"
            initialize_vault(root)
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            result = import_module("gui.views_read").projects_payload(CareerVault(root))
            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

        self.assertEqual(before, after)
        self.assertEqual(result["projects"], [])
        self.assertEqual(result["employment"]["employment_status"], "unknown")


@contextmanager
def running_server():
    server_module = import_module("gui.server")
    try:
        server = server_module.create_server(port=0, home=object())
    except PermissionError as exc:
        raise unittest.SkipTest(f"loopback bind unavailable in this execution sandbox: {exc}") from exc
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def request(server, method: str, path: str, *, headers: dict[str, str] | None = None, body: str | None = None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    payload = response.read()
    result = response.status, dict(response.getheaders()), payload
    connection.close()
    return result


class ProjectCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.tempdir.name) / "vault"
        initialize_vault(self.vault_path)
        self.home = CareerVault(self.vault_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _project(self, label: str, **kwargs):
        context = cases.create_career_context(
            self.home,
            "Acme employment",
            context_kind="company",
            relationship="employer",
        )
        return context, cases.create_project(self.home, context["case_id"], label, **kwargs)

    def _approve_case(self, record: dict) -> dict:
        proposed = cases.propose_canonical_case(self.home, record["case_id"])
        return cases.approve_canonical_case(
            self.home,
            record["case_id"],
            proposed["proposal"]["id"],
        )["case"]

    def test_a_project_case_holds_notes_and_documents_without_touching_the_ledger(self) -> None:
        """A project someone is living through is not yet career evidence.

        Retrospectives and drafts belong beside the project while it runs; only approval turns any
        of it into a confirmed fact, so writing them must leave the canonical ledger alone.
        """
        before = {
            path.name: path.read_bytes() for path in self.home.state_dir.iterdir() if path.is_file()
        }
        context, project = self._project(
            "Payment Platform Migration", project_id="proj-payments",
        )
        retrospective = artifacts.register_artifact(
            self.home, case_ref=project["case_id"], kind="project_review", body="회고 초안",
        )

        self.assertEqual(project["kind"], "project")
        self.assertEqual(project["parent_ref"], context["case_id"])
        self.assertEqual(project["metadata"]["project_id"], "proj-payments")
        self.assertEqual(
            [item["artifact_id"] for item in artifacts.list_artifacts(self.home, case_ref=project["case_id"])],
            [retrospective["artifact_id"]],
        )
        self.assertEqual(
            before,
            {path.name: path.read_bytes() for path in self.home.state_dir.iterdir() if path.is_file()},
        )
        self.assertFalse(self.home.events.exists())

    def test_a_project_case_is_isolated_from_application_cases(self) -> None:
        _, project = self._project("Payment Platform Migration")
        company = cases.create_company(self.home, "Acme", pipeline_slug="acme")
        application = cases.create_application(self.home, company["case_id"], "Backend")
        artifacts.register_artifact(
            self.home, case_ref=project["case_id"], kind="project_review", body="project only",
        )

        visible = artifacts.list_artifacts(self.home, case_ref=application["case_id"])

        self.assertEqual(visible, [])
        self.assertEqual([item["case_id"] for item in cases.list_cases(self.home, kind="project")],
                         [project["case_id"]])

    def test_a_finished_project_reaches_canonical_evidence_only_through_approval(self) -> None:
        """Record now, approve later, reuse in an application years on — the whole point of this.

        The session carries the project's case_ref so the confirmed event can be traced back to
        the work it came from, and nothing reaches the ledger until the user approves it.
        """
        context, project = self._project("Payment Platform Migration")
        self._approve_case(context)
        project = self._approve_case(project)
        started = tanaoroshi.start(self.home, case_ref=project["case_id"])
        session_id = started["session"]["session_ref"]
        saved = tanaoroshi.autosave(
            self.home,
            session_id,
            {
                "summary": "결제 배치 지연을 줄였다",
                "evidence": ["runbook"],
                "role": "owner",
                "direct_actions": ["알람을 재설계했다"],
                "individual_contribution": "알람 기준과 운영 절차를 직접 설계했다",
                "outcome_state": "qualitative",
                "team_result": "결제 배치 대응이 안정됐다",
                "confidentiality": {
                    "contains_confidential": False,
                    "external_use": "allowed",
                },
            },
            expected_revision=0,
        )
        before_proposal = persistence.read_jsonl(self.home.events)
        proposal = tanaoroshi.submit(
            self.home, session_id, expected_revision=saved["revision"]
        )

        self.assertEqual(started["session"]["subject"]["context_label"], "Acme employment")
        self.assertEqual(
            started["session"]["subject"]["project_label"], "Payment Platform Migration"
        )
        self.assertEqual(persistence.read_jsonl(self.home.events), before_proposal)

        tanaoroshi.approve_session(
            self.home,
            session_id,
            proposal["proposal"]["id"],
            expected_revision=proposal["revision"],
        )
        events = persistence.read_jsonl(self.home.events)

        self.assertEqual(len(events), len(before_proposal) + 1)
        self.assertEqual(events[-1]["summary"], "결제 배치 지연을 줄였다")
        self.assertEqual(
            sessions.load_session(self.home, session_id)["case_ref"], project["case_id"]
        )

    def test_the_project_screen_records_through_the_case_and_session_routes(self) -> None:
        script = (RUNTIME_ROOT / "gui" / "static" / "screens.js").read_text(encoding="utf-8")
        renderer = script.split("function createProjectForm", 1)[1].split("function experienceRow", 1)[0]

        self.assertIn("/api/career/projects", renderer)
        self.assertNotIn("external_use", renderer)
        self.assertIn('name: "current"', renderer)
        self.assertIn("date.end_help", renderer)
        self.assertNotIn("/api/workflows/approve", renderer)

    def test_career_history_opens_confirmed_experience_detail_and_recovers_drafts(self) -> None:
        script = (RUNTIME_ROOT / "gui" / "static" / "screens.js").read_text(encoding="utf-8")
        experience = script.split("function experienceRow", 1)[1].split("function projectTree", 1)[0]

        self.assertIn('el("details", { className: "experience-detail" })', experience)
        self.assertIn("experience.detail", experience)
        self.assertIn("evidence.missing_usable", experience)
        self.assertIn("/api/cases/", script)
        self.assertIn("case.archive_confirm", script)
        self.assertIn("success.context_approved_next", script)

    def test_the_client_reads_the_case_shape_the_server_actually_returns(self) -> None:
        """`/api/cases` returns the case flat, not wrapped.

        Reading `created.case.case_id` from a flat body yields undefined and the chained request
        fails in the browser only — every Python test here calls the adapter directly and never
        sees the response shape the client parses.
        """
        script = (RUNTIME_ROOT / "gui" / "static" / "screens.js").read_text(encoding="utf-8")

        self.assertNotIn(".case.case_id", script)
        self.assertIn("organized.ref", script)
        self.assertIn("result.session", script)

    def test_a_project_cannot_be_parented_and_keeps_its_own_kind(self) -> None:
        company = cases.create_company(self.home, "Acme", pipeline_slug="acme")
        with self.assertRaises(CareerError):
            cases.create_project(self.home, company["case_id"], "Wrongly parented")


class ProjectsRouteTests(unittest.TestCase):
    def test_authenticated_projects_route_is_get_only(self) -> None:
        server_module = import_module("gui.server")
        with patch.object(server_module, "projects_payload", return_value={"mode": "projects"}):
            with running_server() as server:
                status, headers, _ = request(
                    server,
                    "POST",
                    "/session",
                    headers={"Content-Type": "application/json"},
                    body=json.dumps({"token": server.bootstrap_token}),
                )
                self.assertEqual(status, 200)
                cookie = headers["Set-Cookie"]
                read = request(server, "GET", "/api/projects", headers={"Cookie": cookie})
                self.assertEqual(read[0], 200)
                self.assertEqual(json.loads(read[2]), {"mode": "projects"})
                post = request(server, "POST", "/api/projects", headers={"Cookie": cookie}, body="{}")
                self.assertEqual(post[0], 405)
                self.assertEqual(post[1]["Allow"], "GET")

    def test_browser_contract_exposes_projects_and_employment_without_html_injection(self) -> None:
        script = import_module("gui.templates").static_asset("screens.js").decode("utf-8")
        self.assertIn("/api/career", script)
        self.assertIn("careerScreen", script)
        self.assertIn("context_kind.company", script)
        self.assertIn("textContent", script)
        self.assertNotIn("innerHTML", script)


if __name__ == "__main__":
    unittest.main()
