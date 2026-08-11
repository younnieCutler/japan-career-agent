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

from gui.server import create_server  # noqa: E402
from gui.templates import static_asset  # noqa: E402


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
    def test_browser_contract_has_a_read_route_and_visible_handoff(self) -> None:
        script = static_asset("bootstrap.js").decode("utf-8")

        self.assertIn("/api/self-analysis", script)
        self.assertIn("renderSelfAnalysis", script)
        self.assertIn("handoff", script)
        self.assertIn("textContent", script)

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
