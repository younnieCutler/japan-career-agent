"""Small loopback-only HTTP server for the local Career Agent shell."""

from __future__ import annotations

import json
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import gui.artifacts as artifacts
import gui.cases as cases
from gui.security import SESSION_COOKIE, SecurityState
import gui.tanaoroshi as tanaoroshi
from self_analysis import profile_payload
from gui.templates import render_shell, static_asset
from gui.views_read import home_payload, timeline_payload


CONTENT_SECURITY_POLICY = (
    "default-src 'none'; style-src 'self'; script-src 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


class GuiServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        port: int,
        *,
        home: Any = None,
        workspace: str | None = None,
        as_of: str | None = None,
    ) -> None:
        super().__init__(("127.0.0.1", port), GuiRequestHandler)
        self.security = SecurityState(self.server_address[1])
        self.home = home
        self.workspace = workspace
        self.as_of = as_of

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

    def _json(self, value: Any) -> None:
        self._send(
            HTTPStatus.OK,
            json.dumps(value, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _json_body(self, limit: int = 131072) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > limit:
            raise ValueError("request body is too large")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def _query_value(self, name: str) -> str | None:
        query = self.path.split("?", 1)[1] if "?" in self.path else ""
        for part in query.split("&"):
            key, separator, value = part.partition("=")
            if separator and key == name:
                return value
        return None

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
        if path in {"/api/home", "/api/timeline", "/api/self-analysis", "/api/cases"}:
            self._read_api(path)
            return
        if path == "/api/tanaoroshi":
            self._resume_tanaoroshi()
            return
        self._error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._guard():
            return
        path = self.path.split("?", 1)[0]
        if path == "/session":
            self._exchange_session()
            return
        if path in {"/api/home", "/api/timeline", "/api/self-analysis"}:
            self._send(
                HTTPStatus.METHOD_NOT_ALLOWED,
                b"read-only route",
                "text/plain; charset=utf-8",
                extra={"Allow": "GET"},
            )
            return
        if not self.server.security.authenticated(self.headers, require_csrf=True):
            self._error(HTTPStatus.FORBIDDEN, "session and CSRF token required")
            return
        if path in {
            "/api/tanaoroshi",
            "/api/draft",
            "/api/checkpoint",
            "/api/proposal",
            "/api/approve",
            "/api/cases",
            "/api/cases/archive",
            "/api/cases/delete",
            "/api/artifacts",
            "/api/artifacts/update",
            "/api/artifacts/delete",
        }:
            self._write_tanaoroshi(path)
            return
        self._error(HTTPStatus.NOT_FOUND, "not found")

    def _read_api(self, path: str) -> None:
        if not self.server.security.authenticated(self.headers, require_csrf=False):
            self._error(HTTPStatus.FORBIDDEN, "session required")
            return
        if path != "/api/self-analysis" and self.server.home is None:
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "Career Vault is not configured")
            return
        try:
            if path == "/api/self-analysis":
                payload = profile_payload(self.server.workspace)
            elif path == "/api/cases":
                payload = cases.payload(self.server.home)
            elif path == "/api/home":
                payload = home_payload(
                    self.server.home,
                    workspace=self.server.workspace,
                    as_of=self.server.as_of,
                )
            else:
                payload = timeline_payload(self.server.home, as_of=self.server.as_of)
        except Exception:  # Keep read failures inside the HTTP boundary without leaking paths.
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "read model unavailable")
            return
        self._send(
            HTTPStatus.OK,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _resume_tanaoroshi(self) -> None:
        if not self.server.security.authenticated(self.headers, require_csrf=False):
            self._error(HTTPStatus.FORBIDDEN, "session required")
            return
        if self.server.home is None:
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "Career Vault is not configured")
            return
        session_id = self._query_value("session_id")
        if not session_id:
            self._error(HTTPStatus.BAD_REQUEST, "session_id is required")
            return
        try:
            self._json(tanaoroshi.resume(self.server.home, session_id))
        except ValueError:
            self._error(HTTPStatus.BAD_REQUEST, "session could not be resumed")
        except Exception:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "session unavailable")

    def _write_tanaoroshi(self, path: str) -> None:
        if self.server.home is None:
            # Preserve the data-free shell's route-discovery contract when no Vault was supplied.
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        try:
            payload = self._json_body()
            if path == "/api/tanaoroshi":
                result = tanaoroshi.start(self.server.home, case_ref=payload.get("case_ref"))
            elif path == "/api/draft":
                result = tanaoroshi.autosave(
                    self.server.home, payload["session_id"], payload.get("draft", {})
                )
            elif path == "/api/checkpoint":
                result = tanaoroshi.checkpoint(self.server.home, payload["session_id"], payload)
            elif path == "/api/proposal":
                result = tanaoroshi.submit(self.server.home, payload["session_id"])
            elif path == "/api/approve":
                result = tanaoroshi.approve_session(
                    self.server.home, payload["session_id"], payload["proposal_id"]
                )
            elif path == "/api/cases":
                result = self._create_case(payload)
            elif path == "/api/cases/archive":
                result = cases.archive_case(self.server.home, payload["case_id"])
            elif path == "/api/cases/delete":
                result = cases.delete_case(self.server.home, payload["case_id"])
            elif path == "/api/artifacts":
                result = artifacts.register_artifact(
                    self.server.home,
                    case_ref=payload["case_ref"],
                    kind=payload["kind"],
                    body=payload["body"],
                    evidence_refs=payload.get("evidence_refs"),
                    source_refs=payload.get("source_refs"),
                    generated_by=payload.get("generated_by"),
                )
            elif path == "/api/artifacts/update":
                result = artifacts.update_artifact(
                    self.server.home, payload["artifact_id"], body=payload["body"]
                )
            else:
                result = artifacts.delete_artifact(self.server.home, payload["artifact_id"])
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._error(HTTPStatus.BAD_REQUEST, "invalid 棚卸し request")
            return
        except Exception:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "棚卸し write unavailable")
            return
        self._json(result)

    def _create_case(self, payload: dict[str, Any]) -> dict[str, Any]:
        kind = payload.get("kind")
        if kind == "company":
            return cases.create_company(
                self.server.home,
                payload["label"],
                pipeline_slug=payload.get("pipeline_slug"),
                business=payload.get("business"),
                products=payload.get("products"),
                source_refs=payload.get("source_refs"),
            )
        if kind == "application":
            return cases.create_application(
                self.server.home,
                payload["parent_ref"],
                payload["label"],
                jd=payload.get("jd"),
                evidence_refs=payload.get("evidence_refs"),
                document_kinds=payload.get("document_kinds"),
                source_refs=payload.get("source_refs"),
            )
        raise ValueError("unsupported case kind")

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


def create_server(
    *,
    port: int = 0,
    home: Any = None,
    workspace: str | None = None,
    as_of: str | None = None,
) -> GuiServer:
    """Bind only to loopback; port 0 lets the OS choose a free port."""
    return GuiServer(port, home=home, workspace=workspace, as_of=as_of)


def serve(
    *,
    port: int = 0,
    no_browser: bool = False,
    home: Any = None,
    workspace: str | None = None,
    as_of: str | None = None,
) -> dict[str, str]:
    """Run the server until interrupted and return its launch metadata."""
    server = create_server(port=port, home=home, workspace=workspace, as_of=as_of)
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
