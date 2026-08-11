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
        script = import_module("gui.templates").static_asset("bootstrap.js").decode("utf-8")
        self.assertIn("/api/projects", script)
        self.assertIn("renderProjects", script)
        self.assertIn("재직 중", script)
        self.assertIn("textContent", script)
        self.assertNotIn("innerHTML", script)


if __name__ == "__main__":
    unittest.main()
