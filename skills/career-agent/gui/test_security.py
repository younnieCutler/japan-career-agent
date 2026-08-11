#!/usr/bin/env python3
"""RED contract tests for the local GUI foundation and browser bootstrap boundary."""

from __future__ import annotations

import http.client
import json
import sys
import threading
import unittest
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


REQUIRED_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'self'; script-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
}


def _server_module():
    try:
        return import_module("gui.server")
    except ModuleNotFoundError as exc:  # Keep the RED failure about the missing feature.
        raise AssertionError(f"GUI server is not implemented: {exc}") from exc


@contextmanager
def running_server():
    try:
        server = _server_module().create_server(port=0)
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


def request(server, method, path, *, headers=None, body=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    payload = response.read()
    result = response.status, dict(response.getheaders()), payload
    connection.close()
    return result


class GuiSecurityTests(unittest.TestCase):
    def test_security_state_contract_without_network(self):
        security = _server_module().SecurityState(43210)
        self.assertTrue(security.host_allowed("127.0.0.1:43210"))
        self.assertTrue(security.host_allowed("localhost:43210"))
        self.assertFalse(security.host_allowed("evil.example:43210"))
        self.assertTrue(security.origin_allowed("http://127.0.0.1:43210"))
        self.assertTrue(security.origin_allowed(None))
        self.assertFalse(security.origin_allowed("http://evil.example"))

        exchanged = security.exchange(security.bootstrap_token)
        self.assertIsNotNone(exchanged)
        session_id, session = exchanged
        cookie = {"Cookie": f"jca_session={session_id}"}
        self.assertFalse(security.authenticated(cookie, require_csrf=True))
        self.assertTrue(
            security.authenticated(
                {**cookie, "X-CSRF-Token": session.csrf_token}, require_csrf=True
            )
        )
        self.assertIsNone(security.exchange(security.bootstrap_token))

    def test_shell_and_bootstrap_assets_are_external_and_data_free(self):
        templates = _server_module()
        html = templates.render_shell()
        bootstrap = templates.static_asset("bootstrap.js").decode("utf-8")
        stylesheet = templates.static_asset("style.css").decode("utf-8")
        self.assertIn('<script src="/static/bootstrap.js" defer></script>', html)
        self.assertNotIn("<script>", html)
        self.assertIn("history.replaceState", bootstrap)
        self.assertIn("prefers-reduced-motion", stylesheet)
        self.assertNotIn("career-state.toml", html + bootstrap + stylesheet)

    def test_root_is_data_free_and_loads_external_bootstrap_only(self):
        with running_server() as server:
            status, headers, body = request(server, "GET", "/")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn('<script src="/static/bootstrap.js" defer></script>', html)
        self.assertNotIn("<script>", html)
        self.assertNotIn(server.bootstrap_token, html)
        self.assertNotIn("events.jsonl", html)
        self.assertNotIn("career-state.toml", html)

    def test_host_and_origin_are_both_restricted_without_cors(self):
        with running_server() as server:
            port = server.server_address[1]
            status, headers, _ = request(
                server, "GET", "/", headers={"Host": f"evil.example:{port}"}
            )
            self.assertEqual(status, 421)
            self.assertNotIn("Access-Control-Allow-Origin", headers)

            status, headers, _ = request(
                server,
                "GET",
                "/",
                headers={"Origin": "http://evil.example"},
            )
            self.assertEqual(status, 403)
            self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_bootstrap_token_exchanges_for_strict_session_and_csrf_is_double_checked(self):
        with running_server() as server:
            payload = json.dumps({"token": server.bootstrap_token})
            status, headers, body = request(
                server,
                "POST",
                "/session",
                headers={
                    "Content-Type": "application/json",
                    "Origin": server.origin,
                },
                body=payload,
            )
            self.assertEqual(status, 200)
            cookie = headers["Set-Cookie"]
            self.assertIn("HttpOnly", cookie)
            self.assertIn("SameSite=Strict", cookie)
            self.assertIn("Path=/", cookie)
            csrf_token = json.loads(body)["csrf_token"]

            status, _, _ = request(server, "POST", "/api/draft", body="{}")
            self.assertEqual(status, 403)
            status, _, _ = request(
                server, "POST", "/api/draft", headers={"Cookie": cookie}, body="{}"
            )
            self.assertEqual(status, 403)
            status, _, _ = request(
                server,
                "POST",
                "/api/draft",
                headers={"Cookie": cookie, "X-CSRF-Token": csrf_token},
                body="{}",
            )
            self.assertEqual(status, 404)

    def test_invalid_bootstrap_token_is_refused(self):
        with running_server() as server:
            status, headers, _ = request(
                server,
                "POST",
                "/session",
                headers={"Content-Type": "application/json"},
                body=json.dumps({"token": "wrong"}),
            )
            self.assertEqual(status, 403)
            self.assertNotIn("Set-Cookie", headers)

    def test_all_responses_carry_the_fixed_security_headers(self):
        with running_server() as server:
            for path in ("/", "/static/bootstrap.js", "/missing"):
                with self.subTest(path=path):
                    status, headers, _ = request(server, "GET", path)
                    self.assertIn(status, (200, 404))
                    for name, value in REQUIRED_HEADERS.items():
                        self.assertEqual(headers.get(name), value, name)


if __name__ == "__main__":
    unittest.main()
