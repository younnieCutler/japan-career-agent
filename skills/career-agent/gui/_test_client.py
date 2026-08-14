"""One view of the browser client, for tests that assert client-wide contracts.

Several contracts are about what the client as a whole does — it reads through `/api/...`, it never
assigns markup, it never touches `localStorage` — not about which module happens to host the code.
Asserting those against a single filename made them fail on a rename and, worse, let a violation
hide by moving into a module the test did not read.

The client is now a React application built from `frontend/src`. Contracts are checked against that
source rather than the built bundle: a minified bundle cannot be searched for an intent, and the
source is what a reviewer actually reads. `built_client()` is available for the few checks that are
about what ships.

The underscore keeps this out of `test_*.py` discovery.
"""

from __future__ import annotations

from pathlib import Path

from gui.templates import STATIC_ASSETS, static_asset


FRONTEND_SRC = Path(__file__).resolve().parents[3] / "frontend" / "src"


def client_modules() -> list[Path]:
    """Every hand-written client source file, sorted for stable output."""
    if not FRONTEND_SRC.is_dir():  # pragma: no cover - only when the checkout is partial
        return []
    return sorted(
        path for path in FRONTEND_SRC.rglob("*")
        if path.suffix in {".js", ".jsx"} and path.is_file()
    )


def client_source(*, exclude: tuple[str, ...] = ()) -> str:
    """Concatenate the client's own source so a new module is covered automatically."""
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in client_modules()
        if path.name not in exclude
    )


def built_client() -> str:
    """The shipped bundle, for contracts about what actually reaches the browser."""
    return "\n".join(
        static_asset(name).decode("utf-8")
        for name in sorted(STATIC_ASSETS)
        if name.endswith(".js")
    )
