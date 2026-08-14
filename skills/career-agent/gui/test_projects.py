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
from gui._test_client import FRONTEND_SRC, client_source  # noqa: E402
from gui import artifacts, cases, tanaoroshi  # noqa: E402
from gui.views_read import applications_payload  # noqa: E402
from experiences import list_experiences  # noqa: E402
from models import CareerError  # noqa: E402
from projection import contexts_from_events, projects_from_events  # noqa: E402
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
    def test_canonical_updates_distinguish_explicit_clear_from_missing_fields(self) -> None:
        context_events = [
            {
                "type": "experience_context", "status": "confirmed", "occurred_at": "2025-01-01T00:00:00Z",
                "experience_context": {
                    "id": "ctx-acme", "kind": "company", "label": "Acme", "role": "Engineer",
                    "summary": "Platform", "period": {"from": "2023-01", "to": "2025-01", "current": False},
                },
            },
            {
                "type": "experience_context", "status": "confirmed", "occurred_at": "2025-02-01T00:00:00Z",
                "experience_context": {
                    "id": "ctx-acme", "kind": "company", "label": "Acme", "role": None,
                    "period": {"to": None, "current": True},
                },
            },
        ]
        project_events = [
            {
                "type": "project", "status": "confirmed", "occurred_at": "2025-01-01T00:00:00Z",
                "project": {
                    "id": "prj-acme", "title": "Migration", "scope": "Payments",
                    "period": {"from": "2023-01", "to": "2025-01", "current": False},
                },
            },
            {
                "type": "project", "status": "confirmed", "occurred_at": "2025-02-01T00:00:00Z",
                "project": {
                    "id": "prj-acme", "title": "Migration", "scope": None,
                    "period": {"to": None, "current": True},
                },
            },
        ]

        context = contexts_from_events(context_events)["ctx-acme"]
        project = projects_from_events(project_events)["prj-acme"]

        self.assertNotIn("role", context)
        self.assertEqual(context["summary"], "Platform")
        self.assertEqual(context["period"], {"from": "2023-01", "current": True})
        self.assertNotIn("scope", project)
        self.assertEqual(project["period"], {"from": "2023-01", "current": True})

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
def running_server(home=None):
    server_module = import_module("gui.server")
    try:
        server = server_module.create_server(port=0, home=home or object())
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
        context = self._approve_case(context)
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
        context, project = self._project(
            "Payment Platform Migration", project_id="proj-payments",
        )
        before = {
            path.name: path.read_bytes() for path in self.home.state_dir.iterdir() if path.is_file()
        }
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
        self.assertTrue(self.home.events.exists())

    def test_a_project_case_is_isolated_from_application_cases(self) -> None:
        context, project = self._project("Payment Platform Migration")
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

    def test_revising_experience_appends_a_replacement_and_supersession(self) -> None:
        context, project = self._project("Payment Platform Migration")
        project = self._approve_case(project)
        started = tanaoroshi.start(self.home, case_ref=project["case_id"])
        saved = tanaoroshi.autosave(
            self.home,
            started["session"]["session_ref"],
            {
                "summary": "결제 배치 지연을 줄였다",
                "evidence": ["runbook"],
                "role": "owner",
                "direct_actions": ["알람을 재설계했다"],
                "individual_contribution": "알람 기준을 직접 설계했다",
                "outcome_state": "qualitative",
                "confidentiality": {"contains_confidential": False, "external_use": "allowed"},
            },
            expected_revision=0,
        )
        proposed = tanaoroshi.submit(
            self.home, started["session"]["session_ref"], expected_revision=saved["revision"]
        )
        tanaoroshi.approve_session(
            self.home,
            started["session"]["session_ref"],
            proposed["proposal"]["id"],
            expected_revision=proposed["revision"],
        )
        original = persistence.read_jsonl(self.home.events)[-1]
        current_context = list_experiences(self.home)["contexts"][context["metadata"]["context_id"]]
        with self.assertRaises(CareerError) as incompatible_context:
            cases.propose_career_context_update(
                self.home,
                context["case_id"],
                context["metadata"]["context_id"],
                expected_revision=current_context["updated_at"],
                label="Acme University",
                context_kind="university",
                relationship="non_work",
            )
        self.assertEqual(incompatible_context.exception.code, "INVALID_RELATIONSHIP")
        company = cases.create_company(self.home, "Acme")
        application = cases.create_application(
            self.home, company["case_id"], "Backend", evidence_refs=[original["id"]],
        )
        document = artifacts.register_artifact(
            self.home,
            case_ref=application["case_id"],
            kind="resume",
            body="Original submitted wording",
            evidence_refs=[original["id"]],
        )

        revised = tanaoroshi.revise(
            self.home, original["id"], expected_revision=original["id"]
        )

        self.assertEqual(revised["draft"]["summary"], original["summary"])
        changed = tanaoroshi.autosave(
            self.home,
            revised["session"]["session_ref"],
            {**revised["draft"], "summary": "결제 배치 지연 원인을 바로잡았다"},
            expected_revision=revised["revision"],
        )
        review = tanaoroshi.submit(
            self.home, revised["session"]["session_ref"], expected_revision=changed["revision"]
        )
        self.assertEqual(review["review_before"]["summary"], original["summary"])
        tanaoroshi.approve_session(
            self.home,
            revised["session"]["session_ref"],
            review["proposal"]["id"],
            expected_revision=review["revision"],
        )

        events = persistence.read_jsonl(self.home.events)
        self.assertEqual(events[-3], original)
        self.assertEqual(events[-2]["summary"], "결제 배치 지연 원인을 바로잡았다")
        self.assertEqual(events[-1]["type"], "experience_supersession")
        self.assertEqual(
            events[-1]["supersession"],
            {"predecessor_event_id": original["id"], "replacement_event_id": events[-2]["id"]},
        )
        self.assertEqual(
            [row["claim_id"] for row in list_experiences(self.home)["claims"]], [events[-2]["id"]]
        )
        position = applications_payload(self.home)["companies"][0]["positions"][0]
        self.assertEqual(position["ref"], application["case_id"])
        self.assertEqual(position["stale_evidence"], [{
            "ref": original["id"], "replacement_ref": events[-2]["id"],
        }])
        with self.assertRaises(CareerError) as stale_application:
            cases.update_application(
                self.home,
                application["case_id"],
                label="Backend",
                expected_revision=application["updated_at"],
                evidence_refs=[original["id"]],
            )
        self.assertEqual(stale_application.exception.code, "INVALID_RELATIONSHIP")
        updated = cases.update_application(
            self.home,
            application["case_id"],
            label="Backend",
            expected_revision=application["updated_at"],
            evidence_refs=[events[-2]["id"]],
        )
        self.assertEqual(updated["metadata"]["evidence_refs"], [events[-2]["id"]])
        self.assertEqual(artifacts.get_artifact(self.home, document["artifact_id"])["evidence_refs"], [original["id"]])
        with self.assertRaisesRegex(CareerError, "reload") as stale:
            tanaoroshi.revise(self.home, original["id"], expected_revision=original["id"])
        self.assertEqual(stale.exception.code, "REVISION_STALE")

    def test_new_work_uses_the_current_canonical_context_after_context_edit(self) -> None:
        context = cases.create_career_context(
            self.home, "Acme", context_kind="company", relationship="employer",
        )
        context = self._approve_case(context)
        project = cases.create_project(self.home, context["case_id"], "Migration")
        project = self._approve_case(project)
        current = list_experiences(self.home)["contexts"][context["metadata"]["context_id"]]
        reviewed = cases.propose_career_context_update(
            self.home,
            context["case_id"],
            context["metadata"]["context_id"],
            expected_revision=current["updated_at"],
            label="University Lab",
            context_kind="university",
            relationship="non_work",
        )
        cases.approve_canonical_case(
            self.home,
            context["case_id"],
            reviewed["proposal"]["id"],
            expected_revision=current["updated_at"],
        )

        subject = sessions.career_project_subject(self.home, project["case_id"])

        self.assertEqual(subject["context_label"], "University Lab")
        self.assertEqual(subject["context_kind"], "university")

    def test_the_project_screen_records_through_the_case_and_session_routes(self) -> None:
        forms = (FRONTEND_SRC / "screens" / "CareerForms.jsx").read_text(encoding="utf-8")
        renderer = forms.split("export function AddProject", 1)[1].split("\nexport function", 1)[0]

        self.assertIn("/api/career/projects", renderer)
        # Confidentiality belongs to an experience, not to the project that contains it.
        self.assertNotIn("external_use", renderer)
        self.assertIn("date.end_help", forms)
        self.assertIn("current", renderer)
        # Creating a project drafts it. Confirmation is a separate, explicit act.
        self.assertIn("action.create_draft", renderer)
        self.assertNotIn("/api/workflows/approve", renderer)

    def test_career_history_opens_confirmed_experience_detail_and_recovers_drafts(self) -> None:
        """A confirmed experience stays inspectable and stranded drafts stay recoverable.

        The disclosure widget this once asserted is gone: experiences are rows in the index and
        open in the record pane. What has to survive is the capability, not the widget.
        """
        client = client_source()

        # An experience opens as a record with its evidence state on it, rather than as a row
        # the user can only read the label of.
        self.assertIn("function ExperienceRecord", client)
        self.assertIn("evidence.missing_usable", client)
        self.assertIn("career.unassigned_work_title", client)
        self.assertIn("/api/workflows/assign-project", client)
        self.assertIn("/api/cases/", client)
        self.assertIn("case.archive_confirm", client)
        self.assertIn("/api/career/approve", client)

    def test_the_client_reads_the_case_shape_the_server_actually_returns(self) -> None:
        """`/api/cases` returns the case flat, not wrapped.

        Reading `created.case.case_id` from a flat body yields undefined and the chained request
        fails in the browser only — every Python test here calls the adapter directly and never
        sees the response shape the client parses.
        """
        client = client_source()

        self.assertNotIn(".case.case_id", client)
        self.assertIn("company.ref", client)
        self.assertIn("started.session", client)

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
        client = client_source()
        self.assertIn("/api/career", client)
        self.assertIn("export default function CareerScreen", client)
        self.assertIn("context_kind.company", client)
        # Vault data must never be able to become markup, in any module.
        self.assertNotIn("innerHTML", client)


class CareerMutationRouteTests(unittest.TestCase):
    """The browser updates existing canonical records through review, never direct writes."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.tempdir.name) / "vault"
        initialize_vault(self.vault_path)
        self.home = CareerVault(self.vault_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _session(self, server):
        status, headers, body = request(
            server,
            "POST",
            "/session",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"token": server.bootstrap_token}),
        )
        self.assertEqual(status, 200)
        return {
            "Cookie": headers["Set-Cookie"],
            "Content-Type": "application/json",
            "X-CSRF-Token": json.loads(body)["csrf_token"],
        }

    def _write(self, server, headers, path: str, payload: dict):
        status, _, body = request(server, "POST", path, headers=headers, body=json.dumps(payload))
        return status, json.loads(body)

    def _career(self, server, headers) -> dict:
        status, _, body = request(server, "GET", "/api/career", headers={"Cookie": headers["Cookie"]})
        self.assertEqual(status, 200)
        return json.loads(body)

    def _confirm(self, server, headers, record: dict) -> dict:
        status, review = self._write(server, headers, "/api/career/propose", {
            "case_ref": record["ref"], "revision": record["revision"],
        })
        self.assertEqual(status, 200)
        status, approved = self._write(server, headers, "/api/career/approve", {
            "case_ref": record["ref"],
            "proposal_ref": review["proposal"]["ref"],
            "revision": review["revision"],
        })
        self.assertEqual(status, 200)
        return approved

    def test_context_and_project_edits_are_proposed_approved_reloaded_and_cas_protected(self) -> None:
        with running_server(self.home) as server:
            headers = self._session(server)
            status, created_context = self._write(server, headers, "/api/career/contexts", {
                "label": "Acme", "context_kind": "company", "relationship": "employer",
                "role": "Engineer", "summary": "Platform", "period": {"from": "2024-01"},
            })
            self.assertEqual(status, 200)
            context = next(
                row for row in self._career(server, headers)["contexts"]
                if row["ref"] == created_context["ref"]
            )
            self._confirm(server, headers, context)
            context = next(row for row in self._career(server, headers)["contexts"] if row["ref"] == context["ref"])
            stale_context_revision = context["revision"]

            status, context_review = self._write(server, headers, "/api/career/contexts", {
                "case_ref": context["ref"], "context_id": context["context_id"],
                "revision": context["revision"], "label": "Acme Japan", "context_kind": "company",
                "relationship": "employer", "role": "Staff Engineer", "summary": "Platform",
                "period": {"from": "2024-01", "to": "2025-12"},
            })
            self.assertEqual(status, 200)
            self.assertEqual(context_review["before"]["label"], "Acme")
            self.assertEqual(context_review["proposal"]["event"]["experience_context"]["label"], "Acme Japan")
            self.assertEqual([event["experience_context"]["label"] for event in persistence.read_jsonl(self.home.events)], ["Acme"])
            status, _ = self._write(server, headers, "/api/career/approve", {
                "case_ref": context["ref"], "proposal_ref": context_review["proposal"]["ref"],
                "revision": context_review["revision"],
            })
            self.assertEqual(status, 200)
            context = next(row for row in self._career(server, headers)["contexts"] if row["ref"] == context["ref"])
            self.assertEqual((context["label"], context["role"]), ("Acme Japan", "Staff Engineer"))

            before_stale = {path.name: path.read_bytes() for path in self.home.state_dir.iterdir() if path.is_file()}
            status, stale = self._write(server, headers, "/api/career/contexts", {
                "case_ref": context["ref"], "context_id": context["context_id"],
                "revision": stale_context_revision, "label": "Stale", "context_kind": "company",
                "relationship": "employer",
            })
            self.assertEqual((status, stale["error"]["code"]), (409, "REVISION_STALE"))
            self.assertEqual(before_stale, {path.name: path.read_bytes() for path in self.home.state_dir.iterdir() if path.is_file()})

            status, created_project = self._write(server, headers, "/api/career/projects", {
                "parent_ref": context["ref"], "label": "Migration", "role": "Owner",
                "scope": "Batch alerts", "period": {"from": "2024-02"},
            })
            self.assertEqual(status, 200)
            context = next(row for row in self._career(server, headers)["contexts"] if row["ref"] == context["ref"])
            project = next(row for row in context["projects"] if row["ref"] == created_project["ref"])
            self._confirm(server, headers, project)
            context = next(row for row in self._career(server, headers)["contexts"] if row["ref"] == context["ref"])
            project = next(row for row in context["projects"] if row["ref"] == project["ref"])
            stale_project_revision = project["revision"]

            status, project_review = self._write(server, headers, "/api/career/projects", {
                "case_ref": project["ref"], "project_id": project["project_id"],
                "revision": project["revision"], "parent_ref": context["ref"], "label": "Migration 2",
                "role": "Technical Owner", "scope": "Batch alerts and runbook",
                "period": {"from": "2024-02", "to": "2025-12"},
            })
            self.assertEqual(status, 200)
            self.assertEqual(project_review["before"]["title"], "Migration")
            self.assertEqual(project_review["proposal"]["event"]["project"]["title"], "Migration 2")
            status, _ = self._write(server, headers, "/api/career/approve", {
                "case_ref": project["ref"], "proposal_ref": project_review["proposal"]["ref"],
                "revision": project_review["revision"],
            })
            self.assertEqual(status, 200)
            context = next(row for row in self._career(server, headers)["contexts"] if row["ref"] == context["ref"])
            project = next(row for row in context["projects"] if row["ref"] == project["ref"])
            self.assertEqual((project["label"], project["role"], project["scope"]), (
                "Migration 2", "Technical Owner", "Batch alerts and runbook",
            ))

            before_stale = {path.name: path.read_bytes() for path in self.home.state_dir.iterdir() if path.is_file()}
            status, stale = self._write(server, headers, "/api/career/projects", {
                "case_ref": project["ref"], "project_id": project["project_id"],
                "revision": stale_project_revision, "parent_ref": context["ref"], "label": "Stale",
            })
            self.assertEqual((status, stale["error"]["code"]), (409, "REVISION_STALE"))
            self.assertEqual(before_stale, {path.name: path.read_bytes() for path in self.home.state_dir.iterdir() if path.is_file()})

    def test_career_edits_clear_optional_values_and_a_current_period_end(self) -> None:
        """`null` is a deliberate edit, while an omitted key still means preserve."""
        with running_server(self.home) as server:
            headers = self._session(server)
            status, created = self._write(server, headers, "/api/career/contexts", {
                "label": "Acme", "context_kind": "company", "relationship": "employer",
                "role": "Engineer", "summary": "Platform",
                "period": {"from": "2023-01", "to": "2025-01", "current": False},
            })
            self.assertEqual(status, 200)
            context = next(row for row in self._career(server, headers)["contexts"] if row["ref"] == created["ref"])
            self._confirm(server, headers, context)
            context = next(row for row in self._career(server, headers)["contexts"] if row["ref"] == context["ref"])
            status, review = self._write(server, headers, "/api/career/contexts", {
                "case_ref": context["ref"], "context_id": context["context_id"],
                "revision": context["revision"], "label": "Acme", "context_kind": "company",
                "relationship": "employer", "role": None,
                "period": {"to": None, "current": True},
            })
            self.assertEqual(status, 200)
            # The review carries the record as it will stand once approved, so a cleared field is
            # gone from it and shows as a change only against `before`. `summary` was not in the
            # request at all, and surviving here is what separates "left out" from "set to null".
            proposed = review["proposal"]["event"]["experience_context"]
            self.assertNotIn("role", proposed)
            self.assertEqual(review["before"]["role"], "Engineer")
            self.assertEqual(proposed["summary"], "Platform")
            self.assertEqual(proposed["period"], {"from": "2023-01", "current": True})
            status, _ = self._write(server, headers, "/api/career/approve", {
                "case_ref": context["ref"], "proposal_ref": review["proposal"]["ref"],
                "revision": review["revision"],
            })
            self.assertEqual(status, 200)
            reloaded = next(row for row in self._career(server, headers)["contexts"] if row["ref"] == context["ref"])
            self.assertIsNone(reloaded["role"])
            self.assertEqual(reloaded["period"], {"from": "2023-01", "current": True})

    def test_application_label_edit_preserves_unsubmitted_metadata_and_provenance(self) -> None:
        company = cases.create_company(self.home, "Acme")
        application = cases.create_application(
            self.home, company["case_id"], "Backend", jd={"text": "Python"},
            document_kinds=["resume", "career_history"], source_refs=["cli-import:original"],
        )
        with running_server(self.home) as server:
            headers = self._session(server)
            status, _ = self._write(server, headers, "/api/applications/positions", {
                "case_ref": application["case_id"], "revision": application["updated_at"],
                "label": "Platform Engineer", "jd": {"text": "Go"},
            })
            self.assertEqual(status, 200)
        updated = cases.get_case(self.home, application["case_id"])
        self.assertEqual(updated["metadata"]["document_kinds"], ["resume", "career_history"])
        self.assertEqual(updated["source_refs"], ["cli-import:original"])

    def test_experience_revision_api_is_reviewed_approved_and_stale_protected(self) -> None:
        from proposals import make_work_event

        original = make_work_event("Original delivery evidence")
        original.update({
            "status": "confirmed",
            "evidence": ["runbook"],
            "work_event": {
                "experience_ref": "delivery",
                "role": "engineer",
                "individual_contribution": "implemented the original flow",
                "outcome_state": "qualitative",
                "confidentiality": {"contains_confidential": False, "external_use": "allowed"},
            },
        })
        persistence.append_jsonl(self.home.events, original)

        with running_server(self.home) as server:
            headers = self._session(server)
            status, started = self._write(server, headers, "/api/career/experiences/revise", {
                "event_id": original["id"], "revision": original["id"],
            })
            self.assertEqual(status, 200)
            session_ref = started["session"]["session_ref"]
            self.assertEqual(started["draft"]["summary"], "Original delivery evidence")
            status, saved = self._write(server, headers, "/api/workflows/draft", {
                "session_ref": session_ref,
                "revision": started["revision"],
                "draft": {
                    **started["draft"],
                    "summary": "Corrected delivery evidence",
                    "outcome_state": "qualitative",
                    "confidentiality": {"contains_confidential": False, "external_use": "allowed"},
                },
            })
            self.assertEqual(status, 200)
            status, review = self._write(server, headers, "/api/workflows/propose", {
                "session_ref": session_ref, "revision": saved["revision"],
            })
            self.assertEqual(status, 200)
            self.assertEqual(review["review_before"]["summary"], "Original delivery evidence")
            status, _ = self._write(server, headers, "/api/workflows/approve", {
                "session_ref": session_ref,
                "proposal_ref": review["proposal"]["ref"],
                "revision": review["revision"],
            })
            self.assertEqual(status, 200)
            rows = list_experiences(self.home)["claims"]
            self.assertEqual([row["label"] for row in rows], ["Corrected delivery evidence"])
            self.assertEqual(persistence.read_jsonl(self.home.events)[0], original)

            before_stale = self.home.events.read_bytes()
            status, stale = self._write(server, headers, "/api/career/experiences/revise", {
                "event_id": original["id"], "revision": original["id"],
            })
            self.assertEqual((status, stale["error"]["code"]), (409, "REVISION_STALE"))
            self.assertEqual(self.home.events.read_bytes(), before_stale)


if __name__ == "__main__":
    unittest.main()
