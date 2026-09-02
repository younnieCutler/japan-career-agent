# Changelog

## [2.20.0] - 2026-09-02

- Add the Human Oversight foundation for consequential career decisions: an append-only local judgment ledger records the human initial judgment, agent assessment, human final judgment, and later outcome without mutating canonical career evidence. Stored history now fails closed on future schemas, malformed rows, invalid ids/sources, and duplicate or out-of-order phases; same-phase concurrent writes are serialized under the Vault lock, and `Unknown` stays explicit.
- Add the source-level human-first React judgment primitive that keeps agent analysis hidden until the initial human judgment is persisted, guards duplicate pending submits, supports radio-group keyboard navigation, and surfaces human/agent divergence. It is intentionally not wired into production workflows in this foundation slice; deterministic L0-L3 impact policy, localized caller copy, resolved evidence references, and selected L3 wiring remain the next slice, so the shipped GUI bundle is unchanged.

## [2.19.0] - 2026-08-27

- Rename the five Gate D quality Skills to shorter canonical names: `debloat` → `trim`, `factchk` →
  `factcheck`, `hate` → `challenge`, `readchk` → `intent`, and `sip` → `verify`. Runtime routing,
  plan options, package paths, documentation, and tests now use the new names; historical records
  remain untouched.

## [2.18.0] - 2026-08-26

- Check what the registries actually serve. `scripts/test_pyproject_install.py --pypi X.Y.Z` runs the
  existing wheel smoke against the published distribution instead of a locally built one, and asserts
  the installed tree carries the GUI bundle and all eighteen Skill manifests. A new `verify-published`
  job runs it after every publish, followed by the README's own quick-start commands against the
  published npm entry point. Until now every check verified the artifact this repository builds, and
  none could see the one a user downloads — which is how a published wheel carrying a single Skill and
  no GUI coexisted with a README describing eighteen Skills and a local GUI.
- Default `--format` to `human` when both stdin and stdout are an interactive terminal, and to `json`
  everywhere else. The human projections, including `guided`'s interactive menu that reads a choice
  from stdin, were already implemented and unreachable without knowing to ask for them: a first run of
  `guided` printed a state object at someone who had been told it would walk them through recording
  something. Pipes, redirects, `$(...)`, plugin hosts and the test suite are all not a terminal, so the
  machine JSON contract is unchanged for every caller that had one.
- Support Python 3.12 in fact rather than only in the packaging classifiers. `requirements.lock` now
  carries the cp312 wheel hashes it was missing, and the CI matrix has a 3.12 runner, so the one
  advertised version that nothing verified is now the only kind this repository has.
- Fix `_run` in the wheel smoke silently returning `stdout=None`. A tool writing a byte the declared
  encoding cannot decode — `python -m venv` on a Japanese Windows console emits cp932 on stderr —
  kills subprocess's reader thread, and `run()` then reports success having produced nothing.

## [2.17.0] - 2026-08-26

- Stop selecting a reference the message has already ruled out. Reference routing read the whole
  message as one bag of words, so a sentence that named a topic in order to dispose of it — refusing
  it, contrasting it against what was actually wanted, or reporting it already finished — still
  returned that topic's reference, and the request that followed never got a turn. Route matching is
  now scoped to the clauses that are not closing their own subject out, driven by a generic marker
  table in `references/routing.yml` rather than a rule per route. This closed all seven critical
  failures on the frozen routing benchmark (dev 2, holdout 5) and lifted holdout accuracy from
  157/182 to 162/182 with no anti-gaming violations.
- Make the routing benchmark a build condition. `scripts/routing_eval.py --gate` exits non-zero on a
  critical or anti-gaming failure and is registered in the repository check matrix; the benchmark
  previously reported its numbers and failed nothing, which is how seven critical failures sat in a
  passing build. Overall accuracy stays a research target rather than a gate, so a paraphrase the
  benchmark scores as a miss does not block an unrelated change. Fixed alongside it: the evaluator's
  failure output crashed with a `cp932` encoding error on a Japanese Windows console, which would
  have turned a reported gate failure into a traceback.
- Fix a release blocker introduced in 2.16.0. `scripts/check_release_tag.py` carried a second copy of
  the `Current release:` README assertion that 2.16.0 removed from the READMEs, and a second copy of
  the plugin-manifest version read that `sync_version.py` had made a generated copy. Both now route
  through `pyproject.toml`, the file that owns the version. The duplicate survived because every test
  here validated a fixture tree the test itself wrote — so the fixture kept supplying the marker the
  repository no longer had — and `test_release_tag.py` now also validates the real repository, which
  is what makes a rule about a file that no longer exists fail at test time rather than mid-release.

## [2.16.0] - 2026-08-26

- Slim the three README entry points to a landing page and move the advanced CLI, GUI startup,
  release-channel and migration material into `docs/`, in all three languages, behind a new
  documentation hub. Documentation facts that can be derived from code are now gated:
  `scripts/check_docs_drift.py` holds Python versions, skill-table completeness, the Gate D root
  Skills, the repository check count, relative-link resolution and the PyPI absolute-link rule to
  what the code actually says. Three claims had already drifted and are corrected here. The release
  version is owned by `pyproject.toml` and written into the plugin and npm manifests by
  `scripts/sync_version.py`, replacing the hand-matched `Current release` lines.

## [2.15.0] - 2026-08-25

- Complete the Gate D quality policy for company research, strategy work, and document plans.
  `factchk` and `sip` now run only when their fixed conditions are met, while `readchk`, `hate`,
  and `debloat` remain explicit plan options. Paused, failed, blocked, unsupported, skipped, and
  one-retry step states are resumable and auditable through the existing invocation ledger. The
  policy now rejects unsupported root Skills instead of applying a catch-all strategy chain.

## [2.14.0] - 2026-08-25

- Add the selected Paperthin quality primitives as real Host Skills: `readchk`, `factchk`, `hate`,
  and `debloat`. They keep Career Agent's Unknown, provenance, approval, and user-decision rules;
  `hate` and `debloat` remain explicit user-invoked operations, no Quality Skill invokes another,
  and `hate`/`factchk` terminal semantics stop objection or contradiction findings before `sip`.

## [2.13.0] - 2026-08-25

- Add the first host-coordinated Gate D execution plan. A bounded linear plan links the existing
  `skill-open` → Host SOP → `skill-report` lifecycle, persists its current snapshot in the Vault,
  projects terminal result data into the next step without copying it into the snapshot, and
  rejects a terminal report before append when its artifact output contract is not met. The first
  quality consumer is the flat `career-document` → `humanize-japanese-career` → `sip` chain;
  unplanned single-Skill callers remain unchanged.

## [2.12.0] - 2026-08-18

- Add a Skill invocation lifecycle (Skill-First Gate A-C). Routing a message to a Skill and
  actually running it were the same recorded fact before this: `trajectory.act.skill` proved a
  Skill was selected, never that it ran. `routing.select_skill()` now marks a selection
  `status: "selected"` with `invocation: null`, and three new CLI commands close the gap Python
  cannot close on its own — this runtime cannot call an LLM host back, so it cannot execute a
  Skill's SOP and hand back a result synchronously. `skills` lists every installed Skill and
  whether it can run without a host (`deterministic`, `hybrid`, `host_required`); `skill-open`
  opens an invocation before a host runs the SOP, and returns `unsupported` immediately, with no
  dangling record, when a `host_required` Skill is opened from `cli` or `gui`; `skill-report`
  closes an invocation with what actually happened, and refuses to close one twice or one with no
  `started` record. An invocation nobody reports stays open and is surfaced by `status` and
  `doctor` — detected, never prevented, and `doctor` still exits 0 on the finding. All thirteen
  domain Skill manifests (and every file under each one's `references/`) now ship in the wheel and
  sdist, not just `career-agent` and `jiko-bunseki`, so an installed CLI can actually discover what
  `skills` lists. `skill-report --status completed` now requires `--summary`
  (`needs_input`/`needs_approval` too), and `failed`/`blocked`/`unsupported` require `--error`, so
  a terminal status carries some evidence of what happened rather than closing on an empty claim.
  The `skill-open → SOP → skill-report` handoff is now a Tier 0 `AGENTS.md` invariant, not only a
  Tier 1 lazy reference a host might never load; `select_skill()`'s `invoke_with` no longer emits a
  copy-pasteable command that silently closes `host_required` Skills as `unsupported` when run
  as-is — it carries an `--entrypoint HOST` placeholder that fails loudly instead. `hybrid` Skills
  (e.g. `career-maintenance`) now get the same placeholder as `host_required` ones: without it,
  a host following `invoke_with` literally recorded `entrypoint: cli` for work it actually did,
  because `skill-open --entrypoint` defaults to `cli`. The placeholder itself changed from
  `<claude|codex>` to `HOST` — the angle brackets and pipe are shell metacharacters, so pasting the
  old placeholder into an actual shell redirected/piped instead of reaching `argparse`'s rejection;
  `HOST` fails the same way whether passed as an argv list or through a shell. `skill-report --error`'s
  help text now says `blocked/failed/unsupported` instead of just `blocked or failed`, matching what
  `validate_skill_result` has required since the previous round.

## [2.11.9] - 2026-08-16

- Redraw the evidence state on each record row as a dot rather than a coloured left rail. The
  screen had more lines than it had groupings — a rail on every row, inside a bordered split,
  inside a bordered panel — and at that density the left edge read as ruling rather than as state.
  The dot keeps the column and all four rules it carried: a marker per tone, conflict declared
  last so a contradicted-but-approved row still reads as contradicted, draft drawn as a hollow
  ring because a draft is the absence of attestation, and selection never repainting it. The
  boxes it competed with go too, replaced by tinted fills, and focus finally draws the ring the
  design always specified.
- Fix the side navigation marking no screen at all. `aria-current` was passed to a component that
  reads `current` and forwards no unknown attribute, so the open screen reached neither the
  stylesheet nor the accessibility tree; the check guarding this asserted the source spelling and
  stayed green throughout, and now asserts the rendered result.

## [2.11.8] - 2026-08-15

- Refuse to rewrite an artifact version that has already been superseded. Demoting a version
  rewrites its revision, so a caller holding the older value was refused, but re-reading the
  retired row yielded one that matched — enough to build a new current version on the provenance
  of the one already replaced and retire the live document in the same call. The named version
  must still be current, checked under the lock, on both the revision-carrying and the
  unversioned update paths.

## [2.11.7] - 2026-08-15

- Surface on Home the states the runtime had already counted and the screen never read: proposals
  waiting to be approved, and dimensions still unknown. Each is a count and a link to the list it
  came from, never a combined figure — these are different questions and a total would answer none
  of them. A conflict keeps its own callout rather than becoming one more row.

## [2.11.6] - 2026-08-15

- Let the GUI rewrite an application document. A rewrite supersedes the previous version and
  carries over the evidence, sources, and document type it was built on, so correcting the text
  never restates what an already-generated document rests on. The document list now shows only
  the current version of each; superseded ones stay on disk and stay readable by reference.
- Show the approval dialog the record as it will stand after approval rather than the submitted
  change alone, so a field the form does not carry is no longer reported as being cleared.
- Fix `add-project` and `add-context` erasing values the command did not mention. Omitting
  `--role` or supplying only `--to` no longer clears a role or a period start recorded earlier.

## [2.11.5] - 2026-08-14

- Let the GUI revise confirmed experience through the existing Work editor. Approval appends the
  replacement evidence and an immutable supersession audit event; readers exclude only the
  replaced claim, keep prior documents unchanged, and reject stale revisions without a write.

## [2.11.4] - 2026-08-14

- Add revision-protected GUI edits for companies, applications, and company research. Application
  evidence is revalidated before every update; research creates a superseding artifact version.

## [2.11.3] - 2026-08-14

- Use one GUI archive/restore control for Career History and Applications, keeping the same
  confirmation and revision-aware archive/restore request on every surface.

## [2.11.2] - 2026-08-14

- Let the GUI edit approved Career Contexts and Projects through the same append-only proposal and
  explicit approval gate as the CLI. The review now shows the server-projected before/after values,
  and every update rejects a stale revision without changing canonical evidence.

## [2.11.1] - 2026-08-14

- Fix every dropdown in the GUI. The shared control composed SEED's Select without its positioner,
  so the option list rendered inline inside whichever pane held the field and was clipped out of
  sight by that pane's own scrolling. The control looked like fixed text and opened nothing —
  language switching, career status, relationship, context kind, outcome state, external use,
  document type, and the status filters were all affected.
- Check the components that wrap composed design-system primitives by rendering them, not by
  reading their source. The existing client contracts are text searches over `frontend/src`, which
  cannot tell whether a listbox opens; that is why this shipped.

## [2.11.0] - 2026-08-14

- Rebuild the GUI client on React and the SEED design system. The career screen becomes a split
  pane — a dense scannable index beside the selected record — replacing nested disclosure widgets
  that showed two records on a 1440px screen. A company record now gathers its experiences across
  projects, so the project is a label beside the record rather than a level to walk through.
- Add a diagnosis screen for the per-dimension readiness the runtime already computed and no
  screen displayed. It reports one state per dimension with the counts behind it, and states in
  the interface that it does not total them.
- Ship the built client inside the wheel, so `uvx japan-career-agent ui` still needs no Node.
- Verify in CI that the committed client bundle is what the committed client source builds, so
  shipping it inside the wheel cannot silently ship a stale one.
- Fail the verification matrix when a tracked test file is not registered in it.
- Bound the in-progress session list, which rendered every session in the Vault.
- Restore `word-break: keep-all`, without which Korean breaks at arbitrary syllable blocks.

## [2.10.2] - 2026-08-13

- Reject application evidence that is unconfirmed or not approved for external use, including
  document generation from an existing application record.
- Require an approved career context for every project, including legacy-project repair and
  restore, and prevent restoring any child beneath an inactive parent.

## [2.10.1] - 2026-08-13

- Return the visible case reference from generic `/api/cases` creation, matching the company and
  application endpoints and keeping the browser's protected follow-up write usable.

## [2.10.0] - 2026-08-13

- Make Career History the primary GUI surface: employer or non-work context → project →
  experience, with search, lifecycle filters, bounded disclosure, actionable empty states, and
  persistent context while editing.
- Keep Capture → Review → Confirm → Reuse honest. Drafts and pending review are never labelled
  confirmed; the approval dialog shows the exact snapshot, Unknowns, evidence, effect, and
  meaningful before/after changes, while stale screens are rejected by revision and snapshot
  checks.
- Share host-neutral workflow records across Claude, Codex, GUI, and CLI. Add strict CAS writes,
  v0/v1 in-memory migration, future-schema refusal, multi-workflow discovery, archive/restore, and
  interruption recovery without transcripts or host session ids.
- Separate career contexts, projects, experiences, target companies, applications, documents, and
  organizing metadata. Enforce context-kind relationship semantics for company, freelance,
  education, personal, volunteer, internship, part-time, open-source, and other experience.
- Add application evidence selection and local versioned documents. Only explicitly selected,
  approved, externally usable evidence may be reused; confidential content stays redacted and no
  application is submitted.
- Add namespaced ko/ja/en human domain vocabulary for overloaded lifecycle, matching, career,
  evidence, document, source, and pipeline values. Guided output, the status bar, and hook failures
  no longer expose raw canonical codes, internal ids, schema/file terms, or mixed-language stages;
  machine JSON/YAML and stored enums remain unchanged.
- Add NEW, ACTIVE, and HEAVY Vault product fixtures and regression contracts for bounded DOM,
  single-pass reads, keyboard/focus behavior, autosave races, duplicate/destructive safeguards,
  loading/empty/error recovery, and pure localized core output.

## [2.9.2] - 2026-08-12

- Even out eight 棚卸し/Projects screen status lines that read as machine-translated:
  failure messages that all shared one template, a passive-voice "제안이 만들어졌습니다",
  and two pairs of lines that were literal duplicates of each other's phrasing.
  Approval-gate promise wording and paired-verb negatives that may define the GUI's
  no-op contract are left unchanged.

## [2.9.1] - 2026-08-12

- Write the 棚卸し screen in the language its shell declares. The heading and lede were Japanese
  above Korean field labels, and a screen reader announces the whole document as `lang="ko"`.
  棚卸し itself is unchanged: it is the product's term, printed as-is in the Korean README.
- Refuse an approval whose proposal no longer matches the draft on disk (`PROPOSAL_STALE`), and
  render the proposal snapshot beside the button that approves it. The proposal id is stable for a
  session, so an approve call stayed valid across an autosave and could write the older wording.

## [2.9.0] - 2026-08-12

- Register the explicit v0→v1 session migration from the legacy semantic `page` field to the
  current `stage` field without rewriting the stored session.
- Add the read-only `career-agent sessions --format json` view over the shared APPLICATION session
  store, keeping CLI and GUI resume state on the same files without importing GUI modules.

## [2.8.0] - 2026-08-12

- Add a read-only Projects / 재직 중 GUI view that composes confirmed project timelines with the
  user's declared employment and job-search state.
- Protect `/api/projects` with the existing local session boundary and keep it GET-only; the GUI
  does not infer employment, write project history, or expose internal identifiers by default.

## [2.7.0] - 2026-08-12

- Add durable Company and Application case metadata under `03-active/gui/`, keeping multiple
  applications separate without changing the company-scoped `data/pipeline.yml` schema.
- Register digest-named, versioned artifact bodies with evidence/source references and generator
  metadata; archive/delete operations tombstone GUI metadata only and never alter canonical evidence.
- Add authenticated GUI case creation, archival, and artifact registration routes with the same
  local session/CSRF boundary as the existing write screens.

## [2.6.0] - 2026-08-12

- Add a read-only self-analysis view for canonical `SELF_ANALYSIS_PROFILE v2` data, preserving
  independent Unknown states and reviewed-empty lists without a completion score.
- Show a user-owned `jiko-bunseki` or approval-gated `propose-context` handoff; the GUI never
  writes the profile or canonical career context.

## [2.5.1] - 2026-08-12

- Keep the verification matrix's output portable on Windows for the resumable GUI session checks
  and preserve the data-free empty-Vault GUI route contract.

## [2.5.0] - 2026-08-12

- Add the resumable local GUI 棚卸し vertical slice. Autosaved drafts and semantic checkpoints
  live in transient `01-capture/gui/` storage and recover after restart without writing canonical
  evidence.
- Create proposals from explicit work/non-work form input and route approval through the existing
  strict `approvals.approve` → `lifecycle.approve` path. Add strict session schema-version refusal
  and the migration hook for a later v0→v1 migration.

## [2.4.0] - 2026-08-12

- Add a read-only local GUI Home and Timeline. It composes the existing status, readiness,
  evidence-pool, weekly-review, Context → Experience → Evidence, project-timeline, and guided
  action projections without creating a parser, a score, or a second store.
- Protect read routes with the local session, keep them GET-only, hide internal identifiers unless
  `JAPAN_CAREER_GUI_DEBUG=1`, and keep the browser rendering accessible and data-safe.

## [2.3.0] - 2026-08-11

- Add the local-first loopback GUI foundation with a data-free shell, fragment bootstrap token,
  Host and Origin checks, strict session/CSRF boundary, fixed response headers, and packaged
  vanilla static assets. The `career-agent ui` command does not write career data.
- Record the GUI architecture and frontend design decisions, including the peer-entrypoint
  boundary and the stdlib-only implementation constraint.

## [2.2.0] - 2026-08-11

- Split `skills/career-agent/runtime.py` into owner modules. The file held the argument parser, the
  dispatch chain, onboarding, diagnostics, the career views and the experience, document and guided
  orchestration, so every new command had to be added there. It is now imports and re-exports:
  `command_line` owns the parser and the single place a result becomes bytes, `dispatch` maps a
  command to its owner, and `diagnostics`, `onboarding`, `ingest`, `experiences`, `documents`,
  `views`, `approvals` and `guided_flow` own the commands themselves.
- Enforce the façade rather than describe it. `check_career_agent_boundaries.py` now fails if
  `runtime.py` defines a function or a class at all, and if an owner module imports the parser or
  the dispatcher. Checking for definitions instead of for size is deliberate: a line budget is
  satisfied by reformatting, this is not.
- Keep the whole historical import surface. `runtime.__all__` names all 226 exports explicitly, so
  removing one is a visible edit instead of a side effect of moving code. `runtime.main`,
  `runtime.build_parser`, `career_agent.pipeline_file` and `career_agent.os` all still resolve.
- **Narrow one compatibility promise, rather than let it read as broken.** A name resolving through
  `career_agent` and a *binding* redirecting the module that uses it are different promises, and
  only the first survives the split. `patch("career_agent.pipeline_file")` no longer changes where
  an approval writes; patch `approvals.pipeline_file`, the module that resolves it. The only
  patchers were this repository's own tests, so this is stated as a change rather than restored —
  an owner reaching back through the façade for its imports would reintroduce exactly the
  dependency the boundary rules exist to prevent.
- Pin the exit-code contract in a test. A command that answers a question reports the answer in its
  exit code; a command that describes the Vault does not. `doctor` finding problems exits 0, because
  a script that treated a new warning as a crash would stop working the day one appeared, while
  `document-check` failing its gate exits 2, because being gated on is what it is for. The split
  briefly collapsed the two and nothing but this test would have noticed.
- Close the canonical write schemas and leave the read path open. Every object in
  `_shared/schemas.yml` carried `additionalProperties: true`, so `decison_status: proceed` validated
  and was stored as a key nothing would ever read again. `validate_new_write` now checks a strict
  schema derived from the tolerant one in code — `additionalProperties: true` *evaluates* unknown
  keys, so `unevaluatedProperties` would be a no-op and the permissive setting has to be replaced.
  One catalog, two validators, nothing to keep in sync.
- Check the fragment a write introduces, at every depth, rather than the merged result. A top-level
  field check let `jd_requirements`, `action_items` and `history` — all lists of objects — keep a
  typo one level down, and `history=` arrives as its own argument so it bypassed the field gate
  entirely. Validating the merged entry instead would reject keys an older version already wrote,
  making an existing pipeline unwritable rather than upgradeable, so only what the write adds is
  checked and `required` is dropped for the partial update.
- Close an object exactly when the catalog declares its `properties`. Closing on `type: object`
  alone closed the objects the catalog deliberately leaves shapeless — `work_style_reflection` is
  required on every CANDIDATE_PROFILE and any real content in it was being rejected — while missing
  `type: [object, 'null']`, which is how every nullable object here is written. Opaque fields are
  not unvalidated: `matching_v3.validate_allocation` and `self_analysis_profile.py` own their rules.
  The exact set of closed objects is pinned by a test so it cannot drift silently.
- Make the frozen-field list say what the prose already claimed. `top_strengths`, `work_style`,
  `portable_skills`, `wellbeing_scores` and five others were documented as legacy read-only and were
  writable anyway, because the gate reads one flat list that never named them. The list is now
  recorded per schema, every frozen field is a declared property, and a test derives one from the
  other so the two cannot disagree again.
- **Behaviour change worth knowing about:** `scripts/pipeline.py upsert|update --json` passes its
  payload straight to the write gate, so a field the schema does not name is now refused instead of
  silently stored. Existing files are unaffected — this is the write path only, and the error names
  the file to add the field to if it is real. A field that was never declared was also never read by
  anything, which is what made the typo invisible.
- Promote the documented fields from the prose sections into `$defs`, without types. Both
  validators read one property list, so adding a type would newly reject historical records that
  hold a different shape. The schema stops shape drift; value rules stay where they already are.
- Fix three schema-versus-code disagreements that surfaced the moment RULES was validated at all:
  `$defs.RULES` declared an array while `calibrate.py` and `status_bar.py` have always written and
  read a `{rules: [...]}` mapping, `source: observed_workflow` was missing from the enum, and
  `action_items[].checked_at`, written by `check_action.py`, was undeclared. `rules.yml` had never
  been validated, because `mutate()` only checked `pipeline.yml`.
- Reject frozen legacy fields at any depth. MATCH_HISTORY is an array and a pipeline's retired
  scores live inside a company entry, so the top-level-only check reported success while writing
  exactly what it exists to refuse.
- Add `_shared/tests/fixtures/legacy/`: four historical shapes that must keep reading forever. The
  suite asserts they read and that at least one is refused as a new write, so they cannot quietly
  become documents that pass either way.
- Make the first-run vocabulary a contract. `effect_label` returned its input unchanged for anything
  it did not recognize, printing `canonical state` at a user instead of a translation. A test now
  walks `ux.py` for every string reaching `changed=`/`unchanged=` and asserts each has a catalog
  entry, and a second test asserts a `setup → record → status → guided` transcript carries no
  proposal id, event id, store filename or internal term while the JSON keeps them all.
- Lead with `npx japan-career-agent setup` and `uvx japan-career-agent setup` in all three READMEs,
  and separate running once from installing. `npx` is an entrypoint; the canonical runtime is
  Python. The plugins move from a peer install option to `Enhanced integrations`, with what they add
  stated and what works without them stated too.
- Add `docs/CAPABILITY_MATRIX.md`, `docs/ARCHITECTURE_BOUNDARIES.md` and
  `docs/MAINTAINER_RUNBOOK.md`. The matrix is checked, not asserted: every `core` row names a
  command `build_parser()` defines, and `scripts/check_capability_matrix.py` fails the build if one
  does not. Rows that are not equal say so rather than being smoothed over.
- Enforce the three READMEs' shape, not just their contents. `check_readme_consistency.py` was
  substring-only, so a section added to one language passed; it now compares heading-level sequences
  and the install order, and refuses `init` as the first command shown.
- Correct the rename version: 2.1.0, not 2.1.1, which is what `verify_release.py` has always said.
- Extend the wheel smoke to `status` and `guided`. Both cross more of the runtime than `doctor`
  does, so they are what proves an arbitrary-CWD install carries the whole application layer.

## [2.1.1] - 2026-08-11

- Rename the project to `japan-career-agent`. The old name described the work as recruiting, which
  is what the other side of the table does; what this actually holds is one person's career record.
- Keep every artefact published under the old name verifiable. `verify_release.py` accepts both
  product names, permanently: a bundle someone already downloaded cannot be re-stamped, and a
  verifier that rejects it would stop checking the very releases still in circulation.
- Keep an existing opt-out working. `JAPAN_RECRUIT_NO_UPDATE_CHECK=1` still disables the update
  check alongside the new `JAPAN_CAREER_NO_UPDATE_CHECK`. A renamed variable that quietly stops
  being read turns a decision the user made back on without telling them.
- Install without a plugin host. `pyproject.toml` builds a wheel, so `uvx japan-career-agent` and
  `pipx install japan-career-agent` now reach the same runtime the plugin ships. The wheel keeps
  `_shared/` and `skills/career-agent/` in their existing relative positions rather than converting
  them into packages, so the runtime modules are shipped unmodified and the plugin path is
  unaffected.
- Add `npx japan-career-agent` as a discovery channel. The npm package contains an installer and no
  runtime: it locates `uv` or `pipx`, installs the same version of the same PyPI package, and hands
  over. It deliberately does not fall back to `pip install`, which would modify an interpreter the
  user did not name. There is no `postinstall` hook — nothing executes at install time — and no second
  artefact to verify, because the only thing ever fetched is the wheel.
- Fail with instructions rather than a traceback when no runner is present. `npx` with neither `uv`
  nor `pipx` installed is an ordinary first run, and it now prints how to install one and states
  that nothing on the machine was changed.
- Guard the new surface in CI. `scripts/test_pyproject_install.py` builds the wheel, installs it
  into a throwaway environment and runs it from a directory unrelated to the repository, asserting
  that both console scripts work and that `routing.yml` and the built-in templates still resolve.
  `scripts/test_npm_bootstrapper.py` asserts the npm package declares no install-time hook and
  cannot drift from the release version.
- Read the installed package version instead of repeating it in the launcher. A literal that has
  to be kept in step with six other files by hand is the copy that ends up wrong.
- Check the release-channel section of each README against the files that own its numbers. It
  claimed the source version and the stable marketplace ref matched while the marketplace was
  two releases behind, which is the one thing that section exists to answer. Bumping the
  marketplace ref without updating the READMEs now fails.

## [2.0.0] - 2026-08-10

- Add the context an experience happened in. A context is a company, a university, a part-time
  shop, a club or a personal effort, and `kind` is the one required field beyond a label because it
  is the part a later reader cannot recover: an employer and a school are both plausible readings
  of a bare name, and reading a university as an employer puts coursework in a 職務経歴書 as a job.
  It is another type on the same ledger, so durability, the approval gate and append-only history
  come with it, and a context's current state is a projection over its events.
- Record evidence about something that did not happen at a job. A seminar, a thesis, a club, a
  volunteer shift and a personal project carry the same payload a work event does -- role, problem,
  actions, individual contribution, team result, metrics, confidentiality -- and share its
  validator, including the rule that a number must appear in the evidence before it can be
  confirmed. They are a separate type because storing a university seminar as a work event would
  say the user was employed there, and every work-scoped read would start returning coursework as
  work history.
- Group evidence into experiences without storing one. An experience is the confirmed evidence
  naming the same project or the same `experience_ref`, so re-linking a note rewrites no history
  and the same evidence never exists twice to appear in two views. Not every experience is a
  project: regular operations, an improvement, an incident, a thesis and a part-time shift are
  experiences too.
- Add `add-context`, `contexts` and `experiences`. The last is the 棚卸し view: contexts, the
  experiences under them, the evidence under those, and the gaps named one by one. There is no
  completion percentage, because the question it answers is whether a decision can quote the
  user's own experience, and a number would hide which part is missing.
- Normalize the target JD onto the pipeline entry it already belongs to (`schema_version` 2.5):
  `jd_source`, `jd_observed_at`, `jd_digest` and `jd_requirements`, each requirement carrying the
  posting's own words, whether the JD called it required or preferred, and the confirmed event ids
  that support it. Nothing is scraped and no requirement can add a fact: a requirement nothing
  supports stays `Unknown`, and adjacent experience is never promoted to fill it. `jd_digest` is
  what makes a generated document reproducible -- an edited posting reads as a changed digest
  rather than as an unexplained difference between two documents.
- Add the JD-specific document model. It selects and arranges confirmed evidence for one target
  and writes no prose: what it produces is the material a recruiter-facing sentence may be built
  from, slot by slot, with the evidence behind each slot and the claims that sentence may not
  strengthen. Evidence whose confidentiality review has not cleared never enters it, an
  `external_label` replaces the internal project name, and a selection pointing at a draft is
  reported rather than silently dropped. Running it against a different JD moves evidence around
  without changing any of it.
- Add the Career Fidelity Gate. Polished Japanese may say less than the evidence and never more:
  a number that was never measured, an existing number rounded, `支援` becoming `主導`, `参加`
  becoming `全体設計`, a JD keyword arriving as a technology the user never used, a team's outcome
  written as one person's doing, an internal project name leaving the building, or a bullet
  structure merged into prose during polishing — each is a refusal, not a warning. Every check is
  literal string work so that the same draft and the same model always produce the same result;
  a check that varies between runs cannot be relied on as a gate.
  What passing establishes, stated precisely: **no known protected-claim violation reaches a
  rendered document.** The rules are enumerated, so a synonym outside them can still raise a
  claim's strength by a degree — proving the absence of every semantic drift in Japanese is not
  something a list of substrings can do. Meaning-level drift is defended by the humanize contract
  and by the user reading the result before they send it. The verdict field is named
  `protected_claim_violations` for that reason. No detector score is read, reported, or optimised
  for.

- Render the checked document with two built-in templates and no dependency at all. The
  substitution engine understands named slots and repeated blocks and deliberately nothing else --
  no expressions, no conditionals, no evaluation -- because a template is a file the user brought
  from somewhere, and templates carry sample career text and occasionally text addressed to a
  model. Every substituted value is HTML-escaped, so neither a template nor a JD nor a resume can
  become markup, and a template id is a name rather than a path. PDF is the browser's print path
  against the A4 print CSS the templates carry.
- Ship two built-in templates rather than one. `standard-chuto` and `simple-print` render the same
  checked document into different markup, which is what makes "changing the template never changes
  the facts" a claim a test can falsify.
- Refuse to render an unchecked document. `document-render` runs the fidelity gate itself instead
  of trusting that a caller ran it, because the failure it guards against is a document reaching a
  recruiter; on failure nothing is written at all. A truncated or hand-edited model makes the gate
  stricter, never looser: a missing claim means nothing supports the wording.
- Never overwrite a generated document. The filename carries a digest of the evidence, the JD, the
  template and the wording that produced it, so regenerating after a change writes a new file
  beside the old one and regenerating after no change writes nothing. Each file gets a manifest
  recording what it was built from, and an existing document whose evidence or JD has since moved
  is reported as a candidate for regeneration -- reported, never acted on, because overwriting
  something the user may already have sent is not this runtime's decision.
- Keep generated documents out of Git. `career-docs/` is ignored at any depth, and the private-data
  gate now recognizes the romanized filenames the renderer produces; prose *about* writing a
  職務経歴書 still tracks normally, because a gate that fires on its own repository gets bypassed.

- Add `career-document` and `humanize-japanese-career`. The first orchestrates the target: read
  the posting, map its requirements onto recorded evidence, store the selection, generate a model,
  write the Japanese, check it, render it. The second is the expression layer, with a genre
  contract of its own — a general humanizer merges bullets into flowing prose, which destroys the
  one thing a 職務経歴書 is for, and it will happily invent a number to make a vague sentence
  concrete. Detector pass rate is explicitly not a goal and is not measured.
- Capture evidence about something that did not happen at a job with `run --mode chat --non-work`.
  A seminar, a thesis, a club or a volunteer shift asks the same questions a release does and
  fills the same fields, and `review-work-event` now works on either type. It is a stated fact
  about the experience, never inferred from wording: only the user knows whether they were
  employed there.
- Add the end-to-end regression the release gate is defined by. One lifecycle through the real CLI
  — install, vault, 棚卸し, canonical evidence, target JD, selection, model, draft, humanize, gate,
  template, HTML — asserting the two things every layer depends on: career facts are identical
  whichever target asked for them, and generating documents leaves the ledger byte-identical.

- Order employment history newest first. It was sorted on the context id, which is a uuid: the
  order was stable within one vault and arbitrary between any two, and a career history whose
  order means nothing is worse than one in an unusual order. Reverse chronological is the ordinary
  Japanese convention and the only ordering the recorded periods actually support; a context with
  no period sorts last, because an Unknown start is not evidence of a recent one. Found by printing
  a two-employer sample and looking at it.
- Let a draft narrow the proposed skills list. Latin tokens are how technology names travel, and
  they also pick "API" out of 決済API and "OJT" out of OJT計画 -- evidence-backed and useless as a
  skill label. The model proposes, the writer selects, and the gate refuses any label that was not
  proposed, so the list can only ever be narrowed.

- Add `career-tanaoroshi`: キャリアの棚卸し, the workflow that recovers experience from before the
  ledger existed. Contexts first, experiences second, evidence third -- asking which companies
  someone worked at leaves a new graduate with nothing to answer, and asking which projects leaves
  the operations engineer and the researcher with nothing either. Documents the user already has
  are read first and only the gaps are asked about, and everything extracted stays a candidate
  until they confirm it.
- Route 棚卸し ahead of maintenance. Every phrase in the new table carries a scope marker the
  maintenance vocabulary has none of -- 지금까지, これまで, so far -- and that marker is what says
  the request is about the years behind the user rather than about today's work. The entry point
  proposes nothing: a seven-year career summarised from one sentence is the invented history the
  ledger exists to refuse. It also needs no track, for the reason maintenance does not, and never
  reads as intent to leave.

- Report `bootstrap_suggested` in `readiness`, with `career_contexts` and `experience_coverage`
  alongside the existing dimensions. It is the fact that the ledger holds nothing to quote, not a
  threshold on a score, and it does not depend on whether a job search is on: someone with seven
  years of experience and a fresh install is in exactly this state whether or not they intend to
  leave.

## [1.24.0] - 2026-08-10

- Add PROJECT as the context a work event happened in. It is another type on the same ledger, not
  a second store, so durability, the approval gate, and append-only history come with it. A
  project's current state is a projection over its events: later non-null fields win and the rest
  keep what an earlier event said, which is how a record actually gets filled in — named in one
  turn, given a role in another, closed in a third.
- Link work events to projects by reference. `primary_project_id` plus `related_project_ids` means
  one canonical event appears in several project timelines while existing once; the same work is
  never recorded twice to make it show up in two places. `--none` records general work, and no
  project question ever blocks a capture: a work event with no project is valid.
- Add `work_date` to the work-event payload, at month or day precision. `occurred_at` remains what
  it was — when the note was captured — so writing up last June's project today can now say June
  without changing an existing meaning. Absent stays Unknown and nothing guesses a date.
- Add `weekly-review`: the period's work grouped by project, with the gaps worth asking about
  ranked by what changes how the record reads later. It windows on capture time, so a note written
  this week about older work appears here, which is the one most likely to still need a
  contribution and a result.
- Add `projects`, `project-timeline`, `add-project`, and `link-work-event`. Timelines are views
  over the ledger; no duplicated history is stored.
- Add `evidence-pool`: confirmed work events grouped under the projects they belong to, which is
  the read a JD answer starts from. Each row says whether its date was stated or inherited from
  capture time, so an answer cannot present the day a note was written as the day work happened.
- Answer a JD with requirements and the evidence behind them first, and primary experience
  candidates second. No score, no total, no ordering by keyword count — a requirement is
  supported when recorded behaviour matches what it asks for, not when a word repeats.
- Add `primary_project_ids` to the per-company selection. A project may be the headline because
  it is the story a reader follows; the work events under it are what makes it checkable, and a
  project title alone supports nothing.
- Add `maintenance-check`: situations worth mentioning, or none. Everything it reports is
  triggered by something in the record — notes piling up on one project, a closed project with no
  summary, confirmed work where the personal contribution is still Unknown, confidential material
  whose external use was never reviewed. There is no schedule and no reminder, at most one thing
  is meant to be said, and silence is the common answer.
- Show pending captures in `weekly-review` and `maintenance-check`. A quick note is a pending
  proposal until it is approved, so reading only the ledger showed an empty week to someone who
  had been capturing all week — and the unfinished notes are what a review is for. Draft rows in
  the review carry their `proposal_id` so it can act on the row it is looking at. Drafts count
  towards "notes are piling up on this project" and stay out of the checks that describe finished
  records.
- Merge a project's `period` a level deeper, for the same reason `confidentiality` merges: a start
  is learned when the project begins and an end when it closes, and replacing the object on the
  second turn dropped the start.
- Base `readiness` recency on the stated `work_date` alone. Falling back to capture time is right
  for ordering a timeline and wrong for "is this recent": it turned a note written today about
  work from five years ago into confirmed recent experience. Undated evidence reads `Unknown`, and
  `Stale` is reserved for a record where every entry is dated and none is recent — it asserts the
  recent record is empty, which an undated note makes unavailable. Any mix reads `Partial`.
- Add `project.external_label`: the safe name for recruiter-facing output, kept beside the real
  title in the record rather than replacing it. "내부 결제 Phoenix 프로젝트" stays the user's own
  record while "payment reliability project" is what leaves, decided once by the user instead of
  improvised per document. Where a label exists, `job-seeker-agent` and `mock-interviewer` use it
  in place of the title in everything recruiter-facing; a title with no label and possible
  confidentiality is asked about rather than judged harmless.
- Ground `mock-interviewer` in confirmed evidence and the company's recorded selection, so practice
  rehearses the answer the candidate will actually give — including saying "그 부분은 경험이
  없습니다" well where `unknown_requirements` names a real gap.
- Fix `add-project`'s next action, which named the project id where `approve` takes a proposal id.
- Add `readiness`: independent dimensions with no total, and job-search intent reported beside
  them rather than derived from them. A current record is not a decision to leave.
- Add project-end review guidance: draft the summary from the project's own confirmed timeline
  instead of asking the user to explain it again. The summary is a narrative layer and never
  becomes evidence on its own.

## [1.23.0] - 2026-08-10

- Separate career readiness from job-search intent. `employment_status` and `job_search` are the
  user's own declaration in the profile, written only by `set-employment-status` and
  `set-job-search`; `career_mode` is projected from events and cannot reach `active_search` while
  job search is off. No JD review, recruiter message, approved event, or match run can turn job
  search on — the single write path makes that structural rather than a rule to remember.
- Add `career-maintenance`: capture what happened at the current job as reusable evidence while
  employed. It is a prompt skill only; capture, approval, and the append-only ledger are the
  existing `career-agent` runtime.
- Add the `work_event` event type as an extension of the existing event contract rather than a
  second store. `track`, `stage`, and `flow_phase` may be null for it alone: work at the job someone
  already has belongs to no hiring market and to no transition step, and inventing one would move
  their routed state. `individual_contribution` and `team_result` stay separate fields, and the
  existing numeric-claim rule now covers `work_event.metrics`, so a metric with no evidence behind
  it cannot be confirmed.
- Stop asking for a track before a maintenance request. An employed user who is not looking has no
  answer to 新卒/中途; the question returns when a request actually needs one. An opportunity-review
  message now counts as a stated intent at the third onboarding gate.
- Add `review-work-event`, the path that fills a captured work event's structured fields before it
  is confirmed. Capture is one sentence by design and approval only ever accepted evidence,
  deadline, company, compensation, currency, and next_action, so without this the payload stayed
  empty from capture through confirmation and the requirement mapping had nothing to read. Keys
  merge across turns, `--replace` clears a field back to Unknown, and pending is the only editable
  state: a confirmed event is corrected by recording a superseding one.
- Move `career_mode` off inference. It was derived from an event's type and stage, which produced
  two wrong answers: writing a work note while at 面接 with a search underway reset the mode to
  `maintenance`, and routine document upkeep with job search off became `opportunity_review` when
  no opportunity existed. The mode is now carried by the chat turn that read the user's words, is
  absent when they stated no workflow intent, and leaves the stored value alone in that case.
- Add `work-events [--confirmed] [--as-of]` as the read contract downstream skills use. Drafts and
  superseded records are excluded in one place instead of separately in every consumer. Its
  boundary is a UTC date because `occurred_at` is a UTC instant; the previous local-date default
  dropped an event the user had just recorded in the hours after UTC midnight. Note what
  `occurred_at` is: capture time, not when the work happened. A `work_date` on the payload is
  the fix for recency and is not in this change.
- Take the vault lock in `set-job-search` and `set-employment-status`. Both read the profile, write
  it, and may rewrite canonical state, which PERSIST-005 requires to be serialized against a
  concurrent approval.
- Add five intent lexicons — maintenance, opportunity review, active search with a negation veto,
  a decided transition, and closing a review out — beside the four existing routing tables, which
  are unchanged.
- Give `maintenance` a way back. It is the resting state, but work events deliberately do not move
  the mode, so one recruiter message left `opportunity_review` standing indefinitely. Declining an
  opportunity in the user's own words returns the mode to `maintenance`, and closing outranks
  reviewing so "헤드헌터가 보냈는데 안 할래" reads as the decision it is.
- Deep-merge `confidentiality` in `review-work-event`. Its two keys are answered at different
  times — the material is flagged at capture, whether it may leave is decided after review — so a
  shallow merge let a second patch drop `contains_confidential: true` and quietly unflag a
  confidential record. Every other field still replaces wholesale.
- Give `career_mode`'s fourth value, `transition`, a stated signal of its own so the vocabulary has
  no unreachable member: resignation and joining phrases that mean the move is decided. The bare
  stems are deliberately absent, so 退職理由 — an interview question about a past move — does not
  fire it. Unlike `active_search` it does not depend on the job-search flag; someone resigning has
  decided whether or not they ever declared a search.
- Add `routing-eval-v3`: every v2 fixture plus 57 for the intent surface, 36 dev and 182 held out.
  v1 and v2 stay digest-pinned so their recorded results remain reproducible. Evaluator version 2
  is additive; a fixture naming no intent scores exactly as before.
- Add per-company evidence selection to `data/pipeline.yml` (`primary_experience_ids`,
  `supporting_experience_ids`, `unknown_requirements`) at schema 2.4. A JD changes selection,
  ordering, and presentation angle; the event ledger is append-only and is never edited to fit a
  posting. The user's three axes are not copied per company.

## [1.22.0] - 2026-08-08

- Match 학チカ and 학チ카 everywhere. The two spellings of one word were split across the track and
  document lexicons, so a message using either reached only one of them.
- Drop four terms that a bare form already in the same list subsumes — 연봉 시세, new graduate,
  interview prep, and resignation — across seven sites. Behaviour is unchanged by substring
  matching; the lexicon is 216 terms rather than 220.
- Held-out routing correctness 108/134 to 109/134 on `routing-eval-v2`, and 45/56 to 46/56 on the
  retired v1 benchmark, from the first autonomous research run.

## [1.21.0] - 2026-08-08

- Add `routing-eval-v2`: 134 held-out and 26 development routing fixtures, replacing v1's 56 and
  26. v1 stays readable and digest-pinned so its recorded results remain reproducible.
- Rebalance the benchmark's languages. v1 was 66% Japanese, so a Korean or English regression was
  largely invisible; v2 is 76/43/41 across Japanese/Korean/English, enforced by a test.
- Double the axes that carry the safety contract rather than inflating uniformly — negation,
  unmatched, generic interview and research, ambiguity, non-capture, and both track boundaries.
- Scope the experiment log to one benchmark version: a v1 best counts 56 cases and a v2 best counts
  134, so comparing a candidate across versions is meaningless rather than merely noisy.

## [1.20.0] - 2026-08-08

- Add the Routing Autoresearch agent program: the loop protocol, the mutation surface, the gate
  order, and a capsule describing how the routing subject resolves a message. It replaces roughly
  90 KB of source reading per trial with 7.5 KB, and its factual claims are checked against the
  runner so it cannot drift into confidently describing a harness that no longer exists.

## [1.19.0] - 2026-08-08

- Add the `routing-eval-v1` frozen benchmark for Career Agent message routing: 26 development and
  56 held-out fixtures across direct intent, paraphrase, JA/KO/EN, negation, mixed intent,
  precedence, ambiguity, non-capture, and both track boundaries.
- Add the Routing Autoresearch runner, which scores one candidate against that benchmark and
  returns KEEP, DISCARD, CRASH, or INVALID without a human judging each result.
- Gate the loop lexicographically — decision philosophy, safety and non-capture, focused
  regressions, held-out accuracy, fallback preservation, complexity, canonical matrix — so routing
  accuracy can never offset a contract violation.
- Pin every file that decides a verdict — evaluator, runner, and both contract-test files — into
  each results row, so a candidate cannot rewrite the logic that scores it.
- Separate `provisional_keep` from `keep`, and classify a Gate 6 failure the candidate did not
  cause as `infra_error`, so the append-only log never records a verdict it did not earn.
- Route the plain market-rate wordings 相場 / market rate / 시세 to the market-positioning
  reference, the first improvement the loop produced (held-out 43/56 → 44/56).
- Match the bare お礼 in place of three compounds of it, the second (held-out 44/56 → 45/56 with
  three fewer routing terms).

## [1.18.1] - 2026-08-08

- Route ten specific chuto execution topics to exactly one existing `tenshoku-strategy` reference
  while preserving lifecycle routing and generic stage fallbacks.
- Reuse the same selected skill context in the chat response and persisted trajectory.
- Record the narrow D-1 experiment and defer or cut the other four-skill evolution candidates.

## [1.18.0] - 2026-08-08

- Onboard a new Career Agent Vault progressively: confirm the track, the shinsotsu graduation year,
  and the task the user wants to start, then route to the existing domain skill for that task.
- Read a stated graduation year (`27卒`) back into the question with the `setup` command that would
  record it, instead of writing an unapproved career fact.
- Separate applying to a posting from reviewing one: `応募`/`지원`/`apply` routes to the application
  workflow, while a bare `求人`/`공고`/`JD` routes to job-seeker-agent evidence review.
- Route "I don't know what to do" to self-analysis without treating it as a recommendation, and only
  when the message names no more specific task.
- Classify `第二新卒` as a `chuto` mid-career hire.
- End onboarding when a turn reaches a real stage (`career_status` becomes `active`).
- Show onboarding progress and an `Unknown` target role in guided output instead of reporting
  onboarding as a setup failure.

## [1.17.3] - 2026-08-08

- Skip `.worktrees` (gitignored `git worktree add` checkouts) in `scripts/check_policy.py`.

## [1.17.2] - 2026-08-06

- Make the stable Codex marketplace channel resolve to the immutable `v1.17.1` tag.
- Keep read-only `status`, `doctor`, and proposal inspection available when a pending approval
  journal needs repair; write-capable commands still recover before proceeding.
- Document that the stable marketplace intentionally follows the latest published tag, which may
  lag source metadata while a release is being prepared.
- Add crash-recoverable approval transactions and durable JSONL appends.
- Add executable canonical schema validation, typed lifecycle vocabulary, and release/install checks.

## [1.17.1] - 2026-08-06

- Preserve heartbeat-specific labels and disclosures in `status` and guided human output.
- Add pending proposal kind metadata to the additive status JSON contract.
- Add chat response language hard-gate coverage for KO/JA/EN turn switching.

## [1.17.0] - 2026-08-06

- Localize Career Agent human UX in Korean, Japanese, and English.
- Follow the latest chat message language immediately, with profile-language fallback for message-free commands.
- Distinguish event confirmation from heartbeat review and keep heartbeat approval queue-only (`applied: false`).
- Add locale-catalog completeness and language/terminology regression coverage.

## [1.16.1] - 2026-08-06

- `job-seeker-agent` states the `Missing` / `Unknown` boundary in `SKILL.md` itself.

## [1.16.0] - 2026-08-06

- Added the P2 UX regression rubric with eight independent safety/navigation rules, ten
  known-good synthetic fixtures, eight known-bad negative controls, and five regression injections.

## [1.15.0] - 2026-08-06

- Added the thin `career_agent.py guided` frontend with canonical-state summaries, stable action
  IDs, deterministic `--choice` testing, and explicit confirmation before setup, proposal, approval,
  or recovery writes.

## [1.14.0] - 2026-08-06

- Added the PR2 progressive-disclosure explanations at setup, workspace, private-store,
  proposal/approval, evidence-state, and recovery boundaries.

## [1.13.0] - 2026-08-06

- Career Agent P0 UX contract work begins on the dedicated `feat/career-agent-ux` branch.

## [1.12.1] - 2026-08-06

- `job-seeker-agent`'s requirement table said two different things about `Conflict`, and both were
  reachable. The table now keeps `Conflict` at Decision Status and `Matched | Missing | Unknown` at
  requirement level.

## [1.12.0] - 2026-08-05

- `propose-fact` closes the last gap in the flow this feature describes: an imported document can
  now become a canonical personal fact, still gated by approval.

## [1.11.0] - 2026-08-05

- Personal facts now reach agent context under bounded, stage-relevant, confirmed-only selection.

## [1.10.0] - 2026-08-05

- Added the personal fact timeline and current personal-profile projection with fail-closed reads.

## [1.9.0] - 2026-08-05

- Added the private career-document store with content-addressed blobs and metadata-only reads.

## [1.8.0] — 2026-08-05

- Added a deterministic gate against tracking or committing personal career documents.

## [1.7.1] — 2026-08-04

- Hardened date, numeric-evidence, and matching-source validation.

## [1.7.0] - 2026-08-04

- Added an informational HTTPS endpoint-health canary and completed production-hardening gates.

## [1.6.21] - 2026-08-04

- Added clean-tree/source-commit/archive/manifest/checksum/SBOM release integrity verification.

## [1.6.20] - 2026-08-04

- Added hash-pinned runtime and verification dependency locks with deterministic SBOM verification.

## [1.6.19] - 2026-08-04

- Added critical behavior replay scenarios for Career Agent and matching/interview contracts.

## [1.6.18] - 2026-08-04

- Added a machine-readable behavior-evaluation schema and deterministic runner.

## [1.6.17] - 2026-08-04

- Completed the Career Agent architecture boundary.

## [1.6.16] - 2026-08-04

- Moved projection ownership out of the runtime façade.

## [1.6.15] - 2026-08-04

- Moved proposal/lifecycle ownership out of the runtime façade.

## [1.6.14] - 2026-08-04

- Moved multilingual routing into `routing.py`.

## [1.6.13] - 2026-08-04

- Moved canonical persistence and Vault ownership out of `runtime.py`.

## [1.6.12] — 2026-08-04

- Extracted Career Agent vocabulary and pure validation from `runtime.py`.

## [1.6.11] — 2026-08-04

- Tightened mock-interviewer readiness precedence.

## [1.6.10] — 2026-08-04

- Made mock-interviewer deep-dive selection adaptive with bounded readiness and evidence provenance.

## [1.6.9] — 2026-08-04

- Hardened E2E artifact redaction across Windows and POSIX path forms.

## [1.6.8] — 2026-08-04

- Added reproducible E2E artifact packaging and integrity verification.

## [1.6.7] — 2026-08-04

- Hardened Career Agent E2E persistence and provenance capture.

## [1.6.6] — 2026-08-04

- Split the CLI into a thin entry point with explicit runtime boundaries.

## [1.6.5] — 2026-08-04

- Added a main-merge release workflow and release-tag checker.

## [1.6.4] — 2026-08-04

- Made incomplete setup explicit/actionable and added quickstart E2E coverage.

## [1.6.3] — 2026-08-04

- Locked remaining concurrent writers and added version-bump/policy gates.

## [1.6.2] — 2026-08-03

- Hardened hooks, self-analysis contracts, and matching semantics.

## [1.6.1] — 2026-08-03

- Made Career Vault state writes atomic and synchronized verification/documentation contracts.

## [1.6.0] — 2026-08-03

- Added the Jiko Bunseki v2 user-led reflection workflow and downstream safety contracts.

## [1.5.0] — 2026-08-03

- Added status-bar/update-check documentation, context budgets, locked dependencies, and consistency checks.

## [1.4.0]

- Evidence-based v3 alignment, approval-gated career state, workspace routing, lazy job-seeker
  references, and compressed status-bar context.
