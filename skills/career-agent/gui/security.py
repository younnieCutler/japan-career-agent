"""Loopback browser security primitives for the local GUI."""

from __future__ import annotations

from dataclasses import dataclass
from http.cookies import CookieError as InvalidCookieError
from http.cookies import SimpleCookie
from secrets import compare_digest, token_urlsafe
from threading import RLock
from typing import Mapping


SESSION_COOKIE = "jca_session"


@dataclass(frozen=True)
class Session:
    csrf_token: str


class SecurityState:
    """Own one server's bootstrap token and short-lived in-memory sessions."""

    def __init__(self, port: int) -> None:
        self.bootstrap_token = token_urlsafe(32)
        self._bootstrap_available = True
        self._sessions: dict[str, Session] = {}
        self._lock = RLock()
        self.allowed_hosts = frozenset({f"127.0.0.1:{port}", f"localhost:{port}"})
        self.allowed_origins = frozenset(
            {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
        )

    @property
    def origins(self) -> frozenset[str]:
        return self.allowed_origins

    def host_allowed(self, host: str | None) -> bool:
        return bool(host and host in self.allowed_hosts)

    def origin_allowed(self, origin: str | None) -> bool:
        return not origin or origin in self.allowed_origins

    def exchange(self, token: str | None) -> tuple[str, Session] | None:
        if not isinstance(token, str) or not token:
            return None
        with self._lock:
            if not self._bootstrap_available or not compare_digest(token, self.bootstrap_token):
                return None
            self._bootstrap_available = False
            session_id = token_urlsafe(32)
            session = Session(csrf_token=token_urlsafe(32))
            self._sessions[session_id] = session
            return session_id, session

    def session_csrf(self, headers: Mapping[str, str]) -> str | None:
        """The CSRF token for an already-authenticated cookie, or None.

        The bootstrap token is single-use and the fragment carrying it is erased once spent, so a
        reload arrives with a valid HttpOnly cookie and no way for the page to learn its CSRF
        token again. The cookie is already the credential here: it is SameSite=Strict, the Origin
        check has run, and only a same-origin script can reach this.
        """
        if not self.authenticated(headers, require_csrf=False):
            return None
        cookies = SimpleCookie()
        try:
            cookies.load(headers.get("Cookie", ""))
        except (InvalidCookieError, ValueError):
            return None
        session_cookie = cookies.get(SESSION_COOKIE)
        if session_cookie is None:
            return None
        with self._lock:
            session = self._sessions.get(session_cookie.value)
        return None if session is None else session.csrf_token

    def authenticated(self, headers: Mapping[str, str], *, require_csrf: bool) -> bool:
        cookie_header = headers.get("Cookie", "")
        cookies = SimpleCookie()
        try:
            cookies.load(cookie_header)
        except (InvalidCookieError, ValueError):
            return False
        session_cookie = cookies.get(SESSION_COOKIE)
        if session_cookie is None:
            return False
        session_id = session_cookie.value
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            return False
        if not require_csrf:
            return True
        csrf_token = headers.get("X-CSRF-Token", "")
        return bool(csrf_token) and compare_digest(csrf_token, session.csrf_token)
