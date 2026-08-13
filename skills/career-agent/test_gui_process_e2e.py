"""Process-level GUI crash/restart contract for the local resumable session path."""

from __future__ import annotations

import http.client
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

from vault import initialize_vault  # noqa: E402


def request(
    host: str,
    port: int,
    method: str,
    path: str,
    *,
    body: dict | None = None,
    cookie: str | None = None,
    csrf: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    headers: dict[str, str] = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    if csrf:
        headers["X-CSRF-Token"] = csrf
    connection = http.client.HTTPConnection(host, port, timeout=3)
    connection.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
    response = connection.getresponse()
    payload = response.read()
    result = response.status, dict(response.getheaders()), payload
    connection.close()
    return result


class GuiProcessE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault = Path(self.tempdir.name) / "vault"
        initialize_vault(self.vault)
        self.processes: list[subprocess.Popen[str]] = []

    def tearDown(self) -> None:
        for process in self.processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
        self.tempdir.cleanup()

    def launch(self) -> tuple[subprocess.Popen[str], str, int, str]:
        process = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "skills" / "career-agent" / "career_agent.py"),
                "ui",
                "--vault",
                str(self.vault),
                "--no-browser",
                "--port",
                "0",
                "--format",
                "json",
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.processes.append(process)
        lines: queue.Queue[str] = queue.Queue(maxsize=1)

        def read_ready_line() -> None:
            assert process.stdout is not None
            lines.put(process.stdout.readline())

        threading.Thread(target=read_ready_line, daemon=True).start()
        try:
            line = lines.get(timeout=5).strip()
        except queue.Empty:
            process.kill()
            raise AssertionError("GUI process did not announce a loopback URL")
        if not line:
            stderr = process.stderr.read() if process.stderr is not None else ""
            if "GUI_START_FAILED" in stderr:
                if os.environ.get("CI", "").casefold() == "true":
                    raise AssertionError("loopback bind unavailable in CI")
                raise unittest.SkipTest("loopback bind unavailable in this execution sandbox")
            raise AssertionError(f"GUI process exited before announcing its URL: {stderr}")
        prefix = "Japan Career Agent GUI: "
        self.assertTrue(line.startswith(prefix), line)
        parsed = urlsplit(line.removeprefix(prefix))
        token = parse_qs(parsed.fragment).get("t", [None])[0]
        self.assertIsNotNone(token)
        return process, str(parsed.hostname), int(parsed.port), str(token)

    def test_sigkill_restart_discovers_and_resumes_the_same_draft(self) -> None:
        first, host, port, token = self.launch()
        status, headers, raw = request(host, port, "POST", "/session", body={"token": token})
        self.assertEqual(status, 200, raw)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        csrf = json.loads(raw)["csrf_token"]

        status, _, raw = request(
            host,
            port,
            "POST",
            "/api/workflows/start",
            body={"workflow": "career_inventory"},
            cookie=cookie,
            csrf=csrf,
        )
        self.assertEqual(status, 200, raw)
        started = json.loads(raw)
        session_ref = started["session"]["session_ref"]
        status, _, raw = request(
            host,
            port,
            "POST",
            "/api/workflows/draft",
            body={
                "session_ref": session_ref,
                "revision": started["revision"],
                "draft": {"summary": "process E2E", "non_work": False},
            },
            cookie=cookie,
            csrf=csrf,
        )
        self.assertEqual(status, 200, raw)

        first.kill()
        first.wait(timeout=3)
        second, host, port, token = self.launch()
        status, headers, raw = request(host, port, "POST", "/session", body={"token": token})
        self.assertEqual(status, 200, raw)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, _, raw = request(host, port, "GET", "/api/sessions", cookie=cookie)
        self.assertEqual(status, 200, raw)
        discovered = json.loads(raw)
        self.assertEqual(len(discovered["sessions"]), 1)
        self.assertEqual(discovered["sessions"][0]["session_ref"], session_ref)
        status, _, raw = request(
            host, port, "GET", f"/api/work?session_ref={session_ref}", cookie=cookie
        )
        self.assertEqual(status, 200, raw)
        resumed = json.loads(raw)
        self.assertEqual(resumed["session"]["stage"], "experience")
        self.assertEqual(resumed["draft"]["summary"], "process E2E")
        self.assertTrue(resumed["unconfirmed_input"])


if __name__ == "__main__":
    unittest.main()
