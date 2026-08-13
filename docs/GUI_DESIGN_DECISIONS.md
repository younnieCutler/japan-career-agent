# Local GUI product design and implementation contract

This is the durable design source of truth for the local Career Agent GUI. It covers design
direction and the UI implementation contract. Repository data, approval, trust, and architecture
rules remain authoritative when they constrain an interaction.

## Operating mode and product goal

The redesign is a mixed workflow: audit the shipped GUI, retain its safety properties, then replace
its storage-shaped interface with a task-shaped career product.

The primary user is a person maintaining career evidence across jobs, projects, self-analysis, and
applications. Success means they can answer three questions without learning the repository model:

1. What should I do next?
2. Which employer or life context and project does this experience belong to?
3. What is a draft, what needs review, and what is already part of my confirmed record?

The GUI remains local-first, dependency-free at runtime, and unable to browse, invoke an LLM,
submit an application, or bypass approval.

## Baseline audit

The 2.9.2 GUI was inspected in a real browser at 320, 375, 768, and 1440 CSS pixels. The following
findings are design inputs, not a description of the target state.

| Severity | Finding | Required correction |
|---|---|---|
| P0 | The document declares Korean while most of Home and several screens are English or Japanese. | One active locale controls the shell, content, errors, controls, and accessibility text. |
| P0 | A 320/375px viewport produces page-level horizontal overflow; navigation labels collapse into vertical letter stacks. | No page overflow at 320px; use a mobile navigation pattern with 44px targets. |
| P0 | A stale browser can overwrite a newer draft because writes carry no revision. | Every mutable workflow write uses optimistic concurrency and returns a recoverable stale-revision error. |
| P0 | Projects are deliberately parentless, so the user cannot know which employer or context owns new work. | New project drafts require an explicit career context; legacy parentless projects remain readable and repairable. |
| P1 | Home reports counts and internal readiness dimensions but provides no action. | Every important card opens the exact work, review, or recovery surface it describes. |
| P1 | Entered fields are labelled `Confirmed`; metrics are presented as required. | Separate input completeness from lifecycle; qualitative, not-measured, and unknown outcomes are valid. |
| P1 | The first active session is resumed silently when several exist. | Show all resumable work with human context and explicit continue/review/archive actions. |
| P1 | `Cases`, artifact kinds, evidence refs, source refs, and CLI handoff commands dominate application work. | Present target companies, positions, JD, research, sources, and documents; keep storage metadata behind the boundary. |
| P1 | Views replace the DOM without changing URL or history; reload returns Home. | History, back/forward, reload, and useful deep links preserve the logical view. |
| P1 | Self-analysis is a read-only profile dump plus a separate checklist/CLI handoff. | Use the shared workflow store and canonical SELF_ANALYSIS_PROFILE shape for start, resume, review, proposal, and approval. |
| P1 | Broad exception handlers erase invalid-input, stale, corruption, and read/write distinctions. | Preserve machine error codes and render localized, action-specific recovery. |
| P2 | Hover can look like the current view after a DOM replacement. | Current location has a persistent non-hover marker and `aria-current`. |
| P2 | Repeated navigation and DOM builders make screen order and terminology drift. | One shell, one route table, one translation catalog, and feature-owned render modules. |
| P2 | The empty Timeline is a read-model endpoint rather than useful navigation. | Career History groups contexts, projects, and experiences; Timeline is a filterable view of the same model. |

## Product structure

The global information architecture follows user tasks:

| Area | Route | User purpose |
|---|---|---|
| Home | `/` | Resume work, review pending items, resolve failures, and start the next useful task. |
| Career History | `/career` | Browse by employer or non-work context, then project and experience. |
| Work in progress | `/career/in-progress` | See every active draft or review item with context and remaining work. |
| Timeline | `/career/timeline` | Navigate dated career history without exposing ledger records. |
| Self Analysis | `/self-analysis` | Start, resume, review hypotheses, and confirm the canonical profile proposal. |
| Applications | `/applications` | Manage target companies, positions, JD, research, sources, and selected evidence. |
| Documents | `/documents` | Find application documents and whether their inputs are current. |
| Workflow | `/work/:session_id` | Continue or review one semantic workflow. The opaque id may exist in the URL but is never required as user vocabulary. |

Career History is the primary answer to “What does Career Agent currently know about my career?”
It is more central than Timeline: the default view groups employers or non-work contexts, then
employment, projects, and experiences. Each row shows draft, review pending, or confirmed state and
links directly to unfinished work, review, or the confirmed experience. Timeline is an alternate
chronological lens over the same history, never a second history the user must mentally reconcile.

Career History and Applications provide text search plus meaningful filters. Career search covers
employer, context, project, experience, period, and lifecycle; application search covers target
company and position. Large collections use collapsed hierarchy, result counts, and progressive
disclosure instead of rendering every record as an expanded card.

Desktop uses a stable side rail. At narrow widths the same five top-level destinations become a
fixed bottom navigation with short localized labels. Secondary views use in-page tabs or filters,
not additional global destinations.

## Career organization and data boundaries

The user-facing hierarchy is:

```text
Career context
  Employer, university, volunteer group, personal work, or another real setting
    Project or other experience container
      Experience / achievement
        role · situation/problem · actions · individual contribution
        outcome · optional metrics · evidence · confidentiality
```

Three similarly named company concepts stay separate:

- A past or current employer is a career context and may own project drafts.
- A target company is application metadata and may own positions/applications.
- A canonical `experience_context` or `project` is confirmed ledger state created only through the
  existing proposal and approval path.

Application storage keeps the historical `company` case kind as a target-company record. A new
`career_context` case kind organizes employer and non-work drafts. A new project case points to a
career-context case. Existing parentless project cases remain readable and appear in a repair
state; strict new writes never create another ambiguous project.

Confirmed history remains a projection over canonical `experience_context`, `project`, and evidence
events. Case metadata organizes drafts and application material; it is never treated as evidence.

While editing, a persistent context header shows employer or non-work context → project →
experience. Changing that context is deliberate and warns about unsaved work. Creation searches for
possible duplicate contexts, projects, and experiences before offering a new record; it never
silently merges them.

Dates support the precision the source actually has: year, year-month, exact date where already
supported, currently active, and explicitly unknown. The UI never invents a day. Overlapping
employment or project periods are shown as reviewable facts rather than automatically treated as an
error.

## State model

The GUI displays three independent axes.

Input state:

- `not_entered`
- `entered`
- `needs_review`
- `explicitly_unknown`
- `not_applicable`

Workflow state:

- `draft`
- `review_pending`
- `completed`
- `archived`

Canonical lifecycle:

- `unconfirmed`
- `pending_approval`
- `approved`

`entered` never renders as approved or confirmed. `Unknown` is not an error. Outcome capture offers
quantitative, qualitative, not measured, and unknown; only the first requires metrics.

Immediately before approval, the review surface renders the exact proposed canonical snapshot in
plain language: what will be confirmed, what remains unknown, the evidence that supports each
claim, and the effect of approval. An update also shows a human-readable before/after comparison
for changed fields. Proposal references and event terminology remain hidden unless debug mode is
explicitly enabled.

Evidence is presented as material that supports or helps recall a career claim. The user can see
which experience it supports, whether evidence is present or missing, whether it is confidential,
and that a well-described qualitative outcome remains usable without invented numbers. Internal
evidence references are not primary labels. Confidentiality has localized explanatory copy and a
persistent visible state; sensitive content is not repeated in summaries that do not need it.

Contextual guidance stays brief: individual contribution separates the user's work from the team's;
qualitative outcomes are valid; evidence helps verify or recall a claim later; Unknown is an honest
state rather than a failure.

Autosave renders `saving`, `saved`, or `failed`. Navigation waits for an in-flight save or asks the
user to stay when it failed. The implementation word `checkpoint` is not user-facing.

## Host-neutral workflow contract

`skills/career-agent/sessions.py` remains the APPLICATION owner. The current session schema is
general rather than GUI-specific and persists only semantic continuation state:

- workflow, stage, workflow status, and originating/last entrypoint;
- completed sections and unresolved or missing items;
- career-context, project, experience, application, or profile subject references and labels;
- draft reference, pending proposal references, next action, revision, and updated time.

It never stores a chat transcript or chain of thought.

Every mutation supplies the revision it read. A mismatch returns `REVISION_STALE` without changing
the newer record. Reads are tolerant: v1 `tanaoroshi` sessions migrate in memory to the generalized
career-inventory shape, and future schemas refuse with upgrade guidance. Writes emit only the
current schema. Completed work is immutable; archive/abandon is explicit and recoverable metadata,
not deletion of canonical evidence.

Destructive lifecycle actions are secondary, require a consequence explanation, and restore focus
to a useful location. Accidentally created drafts can be abandoned or archived and recovered where
the store supports it. Canonical evidence is never casually deleted; rejection and abandonment are
distinct from permanent removal and retain the audit trail required by the existing model.

When exactly one workflow matches a continuation intent, a host may resume it directly. Otherwise
the shared listing returns human context so GUI, CLI, Claude, and Codex can ask the user which work
to continue without making them handle an id.

## Localization contract

Korean, Japanese, and English are first-class locales. A single server-owned catalog is exposed to
the presentation layer. UI modules use keys and interpolation; they do not contain prose variants.

The active locale controls:

- `<html lang>`, title, shell, global and local navigation;
- headings, field labels, statuses, errors, empty/loading states, buttons, and accessibility text;
- presentation mappings for canonical enums and schema fields.

Stored values remain unchanged. Missing catalog keys fail tests instead of leaking identifiers.
The locale is represented in the URL so reload and deep links retain it even though every server
launch uses a new loopback origin.

## Error and recovery contract

HTTP APIs return a machine envelope with a stable code, whether the input is safe, and whether a
retry or reload is appropriate. The client localizes it and tells the user what happened, whether
their current input remains on screen, and the next action.

Required distinctions include invalid input, save failure, stale revision, stale proposal,
completed session, newer schema, expired browser session, approval failure, corrupted state,
invalid relationship, and read failure. Broad `.catch()` copy is not an acceptable recovery UI.

Loading, empty, and failed-to-load are three visually and semantically distinct states. An empty
state offers the correct first or next action. After every major successful workflow—saving a
draft, proposing or approving an experience, completing self-analysis, or adding a context,
project, application, or company—the screen states what changed and offers the most likely next
action instead of ending at a success message.

The shell continuously communicates saved/saving/failed state, draft/review/confirmed lifecycle,
cross-entrypoint resumability, and stale/conflict recovery without exposing implementation jargon.
Local-first privacy is explained where the user decides what to store or share, not repeated as
decorative copy on every screen.

## Visual direction

The product should feel like a calm, private career workbook rather than an admin dashboard.

- Warm paper and ink form the base; forest green marks primary actions, amber marks review, and red
  is reserved for conflicts or destructive consequences.
- A locally available editorial serif stack gives page headings character; a language-aware local
  sans stack keeps Korean, Japanese, and English body text highly legible. No hosted fonts load.
- Hierarchy comes from type, whitespace, rules, and nested context breadcrumbs—not decorative
  dashboards, glass cards, gradients, or data-density theatre.
- One compact status rail distinguishes draft, review, and approved without relying on color.
- Motion is limited to state transitions and disclosure, uses CSS, and disappears under
  `prefers-reduced-motion`.

## Responsive and accessibility contract

- No page-level horizontal overflow at 320, 375, tablet, or desktop widths.
- Interactive targets are at least 44 by 44 CSS pixels.
- Landmarks, headings, labels, validation summaries, `aria-current`, live save status, and visible
  focus are present without redundant ARIA.
- Keyboard order follows the visual order; back/forward and reload preserve the logical view.
- Status never depends on color alone. Error focus moves to the summary or first invalid field.
- Dialog focus is trapped and restored. Route changes focus the new page heading; save failures,
  validation errors, and approvals move focus to the result that needs attention.
- Reduced motion, zoom, long localized labels, and empty/loading/error states are verified in the
  rendered application.

## Security and implementation boundaries

- Keep `ThreadingHTTPServer`, random loopback port, Host/Origin validation, fragment bootstrap,
  HttpOnly/SameSite cookie, double CSRF, no-store responses, and the fixed CSP boundary.
- The browser receives no personal data in the initial shell and no internal ids unless a route
  needs an opaque reference. Debug mode remains the only general internal-id projection.
- The GUI calls APPLICATION owners only. It does not parse the ledger, mutate canonical files,
  duplicate domain validators in JavaScript, call an LLM, or browse externally.
- Vanilla ES modules are allowed; no framework, bundler, or runtime dependency is introduced.

## Acceptance gates

The redesign passes only when:

- all catalog locales have identical keys and rendered screens contain no unintended mixed-language
  product text;
- the mandatory first-time, multi-employer, self-analysis handoff, application, interruption, and
  concurrent-editing journeys work against real state;
- rendered QA covers representative new-user, active-user (3 employers, 10 projects, at least 30
  mixed-state experiences, active self-analysis, resumable work, and applications), and heavy-user
  (at least 5 employers, 25 projects, 80 experiences, substantial evidence, and 20 target companies)
  Vault states without an unbounded wall of cards;
- explicit end-to-end evidence covers Claude ↔ Codex ↔ GUI ↔ CLI semantic handoff, stale-write
  rejection, employer and non-company context → project → experience correctness, and pure ko/ja/en
  core rendering before BLOCKING may reach zero;
- a reviewed proposal snapshot is exactly the state the strict approval path commits;
- required desktop/mobile routes render with working keyboard completion, focus restoration,
  history, search/filter, context orientation, and recovery behavior;
- no task-introduced console, boundary, focused-test, full-check, packaging, documentation, or
  release-consistency failure remains;
- browser captures after remediation show every P0/P1/P2 finding above resolved or explicitly
  constrained by an external limitation;
- a final adversarial pass by a non-developer persona finds and fixes meaningful places where draft
  could be mistaken for confirmed, context could be wrong, internal concepts leak, workflows dead
  end, large histories become unnavigable, or mid-flow/cross-entrypoint changes fail unclearly.
