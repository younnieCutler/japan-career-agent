"""Small loopback-only HTTP server for the local Career Agent shell."""

from __future__ import annotations

import json
import re
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import gui.artifacts as artifacts
import gui.cases as cases
from gui.security import SESSION_COOKIE, SecurityState
import gui.tanaoroshi as tanaoroshi
from self_analysis import profile_payload, workflow_profile
from sessions import (
    approve_proposal as approve_workflow_proposal,
    archive_session,
    checkpoint_session,
    create_proposal as create_workflow_proposal,
    create_session,
    list_sessions,
    restore_session,
    resume_session,
    save_draft,
)
from gui.templates import (
    JIKO_ASSETS,
    STATIC_ASSETS as TEMPLATE_STATIC_ASSETS,
    gui_messages,
    jiko_asset,
    normalize_gui_language,
    render_shell,
    static_asset,
)
from gui.views_read import (
    applications_payload,
    career_overview_payload,
    documents_payload,
    home_payload,
    projects_payload,
    timeline_payload,
)


# `default-src 'none'` denies anything a later directive does not name, so every capability the
# shipped client uses has to appear here. `connect-src` is what lets `bootstrap.js` reach
# `/session` and the read APIs; without it the browser renders the shell and then blocks every
# fetch, which no `http.client` test can observe.
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)

# The jiko-bunseki checklist is a self-contained form that predates the GUI: inline style, one
# inline script and inline handlers. Under the policy above the browser would render it and run
# nothing, which is the same failure the missing `connect-src` caused. It gets its own policy
# instead of being rewritten. `connect-src` is deliberately absent here — the file makes no
# network call, so with no connect-src the page cannot send anything anywhere, which is the
# guarantee that matters when the alternative is loosening script-src for the whole GUI.
CHECKLIST_SECURITY_POLICY = (
    "default-src 'none'; style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "form-action 'none'; frame-ancestors 'none'"
)

SHELL_ROUTES = {
    "/",
    "/career",
    "/career/in-progress",
    "/career/timeline",
    "/diagnosis",
    "/self-analysis",
    "/applications",
    "/documents",
}
WORK_ROUTE = re.compile(r"^/work/session-[a-f0-9]{12,64}$")
STATIC_ASSETS = TEMPLATE_STATIC_ASSETS
APPLICATION_DOCUMENT_TYPES = {"resume", "career_history", "self_pr", "cover_letter", "other"}


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
        language: str = "ko",
    ) -> None:
        super().__init__(("127.0.0.1", port), GuiRequestHandler)
        self.security = SecurityState(self.server_address[1])
        self.home = home
        self.workspace = workspace
        self.as_of = as_of
        self.language = normalize_gui_language(language)

    @property
    def bootstrap_token(self) -> str:
        return self.security.bootstrap_token

    @property
    def origin(self) -> str:
        return next(iter(sorted(self.security.origins)))

    @property
    def bootstrap_url(self) -> str:
        return f"{self.origin}/?lang={self.language}#t={self.bootstrap_token}"


class GuiRequestHandler(BaseHTTPRequestHandler):
    server: GuiServer

    def _send(
        self, status: int, body: bytes, content_type: str, *, extra=None, policy: str | None = None
    ) -> None:
        self.send_response(status)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", policy or CONTENT_SECURITY_POLICY)
        self.send_header("Content-Type", content_type)
        if extra:
            for name, value in extra.items():
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._send(status, message.encode("utf-8"), "text/plain; charset=utf-8")

    def _api_error(
        self,
        error: Exception,
        *,
        fallback_code: str,
        fallback_status: int = HTTPStatus.INTERNAL_SERVER_ERROR,
    ) -> None:
        code = getattr(error, "code", None) or fallback_code
        status = {
            "INVALID_INPUT": HTTPStatus.BAD_REQUEST,
            "INVALID_RELATIONSHIP": HTTPStatus.CONFLICT,
            "PARENT_NOT_CONFIRMED": HTTPStatus.CONFLICT,
            "CONTEXT_REQUIRED": HTTPStatus.CONFLICT,
            "CASE_HAS_ACTIVE_CHILDREN": HTTPStatus.CONFLICT,
            "CASE_ALREADY_CONFIRMED": HTTPStatus.CONFLICT,
            "REVISION_STALE": HTTPStatus.CONFLICT,
            "PROPOSAL_STALE": HTTPStatus.CONFLICT,
            "SESSION_COMPLETED": HTTPStatus.CONFLICT,
            "SESSION_ARCHIVED": HTTPStatus.CONFLICT,
            "SESSION_SCHEMA_NEWER": HTTPStatus.CONFLICT,
            "SESSION_AMBIGUOUS": HTTPStatus.CONFLICT,
            "SESSION_NOT_FOUND": HTTPStatus.NOT_FOUND,
            "CASE_NOT_FOUND": HTTPStatus.NOT_FOUND,
            "PROPOSAL_NOT_FOUND": HTTPStatus.NOT_FOUND,
            "PROFILE_NOT_FOUND": HTTPStatus.NOT_FOUND,
        }.get(code, fallback_status)
        retryable = bool(getattr(error, "retryable", False))
        state_changed = bool(getattr(error, "state_changed", False))
        body = {
            "ok": False,
            "error": {
                "code": code,
                "retryable": retryable,
                "state_changed": state_changed,
                "input_safe": not state_changed,
            },
        }
        details = getattr(error, "details", None)
        if isinstance(details, dict):
            body["error"]["details"] = {
                key: value
                for key, value in details.items()
                if key not in {"path", "vault", "workspace"}
            }
        self._send(
            status,
            json.dumps(body, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

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
        query = self.path.partition("?")[2]
        for part in query.split("&"):
            key, separator, value = part.partition("=")
            if separator and key == name:
                return value
        return None

    def _request_path(self) -> str:
        return self.path.partition("?")[0]

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
        path = self._request_path()
        if path in SHELL_ROUTES or WORK_ROUTE.fullmatch(path):
            language = normalize_gui_language(self._query_value("lang") or self.server.language)
            self._send(
                HTTPStatus.OK,
                render_shell(language).encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return
        if path.startswith("/static/"):
            name = path.removeprefix("/static/")
            if name not in STATIC_ASSETS:
                self._error(HTTPStatus.NOT_FOUND, "not found")
                return
            content_type = "text/css; charset=utf-8" if name.endswith(".css") else "text/javascript; charset=utf-8"
            self._send(HTTPStatus.OK, static_asset(name), content_type)
            return
        if path in {
            "/api/home",
            "/api/career",
            "/api/timeline",
            "/api/sessions",
            "/api/self-analysis",
            "/api/applications",
            "/api/documents",
            "/api/cases",
            "/api/projects",
            "/api/i18n",
        }:
            self._read_api(path)
            return
        if path == "/api/artifact-body":
            self._artifact_body()
            return
        if path in {"/jiko/checklist.html", "/jiko/checklist_runtime.js"}:
            self._checklist(path.rsplit("/", 1)[1])
            return
        if path in {"/api/tanaoroshi", "/api/work"}:
            self._resume_tanaoroshi()
            return
        self._error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._guard():
            return
        path = self._request_path()
        if path == "/session":
            self._exchange_session()
            return
        if path in {
            "/api/home", "/api/career", "/api/timeline", "/api/sessions",
            "/api/self-analysis", "/api/applications", "/api/documents",
            "/api/projects", "/api/artifact-body", "/api/i18n", "/api/work",
        }:
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
            "/api/workflows/start",
            "/api/workflows/draft",
            "/api/workflows/checkpoint",
            "/api/workflows/propose",
            "/api/workflows/approve",
            "/api/workflows/archive",
            "/api/workflows/restore",
            "/api/workflows/import-profile",
            "/api/workflows/assign-project",
            "/api/career/contexts",
            "/api/career/projects",
            "/api/career/propose",
            "/api/career/approve",
            "/api/career/organize",
            "/api/career/assign-project-context",
            "/api/cases",
            "/api/cases/archive",
            "/api/cases/restore",
            "/api/cases/delete",
            "/api/applications/companies",
            "/api/applications/positions",
            "/api/applications/research",
            "/api/applications/documents",
            "/api/artifacts",
            "/api/artifacts/update",
            "/api/artifacts/delete",
        }:
            self._write_api(path)
            return
        self._error(HTTPStatus.NOT_FOUND, "not found")

    def _checklist(self, name: str) -> None:
        """Serve the jiko-bunseki self-analysis form. It writes nothing: the user copies its output."""
        if not self.server.security.authenticated(self.headers, require_csrf=False):
            self._error(HTTPStatus.FORBIDDEN, "session required")
            return
        try:
            body = jiko_asset(name)
        except (FileNotFoundError, OSError):
            self._error(HTTPStatus.NOT_FOUND, "the self-analysis checklist is not installed")
            return
        self._send(HTTPStatus.OK, body, JIKO_ASSETS[name], policy=CHECKLIST_SECURITY_POLICY)

    def _artifact_body(self) -> None:
        """Serve one artifact's stored text. Read-only: opening a document changes nothing."""
        if not self.server.security.authenticated(self.headers, require_csrf=False):
            self._error(HTTPStatus.FORBIDDEN, "session required")
            return
        if self.server.home is None:
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "Career Vault is not configured")
            return
        artifact_id = self._query_value("artifact_ref") or self._query_value("artifact_id")
        if not artifact_id:
            self._error(HTTPStatus.BAD_REQUEST, "artifact_id is required")
            return
        try:
            payload = artifacts.artifact_body(self.server.home, artifact_id)
        except Exception as exc:
            self._api_error(exc, fallback_code="READ_FAILED")
            return
        if payload is None:
            self._error(HTTPStatus.NOT_FOUND, "artifact body not found")
            return
        self._json({"mode": "artifact-body", "read_only": True, **payload})

    def _read_api(self, path: str) -> None:
        if not self.server.security.authenticated(self.headers, require_csrf=False):
            self._error(HTTPStatus.FORBIDDEN, "session required")
            return
        if path not in {"/api/self-analysis", "/api/i18n"} and self.server.home is None:
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "Career Vault is not configured")
            return
        readers = {
            "/api/home": lambda: home_payload(
                self.server.home, workspace=self.server.workspace, as_of=self.server.as_of
            ),
            "/api/career": lambda: career_overview_payload(self.server.home),
            "/api/timeline": lambda: timeline_payload(self.server.home, as_of=self.server.as_of),
            "/api/sessions": lambda: tanaoroshi.present(
                list_sessions(
                    self.server.home,
                    include_archived=self._query_value("include_archived") == "1",
                )
            ),
            "/api/self-analysis": lambda: profile_payload(self.server.workspace),
            "/api/applications": lambda: applications_payload(self.server.home),
            "/api/documents": lambda: documents_payload(self.server.home),
            "/api/cases": lambda: cases.payload(self.server.home),
            "/api/projects": lambda: projects_payload(self.server.home),
            "/api/i18n": lambda: {
                "language": normalize_gui_language(
                    self._query_value("lang") or self.server.language
                ),
                "messages": gui_messages(
                    normalize_gui_language(self._query_value("lang") or self.server.language)
                ),
            },
        }
        try:
            payload = readers[path]()
        except Exception as exc:  # Keep read failures inside the HTTP boundary without leaking paths.
            self._api_error(exc, fallback_code="READ_FAILED")
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
        session_id = self._query_value("session_ref") or self._query_value("session_id")
        if not session_id:
            self._error(HTTPStatus.BAD_REQUEST, "session_id is required")
            return
        try:
            self._json(tanaoroshi.resume(self.server.home, session_id))
        except Exception as exc:
            self._api_error(exc, fallback_code="READ_FAILED")

    def _write_api(self, path: str) -> None:
        if self.server.home is None:
            # Preserve the data-free shell's route-discovery contract when no Vault was supplied.
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        try:
            payload = self._json_body()
            if path in {"/api/tanaoroshi", "/api/workflows/start"}:
                if path == "/api/tanaoroshi":
                    result = tanaoroshi.start(self.server.home, case_ref=payload.get("case_ref"))
                else:
                    result = self._start_workflow(payload)
            elif path in {"/api/draft", "/api/workflows/draft"}:
                result = save_draft(
                    self.server.home,
                    payload.get("session_ref") or payload["session_id"],
                    payload.get("draft", {}),
                    expected_revision=payload.get("revision", payload.get("expected_revision")),
                    entrypoint="gui",
                )
            elif path in {"/api/checkpoint", "/api/workflows/checkpoint"}:
                result = checkpoint_session(
                    self.server.home,
                    payload.get("session_ref") or payload["session_id"],
                    stage=payload.get("stage"),
                    current_item_ref=payload.get("current_item_ref"),
                    missing=payload.get("missing_fields"),
                    completed=payload.get("completed"),
                    expected_revision=payload.get("revision", payload.get("expected_revision")),
                    entrypoint="gui",
                )
            elif path in {"/api/proposal", "/api/workflows/propose"}:
                result = create_workflow_proposal(
                    self.server.home,
                    payload.get("session_ref") or payload["session_id"],
                    expected_revision=payload.get("revision", payload.get("expected_revision")),
                    entrypoint="gui",
                )
            elif path in {"/api/approve", "/api/workflows/approve"}:
                result = approve_workflow_proposal(
                    self.server.home,
                    payload.get("session_ref") or payload["session_id"],
                    payload.get("proposal_ref") or payload["proposal_id"],
                    expected_revision=payload.get("revision", payload.get("expected_revision")),
                    entrypoint="gui",
                )
            elif path == "/api/workflows/archive":
                result = archive_session(
                    self.server.home,
                    payload["session_ref"],
                    expected_revision=payload.get("revision"),
                    entrypoint="gui",
                )
            elif path == "/api/workflows/restore":
                result = restore_session(
                    self.server.home,
                    payload["session_ref"],
                    expected_revision=payload.get("revision"),
                    entrypoint="gui",
                )
            elif path == "/api/workflows/import-profile":
                profile = workflow_profile(self.server.workspace)
                result = save_draft(
                    self.server.home,
                    payload["session_ref"],
                    {"profile": profile},
                    expected_revision=payload.get("revision"),
                    entrypoint="gui",
                )
            elif path == "/api/workflows/assign-project":
                result = tanaoroshi.assign_project(
                    self.server.home,
                    payload["session_ref"],
                    payload["case_ref"],
                    expected_revision=payload["revision"],
                )
            elif path == "/api/career/contexts":
                result = cases.create_career_context(
                    self.server.home,
                    payload["label"],
                    context_kind=payload["context_kind"],
                    relationship=payload["relationship"],
                    role=payload.get("role"),
                    summary=payload.get("summary"),
                    period=payload.get("period"),
                )
            elif path == "/api/career/projects":
                result = cases.create_project(
                    self.server.home,
                    payload["parent_ref"],
                    payload["label"],
                    role=payload.get("role"),
                    scope=payload.get("scope"),
                    summary=payload.get("summary"),
                    period=payload.get("period"),
                    external_use=payload.get("external_use"),
                )
            elif path == "/api/career/propose":
                result = cases.propose_canonical_case(self.server.home, payload["case_ref"])
            elif path == "/api/career/approve":
                result = cases.approve_canonical_case(
                    self.server.home, payload["case_ref"], payload["proposal_ref"]
                )
            elif path == "/api/career/organize":
                context_ref = payload["context_ref"]
                if context_ref.startswith("canonical:"):
                    context_id = context_ref.removeprefix("canonical:")
                else:
                    context_record = cases.get_case(self.server.home, context_ref)
                    if context_record["kind"] != "career_context":
                        raise ValueError("context_ref is not a career context")
                    context_id = context_record["metadata"].get("context_id")
                    if not context_id:
                        raise ValueError("context_ref is not confirmed")
                project_ref = payload.get("project_ref")
                if project_ref is None:
                    result = cases.ensure_canonical_context_case(self.server.home, context_id)
                else:
                    if not project_ref.startswith("canonical:"):
                        raise ValueError("project_ref is not a canonical organizer ref")
                    result = cases.ensure_canonical_project_case(
                        self.server.home,
                        context_id,
                        project_ref.removeprefix("canonical:"),
                    )
            elif path == "/api/career/assign-project-context":
                context = cases.get_case(self.server.home, payload["context_ref"])
                if context["kind"] != "career_context":
                    raise ValueError("context_ref is not a career context")
                project_ref = payload["project_ref"]
                if project_ref.startswith("canonical:"):
                    context_id = context["metadata"].get("context_id")
                    if not context_id:
                        raise ValueError("confirm the career context first")
                    result = cases.ensure_canonical_project_case(
                        self.server.home,
                        context_id,
                        project_ref.removeprefix("canonical:"),
                        explicit_selection=True,
                    )
                else:
                    result = cases.assign_project_context(
                        self.server.home,
                        project_ref,
                        payload["context_ref"],
                        expected_updated_at=payload["updated_at"],
                    )
            elif path == "/api/applications/companies":
                result = cases.create_company(self.server.home, payload["label"])
            elif path == "/api/applications/positions":
                result = cases.create_application(
                    self.server.home,
                    payload["company_ref"],
                    payload["label"],
                    jd=payload.get("jd"),
                    evidence_refs=payload.get("evidence_refs"),
                    document_kinds=payload.get("document_kinds"),
                    source_refs=payload.get("source_refs"),
                )
            elif path == "/api/applications/research":
                result = artifacts.register_artifact(
                    self.server.home,
                    case_ref=payload["case_ref"],
                    kind="company_research",
                    body=payload["body"],
                    source_refs=payload.get("sources"),
                    generated_by={"entrypoint": "gui", "workflow": "company_research"},
                )
            elif path == "/api/applications/documents":
                document_type = payload["document_type"]
                if document_type not in APPLICATION_DOCUMENT_TYPES:
                    raise ValueError("unsupported application document type")
                application = cases.get_case(self.server.home, payload["case_ref"])
                if application["kind"] != "application":
                    raise ValueError("application document requires an application")
                evidence_refs = cases.application_evidence_refs(
                    self.server.home,
                    application.get("metadata", {}).get("evidence_refs", []),
                )
                result = artifacts.register_artifact(
                    self.server.home,
                    case_ref=application["case_id"],
                    kind=document_type,
                    body=payload["body"],
                    evidence_refs=evidence_refs,
                    source_refs=payload.get("sources"),
                    generated_by={"entrypoint": "gui", "workflow": "application_document"},
                )
            elif path == "/api/cases":
                result = self._create_case(payload)
            elif path == "/api/cases/archive":
                result = cases.archive_case(
                    self.server.home,
                    payload["case_id"],
                    expected_updated_at=payload.get("updated_at"),
                )
            elif path == "/api/cases/restore":
                result = cases.restore_case(
                    self.server.home,
                    payload["case_id"],
                    expected_updated_at=payload.get("updated_at"),
                )
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
            self._api_error(
                ValueError("invalid request"),
                fallback_code="INVALID_INPUT",
                fallback_status=HTTPStatus.BAD_REQUEST,
            )
            return
        except Exception as exc:
            self._api_error(
                exc,
                fallback_code=(
                    "APPROVAL_FAILED"
                    if path in {"/api/approve", "/api/workflows/approve", "/api/career/approve"}
                    else "SAVE_FAILED"
                ),
            )
            return
        if path.startswith("/api/workflows/") or path in {
            "/api/draft", "/api/checkpoint", "/api/proposal", "/api/approve",
        }:
            result = tanaoroshi.present(result)
        elif path == "/api/career/propose":
            result = cases.present_review(result)
        elif path == "/api/career/approve":
            result = {"approved": True, "record": cases.present_case(result["case"])}
        elif path in {"/api/career/contexts", "/api/career/projects", "/api/career/organize", "/api/career/assign-project-context", "/api/cases", "/api/applications/companies", "/api/applications/positions"}:
            result = cases.present_case(result)
        elif path in {"/api/applications/research", "/api/applications/documents"}:
            result = {"saved": True}
        self._json(result)

    def _start_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        workflow = payload.get("workflow", "career_inventory")
        profile = None
        if workflow == "self_analysis":
            try:
                profile = workflow_profile(self.server.workspace)
            except Exception as exc:
                if getattr(exc, "code", None) != "PROFILE_NOT_FOUND":
                    raise
        session = create_session(
            self.server.home,
            workflow=workflow,
            entrypoint="gui",
            case_ref=payload.get("case_ref"),
            subject=payload.get("subject"),
        )
        if profile is not None:
            save_draft(
                self.server.home,
                session["session_id"],
                {"profile": profile},
                expected_revision=0,
                entrypoint="gui",
            )
        return resume_session(self.server.home, session["session_id"])

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
        if kind == "career_context":
            return cases.create_career_context(
                self.server.home,
                payload["label"],
                context_kind=payload["context_kind"],
                relationship=payload["relationship"],
                role=payload.get("role"),
                summary=payload.get("summary"),
                period=payload.get("period"),
                source_refs=payload.get("source_refs"),
            )
        if kind == "project":
            return cases.create_project(
                self.server.home,
                payload["parent_ref"],
                payload["label"],
                project_id=payload.get("project_id"),
                external_use=payload.get("external_use"),
                role=payload.get("role"),
                scope=payload.get("scope"),
                summary=payload.get("summary"),
                period=payload.get("period"),
                evidence_refs=payload.get("evidence_refs"),
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
        token = payload.get("token")
        if not token:
            # A reload: the bootstrap token was spent and its fragment erased, but the cookie is
            # still valid. Hand back that session's CSRF token instead of stranding the page.
            csrf_token = self.server.security.session_csrf(self.headers)
            if csrf_token is None:
                self._error(HTTPStatus.FORBIDDEN, "no bootstrap token and no local session")
                return
            self._json({"csrf_token": csrf_token})
            return
        exchanged = self.server.security.exchange(token)
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
    language: str = "ko",
) -> GuiServer:
    """Bind only to loopback; port 0 lets the OS choose a free port."""
    return GuiServer(port, home=home, workspace=workspace, as_of=as_of, language=language)


def serve(
    *,
    port: int = 0,
    no_browser: bool = False,
    home: Any = None,
    workspace: str | None = None,
    as_of: str | None = None,
    language: str = "ko",
) -> dict[str, str]:
    """Run the server until interrupted and return its launch metadata."""
    server = create_server(
        port=port,
        home=home,
        workspace=workspace,
        as_of=as_of,
        language=language,
    )
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
