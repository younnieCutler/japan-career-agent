"""Application-owned GUI templates backed by the repository's safe renderer."""

from __future__ import annotations

from importlib.resources import files

from render import render as render_slots


SHELL_TEMPLATE = """<!doctype html>
<html lang="en">
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
    return render_slots({}, {"title": "Japan Career Agent"}, SHELL_TEMPLATE)


def static_asset(name: str) -> bytes:
    """Read one packaged static asset without accepting a path from the request."""
    if name not in {"bootstrap.js", "style.css"}:
        raise FileNotFoundError(name)
    return files("gui.static").joinpath(name).read_bytes()
