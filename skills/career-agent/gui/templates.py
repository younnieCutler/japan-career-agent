"""Application-owned GUI templates backed by the repository's safe renderer."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from localization import gui_catalog, normalize_language
from gui.judgment_copy import judgment_messages
from render import fill_slots


SHELL_TEMPLATE = """<!doctype html>
<html lang="{{lang}}">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="referrer" content="no-referrer">
    <title>{{title}}</title>
    <link rel="stylesheet" href="/static/app/app.css">
  </head>
  <body>
    <a class="skip-link" href="#main-content">{{skip}}</a>
    <div id="app-root">
      <header class="boot-header">
        <p class="wordmark">{{title}}</p>
        <p class="privacy-note">{{privacy}}</p>
      </header>
      <main id="main-content" tabindex="-1">
        <section class="state-panel state-panel--loading" aria-labelledby="welcome-heading">
          <p class="eyebrow">{{tagline}}</p>
          <h1 id="welcome-heading">{{opening}}</h1>
          <p id="session-status" role="status">{{loading}}</p>
          <span id="boot-error-copy" hidden>{{boot_error}}</span>
        </section>
      </main>
    </div>
    <script type="module" src="/static/bootstrap.js"></script>
  </body>
</html>
"""


def render_shell(language: str = "ko") -> str:
    """Render the data-free shell through the existing escaped slot renderer."""
    locale = normalize_language(language)
    catalog = gui_catalog(locale)
    return fill_slots(
        SHELL_TEMPLATE,
        {
            "title": catalog["app.title"],
            "lang": locale,
            "skip": catalog["a11y.skip"],
            "privacy": catalog["app.privacy"],
            "tagline": catalog["app.tagline"],
            "opening": catalog["home.title"],
            "loading": catalog["state.loading"],
            "boot_error": catalog["error.BROWSER_SESSION_EXPIRED"],
        },
    )


def normalize_gui_language(language: object) -> str:
    """Keep locale policy in the application adapter, outside the HTTP boundary."""
    return normalize_language(language)


def gui_messages(language: object) -> dict[str, str]:
    """Return one complete locale catalog for the data-free browser client."""
    catalog = gui_catalog(language)
    catalog.update(judgment_messages(language))
    return catalog


# The one list of files the server will serve. It was duplicated across the HTTP layer and three
# test modules, so adding a client module meant editing four places and any missed one became a
# 404 only a browser could find. Everything imports this now.
#
# `app/…` is the built React bundle. Vite writes it here rather than to a `dist/` the wheel would
# not ship, and its filenames are fixed rather than content-hashed so this allowlist stays a
# literal set: the server still never takes a path from the request.
STATIC_ASSETS = frozenset({
    "bootstrap.js",
    "app/app.js", "app/app.css",
})


def static_asset(name: str) -> bytes:
    """Read one packaged static asset without accepting a path from the request."""
    if name not in STATIC_ASSETS:
        raise FileNotFoundError(name)
    package, _, leaf = name.rpartition("/")
    anchor = f"gui.static.{package}" if package else "gui.static"
    return files(anchor).joinpath(leaf).read_bytes()


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
