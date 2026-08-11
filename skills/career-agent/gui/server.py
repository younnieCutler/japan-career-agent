"""Small loopback-only HTTP server for the local Career Agent shell."""

from __future__ import annotations

import json
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from gui.security import SESSION_COOKIE, SecurityState
from gui.templates import render_shell, static_asset


CONTENT_SECURITY_POLICY = (
    "default-src 'none'; style-src 'self'; script-src 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


class GuiServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, port: int) -> None:
        super().__init__(("127.0.0.1", port), GuiRequestHandler)
        self.security = SecurityState(self.server_address[1])

    @property
    def bootstrap_token(self) -> str:
        return self.security.bootstrap_token

    @property
    def origin(self) -> str:
        return next(iter(sorted(self.security.origins)))

    @property
    def bootstrap_url(self) -> str:
        return f"{self.origin}/#t={self.bootstrap_token}"


class GuiRequestHandler(BaseHTTPRequestHandler):
    server: GuiServer

    def _send(self, status: int, body: bytes, content_type: str, *, extra=None) -> None:
        self.send_response(status)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        self.send_header("Content-Type", content_type)
        if extra:
            for name, value in extra.items():
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._send(status, message.encode("utf-8"), "text/plain; charset=utf-8")

    def _guard(self) -> bool:
        if not self.server.security.host_allowed(self.headers.get("Host")):
            self._error(HTTPStatus.MISDIRECTED_REQUEST, "invalid Host")
            return False
        if not self.server.security.origin_allowed(self.headers.get("Origin")):
            self._error(HTTPStatus.FORBIDDEN, "invalid Origin")
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._guard():
            return
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(HTTPStatus.OK, render_shell().encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/static/bootstrap.js":
            self._send(HTTPStatus.OK, static_asset("bootstrap.js"), "text/javascript; charset=utf-8")
            return
        if path == "/static/style.css":
            self._send(HTTPStatus.OK, static_asset("style.css"), "text/css; charset=utf-8")
            return
        self._error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._guard():
            return
        path = self.path.split("?", 1)[0]
        if path == "/session":
            self._exchange_session()
            return
        if not self.server.security.authenticated(self.headers, require_csrf=True):
            self._error(HTTPStatus.FORBIDDEN, "session and CSRF token required")
            return
        self._error(HTTPStatus.NOT_FOUND, "not found")

    def _exchange_session(self) -> None:
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 4096)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._error(HTTPStatus.FORBIDDEN, "invalid bootstrap request")
            return
        if not isinstance(payload, dict):
            self._error(HTTPStatus.FORBIDDEN, "invalid bootstrap request")
            return
        exchanged = self.server.security.exchange(payload.get("token"))
        if exchanged is None:
            self._error(HTTPStatus.FORBIDDEN, "invalid bootstrap token")
            return
        session_id, session = exchanged
        body = json.dumps({"csrf_token": session.csrf_token}).encode("utf-8")
        cookie = f"{SESSION_COOKIE}={session_id}; HttpOnly; SameSite=Strict; Path=/"
        self._send(
            HTTPStatus.OK,
            body,
            "application/json; charset=utf-8",
            extra={"Set-Cookie": cookie},
        )


def create_server(*, port: int = 0) -> GuiServer:
    """Bind only to loopback; port 0 lets the OS choose a free port."""
    return GuiServer(port)


def serve(*, port: int = 0, no_browser: bool = False) -> dict[str, str]:
    """Run the server until interrupted and return its launch metadata."""
    server = create_server(port=port)
    url = server.bootstrap_url
    print(f"Japan Career Agent GUI: {url}", flush=True)
    if not no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return {"mode": "ui", "url": url}
