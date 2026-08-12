#!/usr/bin/env python3
"""RED contracts for the read-only GUI home and timeline."""

from __future__ import annotations

import http.client
import json
import os
import sys
import threading
import tempfile
import unittest
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from unittest.mock import patch


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _read_views():
    try:
        return import_module("gui.views_read")
    except ModuleNotFoundError as exc:
        raise AssertionError(f"GUI read views are not implemented: {exc}") from exc


def _sample_reads():
    return {
        "status": {
            "profile": {
                "track": "chuto",
                "career_status": "active",
                "target_role": "LLMOps Engineer",
                "employment_status": "employed",
                "job_search": "off",
            },
            "state": {"career_mode": "maintenance", "last_event_id": "evt-state"},
            "pending_proposals": 1,
            "pending_kind": "event",
            "event_count": 3,
            "workspace": {"exists": True, "pipeline_exists": True, "company_count": 1},
        },
        "readiness": {
            "dimensions": {
                "recent_work_evidence": "Confirmed",
                "project_history": "Partial",
                "metrics_evidence": "Unknown",
            },
            "counts": {"projects": 1, "confirmed_work_events": 2},
            "no_total_by_design": True,
        },
        "evidence": {
            "projects": [{
                "id": "prj-1",
                "title": "Migration",
                "status": "active",
                "work_events": [{"event_id": "evt-1", "title": "Runbook"}],
            }],
            "confirmed_work_event_count": 1,
        },
        "weekly": {"groups": [], "ask_first": ["result"]},
        "experiences": {
            "contexts": {
                "ctx-1": {
                    "id": "ctx-1",
                    "kind": "company",
                    "label": "Acme",
                    "period": {"from": "2024-01", "to": None},
                }
            },
            "experiences": [{"experience_id": "project:prj-1", "label": "Migration"}],
        },
        "projects": {
            "projects": [{
                "id": "prj-1",
                "title": "Migration",
                "period": {"from": "2025-01", "to": None},
            }]
        },
        "guided": {
            "guided": {
                "summary": {"unknown_count": 1, "conflict_count": 1},
                "available_actions": [{
                    "id": "inspect_unknown",
                    "label": "Inspect Unknown",
                    "command": "personal-profile",
                }],
            }
        },
    }


class GuiReadParityTests(unittest.TestCase):
    def test_real_vault_read_is_data_preserving(self):
        from vault import CareerVault, initialize_vault

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "vault"
            initialize_vault(root)
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            views = _read_views()
            home = CareerVault(root)
            result = views.home_payload(home, as_of="2026-08-12")
            timeline = views.timeline_payload(home, as_of="2026-08-12")
            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

        self.assertEqual(before, after)
        self.assertTrue(result["no_total_by_design"])
        self.assertEqual(timeline["sections"], [])

    def test_home_calls_existing_read_models_and_has_no_composite_percentage(self):
        reads = _sample_reads()
        views = _read_views()
        with (
            patch.object(views, "status", return_value=reads["status"]) as status,
            patch.object(views, "readiness", return_value=reads["readiness"]) as readiness,
            patch.object(views, "evidence_pool", return_value=reads["evidence"]) as evidence,
            patch.object(views, "weekly_review", return_value=reads["weekly"]) as weekly,
            patch.object(views, "list_experiences", return_value=reads["experiences"]) as experiences,
            patch.object(views, "list_projects", return_value=reads["projects"]) as projects,
            patch.object(views, "run_guided", return_value=reads["guided"]) as guided,
        ):
            result = views.home_payload(object(), workspace="case", as_of="2026-08-12")

        for call in (status, readiness, evidence, weekly, experiences, projects, guided):
            self.assertTrue(call.called, call)
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("evt-1", encoded)
        self.assertNotIn("prj-1", encoded)
        self.assertNotIn("last_event_id", encoded)
        self.assertNotIn("percentage", encoded.casefold())
        self.assertNotIn("percent", encoded.casefold())
        self.assertTrue(result["no_total_by_design"])
        self.assertEqual(result["pending_approval"]["count"], 1)
        self.assertEqual(result["conflicts"]["count"], 1)

    def test_debug_mode_is_the_only_way_to_include_internal_ids(self):
        views = _read_views()
        reads = _sample_reads()
        with (
            patch.dict(os.environ, {"JAPAN_CAREER_GUI_DEBUG": "1"}),
            patch.object(views, "status", return_value=reads["status"]),
            patch.object(views, "readiness", return_value=reads["readiness"]),
            patch.object(views, "evidence_pool", return_value=reads["evidence"]),
            patch.object(views, "weekly_review", return_value=reads["weekly"]),
            patch.object(views, "list_experiences", return_value=reads["experiences"]),
            patch.object(views, "list_projects", return_value=reads["projects"]),
            patch.object(views, "run_guided", return_value=reads["guided"]),
        ):
            result = views.home_payload(object(), as_of="2026-08-12")
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertIn("prj-1", encoded)
        self.assertIn("evt-1", encoded)

    def test_timeline_uses_existing_project_timeline_and_sorts_time_sections(self):
        reads = _sample_reads()
        views = _read_views()
        home = object()
        with (
            patch.object(views, "list_experiences", return_value=reads["experiences"]),
            patch.object(views, "list_projects", return_value=reads["projects"]),
            patch.object(
                views,
                "show_project_timeline",
                return_value={"project": reads["projects"]["projects"][0], "timeline": []},
            ) as timeline,
        ):
            result = views.timeline_payload(home, as_of="2026-08-12")

        timeline.assert_called_once_with(home, "prj-1")
        self.assertEqual(result["mode"], "timeline")
        self.assertEqual(result["sections"][0]["period"]["from"], "2024-01")
        self.assertNotIn("prj-1", json.dumps(result))


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


class GuiReadRouteTests(unittest.TestCase):
    def test_authenticated_home_returns_json_without_csrf_for_read(self):
        server_module = import_module("gui.server")
        with patch.object(server_module, "home_payload", return_value={"mode": "home"}):
            with running_server() as server:
                port = server.server_address[1]
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                connection.request(
                    "POST",
                    "/session",
                    body=json.dumps({"token": server.bootstrap_token}),
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                cookie = response.getheader("Set-Cookie")
                response.read()
                connection.request("GET", "/api/home", headers={"Cookie": cookie})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Content-Type"), "application/json; charset=utf-8")
                self.assertEqual(json.loads(response.read()), {"mode": "home"})
                connection.close()

    def test_read_routes_are_session_protected_and_get_only(self):
        with running_server() as server:
            port = server.server_address[1]
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            connection.request("GET", "/api/home")
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            connection.request("POST", "/api/home", body="{}")
            response = connection.getresponse()
            self.assertEqual(response.status, 405)
            self.assertEqual(response.getheader("Allow"), "GET")
            response.read()
            connection.close()


if __name__ == "__main__":
    unittest.main()
