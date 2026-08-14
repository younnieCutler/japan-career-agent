# UI Specification — Career Workspace

Implementation contract for the frontend rebuild. `DESIGN.md` holds the thesis (棚卸し — a ledger
you keep about yourself); this file holds the measurements. Where the two disagree, `DESIGN.md`
wins and this file is wrong.

## Global Shell

```
+--------+---------------------------+-------------------------------+
| rail   | index pane                | record pane                   |
| 13rem  | minmax(19rem, 24rem)      | 1fr                           |
+--------+---------------------------+-------------------------------+
```

- Top bar `3.5rem`: wordmark, local-only note, language.
- Nav rail collapses to a bottom bar under `900px`.
- Under `900px` the two panes become one view at a time: the index, or the record with a back
  control. The record must stay reachable on a phone — the pane is not a desktop-only affordance.
- Content max width `72rem`; prose measure capped at `62ch`.

**Split ratio deviates from the reference on purpose.** A 50/50 split suits a hero-plus-spec page;
an index does not need half the viewport, and the record does need the room.

## Panel Roles

Each panel has one job, and they are not interchangeable.

| Panel | Job | Density |
|---|---|---|
| Index | scan and locate | dense, one line per record |
| Record | read and act | roomier, grouped facts, actions |

## Index Pane

- One flat list. Contexts, projects, and experiences appear as rows at depth 0/1/2, indented by
  `--s4` per level. **The three-level accordion is gone** — no row hides another row.
- Row anatomy: `[rail] label … chips … period(mono)`. Row height `2.25rem`, hit target ≥ 2.25rem.
- Filter bar above: text search + status + kind. Filters compose.
- Bounded rendering via `boundedList` (`PAGE_SIZE = 25`) with a "show more" control. A new filter
  result resets the depth.
- Selected row: `--attest-wash` background plus a solid left rail. Selection is also in the URL.

## Record Pane

Follows the reference's **specification block** pattern: compact two-column facts, thin dividers,
line-separated rows, restrained tabular presentation.

- `record-header`: title + status chips + period (mono).
- Fact block: `dl` at `minmax(8rem, 0.3fr) 1fr`, hairline between rows.
- Then role-specific sections (below).
- Actions sit at the end of the section they belong to, never in a floating bar.

### Company record

```
[회사명]  확정됨
2019-04 ~ 현재

역할 / 요약 / 기간            <- facts
─────────────────────────
프로젝트 (2)                  <- rows, each linking into the index selection
─────────────────────────
경험 (5)                      <- THE ROLLUP
  • 障害対応フローを作り直した   確정  2024-03   [決済基盤]
  • 監視ダッシュボードの改善     초안  --        [決済基盤]
  [+ 경험 추가]
```

The experience list merges `projects[].experiences[]` with `other_experiences[]` and demotes the
project to a trailing label. This is a **view-level rollup only**: the write path still requires a
project parent (`sessions.py:89`), so `+ 경험 추가` resolves a project before starting a session —
one project auto-selects, several prompt a choice, none directs the user to create one first.
Never invent a project to make the button work.

### Project record
Facts, its experiences, in-progress sessions, lifecycle actions.

### Experience record
Confirmed content, evidence state, external-use constraint. Read-only — editing happens in 棚卸し.

## Typography

Three roles, system faces only (CSP forbids `font-src`, so webfonts are impossible).

| Role | Family | Use |
|---|---|---|
| UI | `--sans` | everything read as prose |
| Record | `--serif` | headings, record titles — small and sparing |
| Figure | `--mono` + `tabular-nums` | dates, periods, counts, versions |

Scale 1.2 ratio: `12 / 13 / 15 / 16 / 20 / 24 / 32px`. Weights 400/600/700 only.

CJK: `word-break: keep-all`, no negative tracking, `line-height: 1.7`, never italic.

## Design Tokens

Space `4px` base, `--s1..--s8`. Radius `2px` and `999px` only. Rail `3px`.
Colours as in `DESIGN.md`: `--attest` indigo (confirmed), `--pending` ochre (waiting),
`--conflict` vermilion (**contradiction only**), draft = dashed, no colour.

## Interaction States

- Hover: background only. Never size, never shadow.
- Focus: `2px --attest` ring, `2px` offset, visible in both schemes, on every interactive element.
- Selected index row: background + rail + `aria-current`.
- Disabled: `--surface-2`, `not-allowed`.
- Transitions `90ms` background/border. Route change `120ms` opacity.

## Empty / Loading / Error

| State | Treatment |
|---|---|
| Loading | `state-panel--loading`, `aria-busy`, left rail `--attest` |
| Empty | dashed border, centred, one sentence + the action that fills it |
| No filter match | same shell, different copy, offers to clear the filter |
| Error | `--conflict` rail, states what happened and whether data changed, retry control |

An empty screen is an invitation to act, not an apology.

## Approval Gate

Materially heavier than any other surface, because it is the only moment canonical state changes.

- `4px --attest` top edge; the only filled indigo button in view.
- Order: where → before → after snapshot → not entered → **still unknown** → evidence → effect.
- `Save` is an outline button. `Approve` is filled. They must never look alike.
- Stale proposals are refused visibly, never silently retried.

## Motion

Route fade `120ms`; background/border `90ms`. Nothing else. No scroll animation, no reveals, no
parallax, no marquees. `prefers-reduced-motion` reduces both to ~0.

A ledger does not animate. Motion here would read as a product trying to feel impressive about
someone's career anxiety.

## Accessibility

- Status never by colour alone — every rail and chip carries a text label.
- Index rows are `button`s, reachable and operable by keyboard.
- Record pane is `aria-live="polite"`; selection changes announce.
- Contrast verified by computing from rendered styles, both schemes, not by eye.

## Performance Constraints

- No dependencies. Stdlib Python, vanilla ES modules.
- Bounded rendering everywhere; no unbounded `map` over Vault rows.
- Detail bodies fetched on demand (`/api/artifact-body`), not eagerly.

## Negative Constraints

Explicitly out, regardless of what any style reference offers:

- Charts, sparklines, gauges, meters, progress rings, completeness percentages.
- Composite scores, rankings, hire probability, AI confidence.
- **`metrics-dashboard` patterns** — this product refuses the question "how am I doing".
- Gradient borders, mesh gradients, gooey blobs, glassmorphism, dither fields, WebGL, laser
  corners, atmospheric backgrounds.
- Skeuomorphic paper texture, stamps, faux aging.
- Invented "technical" ornament: coordinates, fake system markers, version numbers that are not
  real. Metadata rails carry true values (`updated_at`, revision, evidence count) or nothing.
- A hero. The record starts immediately.
- Bento grids.

## Acceptance Criteria

1. All routes render with zero page errors, light and dark.
2. Index shows ≥ 20 records in one 1440×900 viewport without scrolling past the filter bar.
3. Selecting a record updates the URL; reload and back restore the same selection.
4. Company record lists experiences from every project plus context-level ones.
5. `+ 경험 추가` never creates a project the user did not ask for.
6. Every chip and body pair ≥ WCAG AA in both schemes, measured.
7. At 390px the record is reachable and returnable.
8. Full suite green, ruff clean.
