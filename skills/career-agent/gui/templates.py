"""Application-owned GUI templates backed by the repository's safe renderer."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from render import fill_slots


SHELL_TEMPLATE = """<!doctype html>
<html lang="{{lang}}">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="referrer" content="no-referrer">
    <title>{{title}}</title>
    <link rel="stylesheet" href="/static/style.css">
  </head>
  <body>
    <a class="skip-link" href="#main-content">Skip to main content</a>
    <header class="masthead">
      <p class="eyebrow">LOCAL / PRIVATE</p>
      <h1>{{title}}</h1>
      <p class="lede">A calm place to collect career evidence, one honest step at a time.</p>
    </header>
    <main id="main-content" tabindex="-1">
      <section class="empty-state" aria-labelledby="welcome-heading">
        <p class="section-label">SECURE SESSION</p>
        <h2 id="welcome-heading">Your local career case is opening.</h2>
        <p id="session-status" role="status">Waiting for the browser session handshake.</p>
      </section>
    </main>
    <script src="/static/bootstrap.js" defer></script>
  </body>
</html>
"""


def render_shell() -> str:
    """Render the data-free shell through the existing escaped slot renderer."""
    return fill_slots(SHELL_TEMPLATE, {"title": "Japan Career Agent", "lang": "ko"})


def static_asset(name: str) -> bytes:
    """Read one packaged static asset without accepting a path from the request."""
    if name not in {"bootstrap.js", "style.css"}:
        raise FileNotFoundError(name)
    return files("gui.static").joinpath(name).read_bytes()


# The self-analysis form is `jiko-bunseki`'s, not the GUI's. A profile is only valid with all
# thirteen required fields present, so there is no partial form to build: a smaller GUI form
# could not produce a profile the validator accepts. Serving the existing dependency-free
# checklist keeps one implementation and one contract test instead of two that drift.
JIKO_ASSETS = {"checklist.html": "text/html; charset=utf-8",
               "checklist_runtime.js": "text/javascript; charset=utf-8"}


def jiko_asset(name: str) -> bytes:
    """Read one packaged jiko-bunseki checklist file. The name is never taken from a request."""
    if name not in JIKO_ASSETS:
        raise FileNotFoundError(name)
    root = Path(__file__).resolve().parents[2] / "jiko-bunseki"
    return (root / name).read_bytes()
