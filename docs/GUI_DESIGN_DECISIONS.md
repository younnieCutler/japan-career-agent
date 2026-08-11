# Local GUI design decisions

This document is the source of truth for the local-first GUI. It records decisions that must stay
true while the seven stacked PRs are built.

## Foundation

1. The GUI uses the Python standard library only: `ThreadingHTTPServer`, server-rendered HTML,
   and small vanilla CSS/JavaScript. FastAPI, Flask, React, npm, bundlers, and new runtime
   dependencies would conflict with the repository's lock, SBOM, and wheel contract.
2. The GUI container is called a `case`. The existing `workspace` meaning is already occupied by
   the job-search projection and CLI compatibility surface.
3. The GUI does not call an LLM. Structured fields belong to deterministic screens; adaptive
   interview work is handed off by displaying a command for the user to run.
4. GUI and CLI are peer entrypoints. They share application owners, never import each other, and
   never let the GUI reach directly into domain modules. The dispatcher has the one directional
   launch bridge for `career-agent ui`.
5. A company and an application are separate `case` records. The pipeline projection remains
   company-scoped and its schema is unchanged.

## Visual direction

The frontend skill review selected exaggerated minimalism: editorial black and warm paper, one
bright accent, strong type scale, and generous whitespace. The local shell uses:

- ink `#18181B`, muted text `#3F3F46`, paper `#FAFAFA`, accent `#EC4899`;
- a readable local font stack with Atkinson Hyperlegible first when installed, without fetching a
  web font at runtime;
- semantic HTML before ARIA, a skip link, visible `:focus-visible`, keyboard-order parity, and
  no emoji icons;
- mobile-first layout with no horizontal overflow, a readable body size, and responsive checks at
  320/375/414/768/1024/1440 widths;
- `prefers-reduced-motion: reduce`, 150–300ms interaction motion when motion is added, and no
  scroll-jacking;
- form labels, semantic input types, inline validation, 44px minimum touch targets, and explicit
  loading/success/error feedback in the write screens introduced later.

These rules are adapted from the reviewed `frontend-design`, `design-first-ui-prompting`, and
`ui-ux-pro-max` guidance. The repository's stdlib-only and security contracts take precedence over
any framework, hosted-font, or component-library suggestion.

## Security boundary

- Bind loopback only and let port `0` choose a free port.
- Accept only `127.0.0.1:<port>` or `localhost:<port>` in `Host`.
- If an `Origin` header exists, accept only the matching local origin; never emit CORS headers.
- Put the one-time bootstrap token in the URL fragment. The server never receives it in the
  request target. External `static/bootstrap.js` exchanges it for an `HttpOnly; SameSite=Strict;
  Path=/` session cookie, then removes the fragment with `history.replaceState`.
- Every future state-changing route requires both the session cookie and `X-CSRF-Token`.
- Every response carries the fixed no-store, referrer, content-type, frame, and CSP headers.
- The initial `/` response is a career-data-free shell. All values inserted into templates pass
  through the existing escaped slot renderer; the GUI does not create another template language.

## Persistence boundary

PR1 writes no career data. Draft/session storage is transient; `case` and artifact metadata are
durable; canonical evidence remains in `02-state` and can only be changed by the existing strict
approval path. The exact durable directory for the latter two is intentionally decided by tests at
PR3, before those records exist.

## Read-only slice

PR2 adds Home and Timeline as authenticated GET views. They compose the existing application read
models only: status, readiness, evidence pool, weekly review, Context → Experience → Evidence,
project timelines, and guided actions. The browser receives no internal identifiers unless
`JAPAN_CAREER_GUI_DEBUG=1`; readiness dimensions remain independent and no composite percentage is
shown. These routes do not write the Vault and POST returns `405 Allow: GET`.
