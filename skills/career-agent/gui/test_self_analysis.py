"""GUI route and browser contract tests for self-analysis handoff."""

from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from gui._test_client import client_source  # noqa: E402
from gui.server import create_server  # noqa: E402
from gui.templates import jiko_asset  # noqa: E402


@contextmanager
def running_server(workspace: Path):
    try:
        server = create_server(port=0, home=object(), workspace=workspace)
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


class SelfAnalysisGuiTests(unittest.TestCase):
    def test_the_structured_form_is_the_existing_checklist_not_a_second_one(self) -> None:
        """A profile is valid only with all thirteen required fields, so there is no partial form.

        Rebuilding a smaller one in the GUI could not produce a profile the validator accepts, and
        rebuilding the whole thing would leave two 44KB forms to keep in step. The GUI serves the
        one jiko-bunseki already ships and that its contract test already covers.
        """
        # Compared as bytes on both sides. The server sends bytes, and reading the same file as
        # text translates CRLF to LF on Windows, which made this fail there for a difference the
        # browser never sees.
        served = jiko_asset("checklist.html")
        source = (
            Path(__file__).resolve().parents[2] / "jiko-bunseki" / "checklist.html"
        ).read_bytes()

        self.assertEqual(served, source)
        self.assertIn("/jiko/checklist.html", client_source())
        with self.assertRaises(FileNotFoundError):
            jiko_asset("../../../etc/passwd")

    def test_the_checklist_may_run_inline_but_may_not_transmit(self) -> None:
        """It predates the GUI and uses inline script, style and handlers.

        Under the main policy the browser would render it and run none of it — the same failure the
        missing connect-src caused. It gets its own policy, and the absence of connect-src there is
        what keeps a locally-running form from sending career answers anywhere.
        """
        source = Path(__file__).with_name("server.py").read_text(encoding="utf-8")
        checklist = jiko_asset("checklist.html").decode("utf-8")
        runtime = jiko_asset("checklist_runtime.js").decode("utf-8")
        policy = source.split("CHECKLIST_SECURITY_POLICY = (", 1)[1].split(")", 1)[0]

        self.assertIn("'unsafe-inline'", policy)
        self.assertNotIn("connect-src", policy)
        for call in ("fetch(", "XMLHttpRequest", "sendBeacon"):
            self.assertNotIn(call, checklist + runtime, call)

    def test_browser_contract_has_a_read_route_and_visible_handoff(self) -> None:
        script = client_source()

        self.assertIn("/api/self-analysis", script)
        self.assertIn("export default function SelfAnalysisScreen", script)
        self.assertIn("handoff", script)
        self.assertIn("success.self_analysis_approved", script)
        self.assertIn("<ChangesView before={before} event={event} />", script)
        self.assertIn("before={review.review_before}", script)
        self.assertIn("export function containsUnknown", script)
        self.assertIn('key === "period" && value.current === true', script)
        self.assertIn('kind === "profile"\n    ? Object.keys(payload || {})', script)

    def test_authenticated_self_analysis_route_is_get_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            with running_server(workspace) as server:
                payload = json.dumps({"token": server.bootstrap_token})
                status, headers, body = request(
                    server,
                    "POST",
                    "/session",
                    headers={"Content-Type": "application/json"},
                    body=payload,
                )
                self.assertEqual(status, 200)
                cookie = headers["Set-Cookie"]
                response = request(server, "GET", "/api/self-analysis", headers={"Cookie": cookie})
                self.assertEqual(response[0], 200)
                result = json.loads(response[2])
                self.assertEqual(result["mode"], "self-analysis")
                self.assertEqual(result["state"], "unknown")
                post = request(server, "POST", "/api/self-analysis", headers={"Cookie": cookie}, body="{}")
                self.assertEqual(post[0], 405)
                self.assertEqual(post[1]["Allow"], "GET")


if __name__ == "__main__":
    unittest.main()
