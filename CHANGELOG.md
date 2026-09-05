# Changelog

## [2.28.0] - 2026-09-05

- Extract the complete CLI argument contract from `command_line.py` into `cli_parser.py` while preserving `command_line.build_parser`, `runtime.build_parser`, command semantics, output projection, and process exit behavior.
- Register `cli_parser` as a first-class CLI boundary in the executable architecture guard and move canonical `build_parser` ownership there, so application and GUI modules cannot depend on the extracted parser layer.

## [2.27.0] - 2026-09-04

- Make `npm install -g japan-career-agent` the self-contained default install. npm now fetches a pinned uv 0.12.7 archive from the official immutable release, verifies its SHA-256 digest, and uses a package-private managed Python to install the exact matching PyPI runtime; users do not need to preinstall Python, uv, or pipx, and existing Python environments are not modified.
- Make the installed npm command use only that private runtime, keep `npx` and direct uv/pipx paths as optional alternatives, and verify the real global-install contract in repository and post-publish smoke tests.

## [2.26.0] - 2026-09-04

- Make the zero-argument command the thin default: prepare only an empty local record when needed and open the existing GUI. Explicit `ui` stays write-free and the full CLI remains available.
- Remove raw internal vocabulary from Korean/Japanese GUI copy and lock a three-company application scenario where reusable confirmed evidence keeps every application to JD paste plus submit.

## [2.25.0] - 2026-09-03

- Add local TXT/DOCX/PDF import to the existing evidence-gated career capture flow.
- Localize execution-plan and Skill-invocation statuses in Korean and Japanese human output.

## [2.24.0] - 2026-09-03

- Make the local GUI start from what a job seeker already has instead of from internal hierarchy. An empty Vault can paste existing career material into an unassigned draft, experience capture can begin before a Project exists, and the application screen accepts a JD first. Company and position values are filled only from explicit labelled lines; free prose is never guessed into identity fields.
- Reduce repeated input without weakening evidence controls. JD text can preselect up to three confirmed, externally usable experiences only when their visible text overlaps; experience, Context, and Project forms progressively reveal optional detail; and multiple ordinary Context/Project drafts can be reviewed from their server proposals and approved from one user action. Relationship-conflicted Projects are excluded, approval stops on the first failure, and no new canonical write path, schema, or backend batch transaction is introduced.

## [2.23.0] - 2026-09-03

- Let an initialized but empty Vault start from existing career material instead of making the user create Context/Project structure first. `guided` now exposes the existing career-inventory workflow first when canonical `readiness.bootstrap_suggested` is true, stores pasted resume, career-history, or notes text only as an unplaced transient draft, and keeps review/approval blocked until that draft is connected to a confirmed project. No fact, context, project, or canonical event is inferred from the pasted text.

## [2.22.0] - 2026-09-03

- Let a person using interactive `guided` finish the selected action in the same terminal run. Missing task text, setup track/year, approval evidence, and write confirmation are prompted in place instead of returning a CLI recipe that requires a second invocation. Non-interactive JSON, plugin, and scripted callers keep the existing explicit argument/confirmation contract, and every write still goes through the same canonical approval and persistence gates.

## [2.21.0] - 2026-09-02

- Add a deterministic, host-independent L0-L3 review policy and authenticated judgment API. Application judgments are always classified L3 by the server, phase writes stay append-only, the Host can record Agent assessment through the CLI without Python calling an LLM, and the browser withholds unresolved evidence references rather than presenting syntax as evidence.
- Wire Human Judgment into active application records in the production React GUI. The user records an initial view before Agent advice can appear, sees an honest waiting state when no assessment exists, compares Human and Agent judgments, records a final decision and optional later outcome, and receives the same product copy in Korean, Japanese, and English.

## [2.20.0] - 2026-09-02

- Add the Human Oversight foundation for consequential career decisions: an append-only local judgment ledger records the human initial judgment, agent assessment, human final judgment, and later outcome without mutating canonical career evidence. Phase ordering is serialized under the Vault lock, `Unknown` stays explicit, and architecture/test-registration gates own the new module.
- Add a human-first React judgment gate that keeps agent analysis hidden until the initial human judgment is persisted, surfaces human/agent divergence, and keeps the existing Capture → Review → Confirm approval boundary separate. The oversight contract documents the L0-L3 impact model and limits blind judgment to consequential L3 decisions.

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
  of a bare name, and reading a university as an employer puts coursework into a 職務経歴書 as a job.
- Record evidence about something that did not happen at a job. A seminar, a thesis, a club, a
  volunteer shift and a personal project carry the same payload a work event does -- role, problem,
  actions, individual contribution, team result, metrics, confidentiality -- and share its
  validator, including the rule that a number must appear in the evidence before it can be
  confirmed. They are a separate type because storing a university seminar as a work event would
  say the user was employed there, and every work-scoped read would start returning coursework as
  work history.

## [1.24.0] - 2026-08-10

- Add PROJECT as the context a work event happened in and link work events to projects without duplicating canonical evidence.
- Add `weekly-review`, `projects`, `project-timeline`, `add-project`, `link-work-event`, `evidence-pool`, `maintenance-check`, and independent readiness dimensions.

## [1.23.0] - 2026-08-10

- Separate career readiness from job-search intent and add the `career-maintenance` workflow with explicit user-owned intent transitions.
- Add `work_event`, `review-work-event`, `work-events`, intent lexicons, and `routing-eval-v3` while keeping canonical evidence append-only.

## [1.22.0] - 2026-08-08

- Match 학チカ and 학チ카 everywhere, collapse redundant routing compounds, and improve frozen routing benchmark correctness.

## [1.21.0] - 2026-08-08

- Add `routing-eval-v2`, rebalance benchmark languages, and scope experiment logs by benchmark version.

## [1.20.0] - 2026-08-08

- Add the Routing Autoresearch agent program, mutation/gate protocol, and checked capsule for fast deterministic routing experiments.

## [1.19.0] - 2026-08-08

- Add the frozen routing benchmark and autoresearch runner with decision-philosophy, regression, held-out, fallback, complexity, and canonical-matrix gates.

## [1.18.1] - 2026-08-08

- Route ten specific chuto execution topics to existing `tenshoku-strategy` references while preserving lifecycle routing and generic fallbacks.

## [1.18.0] - 2026-08-08

- Add progressive Career Agent onboarding, explicit track/task routing, and safer shinsotsu/chuto intent handling.

## [1.17.3] - 2026-08-08

- Skip `.worktrees` in `scripts/check_policy.py` so ignored worktree copies do not trip repository policy scans.

## [1.17.2] - 2026-08-06

- Make the stable Codex marketplace channel resolve to the immutable `v1.17.1` tag and add crash-recoverable approval transactions.

## [1.17.1] - 2026-08-06

- Preserve heartbeat labels, proposal metadata, and multilingual chat-language hard-gate coverage.

## [1.17.0] - 2026-08-06

- Localize Career Agent human UX in Korean, Japanese, and English and separate heartbeat review from confirmation.

## [1.16.1] - 2026-08-06

- Clarify `Missing` versus `Unknown` in job-seeker requirements and preserve no-offset decision semantics.

## [1.16.0] - 2026-08-06

- Add the P2 UX regression rubric, deterministic calibration coverage, and provider-neutral advisory calibration seam.

## [1.15.0] - 2026-08-06

- Add the thin `career_agent.py guided` frontend with canonical summaries and explicit confirmation gates.

## [1.14.0] - 2026-08-06

- Add progressive-disclosure explanations and exactly three reproducible synthetic workflows.

## [1.13.0] - 2026-08-06

- Begin the Career Agent P0 UX contract work on a dedicated branch.

## [1.12.1] - 2026-08-06

- Resolve the `Missing`/`Unknown`/`Conflict` terminology contradiction in `job-seeker-agent`.

## [1.12.0] - 2026-08-05

- Add `propose-fact`, approval preflight, durable private-document evidence links, and fact supersession validation.

## [1.11.0] - 2026-08-05

- Add bounded stage-relevant personal context, historical comparison, candidate-profile projection, and strict supersession/date rules.

## [1.10.0] - 2026-08-05

- Add the personal fact timeline, current personal-profile projection, explicit Unknown/Conflict states, and document currency projection.

## [1.9.0] - 2026-08-05

- Add the private career-document store with content-addressed blobs, metadata-only listing, safe root resolution, and stray-document diagnostics.

## [1.8.0] — 2026-08-05

- Add deterministic private-data commit gates, staged-blob inspection, synthetic fixture rules, and pre-commit integration.

## [1.7.1] — 2026-08-04

- Harden date, numeric-claim, matching-method, and GitHub Actions pinning checks.

## [1.7.0] - 2026-08-04

- Add an informational HTTPS endpoint-health canary and complete deterministic production-hardening release checks.

## [1.6.21] - 2026-08-04

- Add clean-tree/source-commit/archive/secret/checksum/SBOM release integrity verification.

## [1.6.20] - 2026-08-04

- Add hash-pinned runtime/dev locks and deterministic CycloneDX SBOM generation.

## [1.6.19] - 2026-08-04

- Add critical behavior-replay scenarios across interview, matching, and Career Agent boundaries.

## [1.6.18] - 2026-08-04

- Add the machine-readable behavior-evaluation schema and deterministic adapter-based runner.

## [1.6.17] - 2026-08-04

- Complete the staged Career Agent architecture extraction and reduce the boundary guard to final PASS.

## [1.6.16] - 2026-08-04

- Move workspace/pipeline projection ownership into `projection.py`.

## [1.6.15] - 2026-08-04

- Move proposal creation and lifecycle/approval ownership into dedicated modules.

## [1.6.14] - 2026-08-04

- Move multilingual routing into `routing.py`.

## [1.6.13] - 2026-08-04

- Move canonical persistence and Vault ownership out of the runtime facade.

## [1.6.12] — 2026-08-04

- Extract Career Agent vocabulary/validation and add the staged architecture boundary guard.

## [1.6.11] — 2026-08-04

- Tighten mock-interviewer readiness precedence and adaptive terminology contracts.

## [1.6.10] — 2026-08-04

- Make mock-interviewer deep-dive selection adaptive with a session-local coverage ledger.

## [1.6.9] — 2026-08-04

- Harden E2E artifact redaction across Windows and POSIX path forms.

## [1.6.8] — 2026-08-04

- Add reproducible E2E artifact packaging with source/runtime identity and integrity verification.

## [1.6.7] — 2026-08-04

- Harden Career Agent E2E persistence, provenance, UTF-8 ingestion, and proposal resolution recording.

## [1.6.6] — 2026-08-04

- Split the CLI into a thin entry point with explicit runtime boundaries and golden CLI projections.

## [1.6.5] — 2026-08-04

- Add main-merge release workflow and release-tag consistency checks.

## [1.6.4] — 2026-08-04

- Make incomplete setup explicit/actionable and add Quickstart/demo/E2E approval coverage.

## [1.6.3] — 2026-08-04

- Lock Career Vault writers, unify workspace resolution, add static policy guards, and introduce the version-bump gate.

## [1.6.2] — 2026-08-03

- Harden status-bar failure behavior, hook lifecycle portability, schema validation, and matching gap semantics.

## [1.6.1] — 2026-08-03

- Make Career Vault writes atomic, tighten context budgets, and add executable Jiko/export/schema checks.

## [1.6.0] — 2026-08-03

- Add Jiko Bunseki v2 and harden downstream contracts so reflection values never become unreviewed career facts or recommendations.

## [1.5.0] — 2026-08-03

- Document status-bar update checks, reduce always-loaded context, add dependencies/CI/readme contracts, and fix stale architecture headings.

## [1.4.0]

- Evidence-based v3 alignment, approval-gated career state, workspace routing, lazy job-seeker references, and compressed status-bar context.
