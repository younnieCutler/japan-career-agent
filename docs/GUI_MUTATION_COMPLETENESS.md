# GUI mutation completeness

Handoff. Verified against `c317596` (main, 2.11.1) on 2026-08-14.

## The requirement

> Every user-managed record must support Create / Read / Edit / Archive-Restore from the GUI, and
> any Create or Update of canonical evidence must pass through Review → explicit Approve.

Today the product is **Create → Confirm → Read**. The missing loop is
**Read → Edit → Review changes → Approve revision**.

This is a product defect, not a convenience gap: the local Career Vault is the GUI's own data. If
correcting a typo, a period, a role, or a confidentiality decision after confirmation requires
dropping to the CLI, the GUI is a partial frontend rather than a peer entrypoint.

Not negotiable while doing it: canonical evidence is never `PUT` over. Delete stays archive /
restore / supersede. The approval gate keeps rendering the **server's** proposal with a
before/after, not the form's own state.

## Verified state — four corrections to the intake table

The intake table was right that Edit is missing everywhere. It was wrong about *where* the gap
lives, and that changes the cost of each item by an order of magnitude.

| Entity | Intake | Verified | Where the gap actually is |
|---|---|---|---|
| Career Context | Edit ❌ | Edit ❌ **in the GUI only** | `command_line.py:239` — `add-context --context-id` already updates in place. The runtime can do it; `server.py:499` calls `cases.create_career_context` with no id. |
| Project | Edit ❌ | Edit ❌ **in the GUI only** | `command_line.py:216` — `add-project --project-id` already updates. `server.py:509` calls `cases.create_project` with no id. |
| Experience | 확정 후 Edit ❌ | Edit ❌ **everywhere** | No revision model exists. The ledger is append-only; `approve` appends `status="confirmed"` (`lifecycle.py:481`). `superseded` is in `EVENT_STATUSES` but `personal_timeline.py:8` states it is declared and never written for events — only *facts* carry `supersedes` (`proposals.py:629`). |
| Company / Application / Research | Edit ❌ | Edit ❌ **everywhere** | `case_store.py` exposes create / archive / restore / delete / propose / approve / link. There is no `update_case`. |
| Archive/Restore | "제한적" | **Already present and consistent** | `CareerForms.jsx:244` and `Applications.jsx:309` are two copies of the same `LifecycleControl`; sessions have their own at `Chronology.jsx:142` and `Work.jsx:233`. The defect is duplication, not absence. |

One thing already works in our favour for the hardest item: **reads already exclude superseded
rows.** `experiences.py:129` filters to `status == "confirmed"`, and the comment there anticipates
exactly this ("a superseded row is history that a later record replaced"). The read side of a
revision model is largely built. The write side is not.

## Work, in cost order

### A. GUI passthrough — Context and Project edit

Runtime capability exists. This is wiring plus a form.

1. `server.py` `/api/career/contexts` and `/api/career/projects`: accept an optional existing id and
   route to the updating runtime path rather than `cases.create_*`. Keep the id **optional** so the
   create path is unchanged.
2. `CareerForms.jsx`: `AddContext` (:69) and `AddProject` (:151) already hold every field. Give each
   an edit mode seeded from the selected record rather than writing a second form.
3. `Career.jsx`: `ContextRecord` (:177) and `ProjectRecord` (:252) get the Edit affordance.
4. The result is a proposal, so it lands in the existing `ConfirmRecord` (`CareerForms.jsx:206`)
   review path. **Confirm the before/after actually renders for an update** — that surface was
   built for creation, where "before" is empty.

The question this phase turned on is settled: an id **never mutates**. `experiences.py:149`
documents it — "Propose a project, or an update to one that already exists… goes through the same
proposal the rest of the ledger uses" — and the return payload carries `updates_existing`. Both
functions also already take `case_ref`, which is how a proposal stays linked to the GUI's case
record. Phase A is wiring, not a new write path.

### B. New runtime capability — Company / Application / Research edit

`case_store.py` needs an update that follows the module's existing shape:

- validate through `_validate_case`;
- carry the revision the caller read, and reject a mismatch with `REVISION_STALE` the way every
  other write does;
- for a case with a canonical counterpart, go through `propose_canonical_case` /
  `approve_canonical_case` rather than writing the canonical record directly.

Then `server.py` route, then Edit on `CompanyRecord` (:390) and `PositionRecord` (:338).

Which fields are mutable metadata versus canonical evidence has to be decided per field, not per
entity. A company label is metadata. Selected evidence refs on an application are not — they are
already gated by `application_evidence_refs` and must stay gated.

### C. New domain model — revising a confirmed Experience

The largest item and the one to design before writing code. It is a runtime task; React is the last
step, not the first.

A revision should append a new work event that supersedes its predecessor and mark the predecessor
`superseded` — which is what `EVENT_STATUSES` already anticipates and what the fact timeline
already does for facts (`personal_timeline.py:188-218`, including its "a superseded fact must be…"
and "superseded by more than one confirmed fact" guards). Copy that model rather than inventing a
second one.

Questions that must be answered before implementation:

- Does a revision require its own evidence, or does it inherit the predecessor's? Approval already
  refuses a confirmed event with no evidence (`lifecycle.py:468`), and `NUMERIC_CLAIM` still
  applies to the new text.
- What happens to documents and applications that already quoted the superseded event? The
  reuse rules live in `application_evidence_refs`; a revision must not silently change what a
  generated document claimed.
- Readiness counts confirmed events (`views.py:288`). Superseding must not double-count.
- Can a superseded event be restored? The fact model's answer is the default answer.

### D. Consolidation

Fold `CareerForms.jsx:244` and `Applications.jsx:309` into one `LifecycleControl`. Two copies of a
destructive-action confirmation is two places to get the confirmation copy wrong. Do this **before**
extending archive/restore to any new surface, not after.

### E. Test contract

Per entity: `Create → Read → Edit → Confirm → Reload → Archive → Restore`, asserted against the
server, not against JSX text.

Note what the dropdown regression (#80) taught: a text search over `frontend/src` cannot tell
whether a control works. Edit affordances are exactly the kind of thing that can be present in the
source and unreachable on screen. The E2E must drive the API; `frontend/` now also has vitest +
jsdom for anything that is genuinely about the component.

Register every new `test_*.py` in `scripts/run_all_checks.py` — `check_test_registration.py` fails
the matrix otherwise, which is the intended behaviour.

## Sequencing

A → D → B → C. A proves the review-an-update path end to end on the cheapest entity, D removes the
duplicate before more surfaces depend on it, B repeats A's pattern with a new runtime function, and
C is designed with three working examples of the pattern already in the tree.

E is written alongside each, not at the end.

## Explicitly out of scope

Another redesign. The split pane, dense index, `/diagnosis`, and SEED stay as they are. This work
adds a verb to existing screens; it does not move anything.
