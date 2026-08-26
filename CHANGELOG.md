# Changelog

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
  The repository, the plugin, the marketplace entry and the release product name all move together,
  because a name that is right in one manifest and stale in another is worse than either name alone.
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
  largely invisible; v2 is 76/43/41 across Japanese, Korean, and English, enforced by a test.
- Double the axes that carry the safety contract rather than inflating uniformly — negation,
  unmatched, generic interview and research, ambiguity, and both track boundaries.
- Scope the experiment log to one benchmark version: a v1 best counts 56 cases and a v2 best
  counts 134, so comparing a candidate across versions is meaningless rather than merely noisy.

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
  returns KEEP, DISCARD, CRASH, or INVALID without a human judging each result. The mutation
  surface is `references/routing.yml` and `routing.py`; a diff that reaches outside it, or an
  evaluator or fixture digest that differs from the baseline, is rejected before any gate is read.
- Gate the loop lexicographically — decision philosophy, safety and non-capture, focused
  regressions, held-out accuracy, fallback preservation, complexity, canonical matrix — so routing
  accuracy can never offset a contract violation.
- Pin every file that decides a verdict — evaluator, runner, and both contract-test files — into
  each results row, so a candidate cannot rewrite the logic that scores it.
- Compare critical and fallback failures as sets rather than counts: a candidate that fixes one
  failure and introduces a different one is a DISCARD even though the count is unchanged.
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
  workflow, while a bare `求人`/`공고`/`JD` routes to job-seeker-agent evidence review. A message
  that names a more specific task alongside `応募` (interview, company research, offer, or exit) now
  resolves as that task, not as a bare application.
- Route "I don't know what to do" to self-analysis without treating it as a recommendation, and only
  when the message names no more specific task.
- Classify `第二新卒` as a `chuto` mid-career hire. It contains `新卒` as a substring and was being
  read as a new graduate.
- End onboarding when a turn reaches a real stage (`career_status` becomes `active`). Existing
  Vaults keep their recorded status and previous routing behaviour.
- Show onboarding progress and an `Unknown` target role in guided output instead of reporting
  onboarding as a setup failure.

## [1.17.3] - 2026-08-08

- Skip `.worktrees` (gitignored `git worktree add` checkouts) in `scripts/check_policy.py`. A local
  worktree of another branch carries its own copy of the two files this repo already allowlists for
  historical content, and the scanner was failing on those copies.

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

- `job-seeker-agent` states the `Missing` / `Unknown` boundary in `SKILL.md` itself. The rule is not
  new — `_shared/decision_philosophy.md` already keeps absence of evidence at `Unknown`, and
  `references/evaluation_rules.md` already leaves a one-sided gap `Unknown` until the missing side is
  confirmed. It was only reachable through a lazily-routed reference, so a run that did not load it
  saw "one-sided evidence stays `Unknown`" and "a missing core skill is a `Missing` requirement"
  two lines apart with nothing choosing between them.
- `Missing` now names its precondition: comparable **confirmed candidate evidence** that does not
  meet a confirmed JD requirement. Silence in a resume or profile is not that evidence, so a
  requirement the candidate has said nothing about stays `Unknown` until they confirm it.
- No new obligation was added. Deriving a fact the candidate did not state — computing a career
  length from confirmed dates, for instance — is still neither required nor forbidden, and the
  requirement state does not depend on how firmly the JD is worded.

## [1.16.0] - 2026-08-06

- Added the P2 UX regression rubric with eight independent safety/navigation rules, ten
  known-good synthetic fixtures, eight known-bad negative controls, and five regression injections.
- Added deterministic calibration coverage to the canonical check path: all negative controls and
  injections are detected with zero false positives or false negatives and reproducible results.
- Added a provider-neutral advisory calibration seam that evaluates captured subject output and
  records a fixed three-subject by three-judge run matrix, model identity, run conditions, and
  subject/judge variance without touching canonical state.
- Documented that the deterministic evaluator is CI-safe while a network-dependent live LLM judge
  remains advisory until model variance, provider failure, runtime, and cost are calibrated.

## [1.15.0] - 2026-08-06

- Added the thin `career_agent.py guided` frontend with canonical-state summaries, stable action
  IDs, deterministic `--choice` testing, and explicit confirmation before setup, proposal, approval,
  or recovery writes.
- Distinguished guided confirmation reasons for setup, proposal creation, approval, and state
  recovery so each blocked write explains the correct next step.
- Guided actions dispatch through the existing setup, status, context, proposal, and approval
  facades; Unknown, Conflict, pending proposals, cancellation, and invalid choices remain explicit.

## [1.14.0] - 2026-08-06

- Added the PR2 progressive-disclosure explanations at setup, workspace, private-store,
  proposal/approval, evidence-state, and recovery boundaries.
- Added exactly three reproducible synthetic workflows: First 10 Minutes, Real Application, and
  Recovery, with semantic invariant checks and no guided frontend.

## [1.13.0] - 2026-08-06

- Career Agent P0 UX contract work begins on the dedicated `feat/career-agent-ux` branch.
- Major CLI operations will expose additive state, reason, allowed-transition, and unchanged-state
  metadata while preserving the existing JSON fields and approval/evidence boundaries.

## [1.12.1] - 2026-08-06

- `job-seeker-agent`'s requirement table said two different things about `Conflict`, and both were
  reachable. The table header allowed `Matched / Missing / Unknown`; the sentence directly under it
  told the reader to mark a `Conflict` on an evidenced hard-requirement disagreement. Nothing in the
  file said which one governed a requirement row.
- The cost was not cosmetic. The same input, run three times against the unmodified skill, used the
  `Conflict` label 9, 3, and 0 times. Every one of those runs followed the file — it says both
  things, so following it does not narrow the output.
- `Conflict` is a `Decision Status` value in `_shared/decision_philosophy.md`, and Requirement has
  only `Matched | Missing | Unknown` there. The skill now says so directly: a hard requirement both
  sides evidence and disagree on is `Missing` in the table, and that `Missing` is what makes the
  `Decision Status` a `Conflict`. One finding, recorded at the level each belongs to.
- **The three states stay distinct rather than collapsing into one.** `Missing` is a confirmed
  requirement the confirmed candidate evidence does not demonstrate. `Unknown` is what a requirement
  stays at when either side is absent, `Contradictory`, or `Stale`. A contradiction in the evidence
  itself is labelled on the evidence axis, which already has `Contradictory` for it.
- The no-offset invariant is unchanged and now names its level: a confirmed hard-requirement,
  work-authorization, must-have, or avoid conflict stays a `Conflict` at `Decision Status`, and
  other strengths do not offset it. Interest is still recorded separately and still reorders
  nothing, and the skill still does not decide whether to apply.
- `references/evaluation_rules.md` already described `Conflict` as decision-level. It was the
  `SKILL.md` summary that had drifted, so the reference is unchanged.

## [1.12.0] - 2026-08-05

- `propose-fact` closes the last gap in the flow this feature describes: an imported document can
  now become a canonical personal fact. Before this, a user who imported a resume still had to
  hand-edit `events.jsonl` for any of it to reach a projection.
- **The tool does not read the document.** Text extraction is a v1 non-goal, so the value comes from
  the user and the document is what they are pointing at. The response says `machine_read: false`
  rather than letting the shape of the command imply otherwise.
- The proposal is a `draft` and `approve` is the only thing that confirms it. A pending proposal
  lives in `proposals.jsonl`, not the event ledger, so an unreviewed fact does not appear in any
  projection at all.
- The evidence link is `private-document:<document_id>` and nothing else. The registry already maps
  the id to a digest and a storage path; copying either into the event would be a second source of
  truth that goes stale the moment the registry changes. A proposal naming a document that was never
  imported is rejected -- evidence that resolves to nothing looks provenance-backed and is not.
- `approve --evidence` no longer destroys that link. The flag replaces the evidence list, so a user
  adding a note would have silently deleted the reference the proposal was built around; adding a
  note is not the same statement as "this document is no longer the source".
- The fact value stays out of `title` and `summary`. A number there must appear in the evidence text
  before an event can be confirmed, and satisfying that by echoing the value into the evidence string
  would make the check circular. The value lives in the structured payload, where `validate_fact`
  governs it.
- Corrections need no new machinery: `--supersedes` reuses the existing chain, so an approved
  correction closes the previous interval and the old record stays visible in history.
- **Approval runs a full preflight before anything is written.** Validating a proposal when it is
  created is necessary and not sufficient: two corrections of the same fact are each individually
  valid and only the pair is a fork, which no single proposal can see. Inside the approval lock the
  candidate is appended to the ledger in memory and run through `derive_intervals`, the reader's own
  rule set, so the writer cannot store a state the reader would reject. Previously a fork reached
  the ledger and only the next projection reported it — by which point the invalid row was canonical.
- The document link is re-resolved at approval rather than trusted from proposal time. The private
  root can change between the two, and extra `--evidence` can name a document nobody imported.
  Existence, id uniqueness, and the blob still being on disk are all checked, by the same function
  the proposal path uses.
- A duplicate `document_id` in the registry makes the reference unusable rather than acceptable. The
  id is the whole link, so ambiguity in it is ambiguity in the provenance — the same reason a
  duplicate fact id is rejected on read.
- Both checks run **before** the pipeline writer. An event carrying a company would otherwise have
  updated the workspace projection and then failed to reach the ledger.

## [1.11.0] - 2026-08-05

- Personal facts now reach agent context, under section 12.1's whole list rather than a subset of it:
  confirmed only, effective at `as_of`, not superseded, stage-relevant, capped at five, ordered
  newest effective date first before the cap, and marked `untrusted_career_data` /
  `instruction_authority: none`. `context` carries the selection; the unbounded `project()` output
  still requires an explicit `personal-profile` call.
- Relevance is a hardcoded stage → fact-category map, not the recording event's track. A fact
  describes the person, not the search, so a JLPT result recorded during a shinsotsu search is still
  true during a chuto one; filtering by the recording track would drop currently-true facts, which is
  the mirror image of the stale-context bug this feature exists to prevent. An empty entry is a real
  answer — company research and an aptitude test need nothing about the person. An unrecognized
  `--stage` is rejected rather than treated as "no filter", so a typo cannot widen the selection to
  the whole profile.
- A conflicting or Unknown field is withheld from context but counted in `withheld`. A model told
  nothing about salary concludes there is no salary, when the truth may be that two records disagree.
- New `personal-context` command. `--historical` is the only path to superseded documents and labels
  both sides explicitly (section 12.2); `--candidate-profile` emits confirmed facts under the
  `CANDIDATE_PROFILE` field names so the job-seeker skill can quote exact values instead of asking
  again. That command writes nothing: `data/candidate_profile.yml` is still written by a skill with
  the user confirming, and a field returned as `unknown` or `conflict` stays Unknown in the profile.
- Document bodies are not included in any context path, current or historical, and never have been.
- A successor must be effective **strictly after** its predecessor. Equal or earlier dates derive an
  `effective_to` at or before the predecessor's own `effective_from` — an interval that ends before
  it starts. Backdating a correction is a real need, but it means replacing an interval rather than
  closing one, so it is a separate operation rather than an ordinary supersession in disguise.
- Supersession topology is now settled before any date is read. A cycle contains a backwards edge by
  construction, so deriving first reported the date violation and never named the loop that caused
  it — the less useful of two true statements.
- A missing private store never breaks the historical comparison. The reason travels in the payload
  as `documents_unavailable` rather than being swallowed.
- Default personal context carries facts and **no documents**. The relevance map is keyed by fact
  category and the cap counts facts, so document metadata — type, company, purpose, effective dates,
  digest — was constrained by neither: a stage that legitimately needs nothing about the person would
  still have received the shape of every document they own, uncapped. Documents are reachable only
  through the explicit commands.
- `select_personal_context` rejects an unrecognized stage itself rather than relying on the CLI in
  front of it. A missing map entry means "no category filter", and the selector is a public boundary
  symbol other code can call without going through argparse; a guard only at the outermost layer is
  a guard the next caller skips.
- The historical comparison **requires** a request to name what it is asking for: `--type`,
  `--company`, or `--document-id`. Comparing two resumes should not also disclose every certificate
  and every company's ES, and leaving the filters optional meant the short form still did. Sweeping
  the whole store needs an explicit `--all-documents`, so full disclosure is a decision rather than
  a default. `--document-id` is repeatable, because a type filter still returns three historical
  resumes when the question named two. It stays metadata-only in this mode too, since document text
  extraction is a v1 non-goal — the user opens the files themselves.
- The historical comparison reports documents that are neither current nor superseded — a contested
  date, a future date, no date at all — in an `unresolved` bucket instead of dropping them. In an
  explicit query, losing a document the user asked about is worse than showing an awkward state.
- `--candidate-profile` validates each value against the domain `_shared/schemas.yml` states and
  reports a violation as `invalid` with a null value. A fact's `value` is otherwise unconstrained and
  the consuming skill is told to quote it exactly, so an unchecked `jlpt_level: N9` became a schema
  violation two skills downstream. Checked per field, so one bad record does not take the others down.
- A withheld field withholds the **value**, not just the `value` key. A `conflict` projection carries
  its `candidates`, each with the value that caused the conflict, so passing the entry through handed
  the consumer exactly the values the state said it may not use; an `invalid` reason that quoted the
  offending value smuggled it back the same way. Non-confirmed fields now travel as state, a reason
  built from constants, and counts — the rule default context already followed.
- `personal-context` rejects an argument that does not apply to the chosen mode instead of accepting
  and ignoring it. An ignored `--type` claims a filter that was never applied.
- `run --mode chat` carries the same `personal_context` block, built by the same selector as the
  shared `context` command. Two selectors would eventually disagree about what "current" means.
  `references/shared-vault-context.md` now states what consumers may do with it.

## [1.10.0] - 2026-08-05

- Added the personal fact timeline and the current personal-profile projection
  (`skills/career-agent/personal_timeline.py`) with two new commands: `personal-profile` and
  `personal-timeline`.
- Facts extend the existing append-only career event ledger rather than opening a second canonical
  state store. An event may carry a `fact` object, and the ledger's long-declared but never written
  `superseded` status finally means something — derived from the forward `supersedes` link, not
  stamped by hand.
- `effective_to` is derived and cannot be hand-authored: when B supersedes A and `B.effective_from`
  is known, `A.effective_to` becomes the day before it. When `B.effective_from` is Unknown, both
  records are reported as a conflict from `A.effective_from` onward instead of resolving
  newest-wins, because a record with no effective date has no defensible position in the chain.
- Every projected field carries an explicit `state` of `confirmed`, `unknown`, or `conflict`.
  `unknown` and `conflict` both set `value` to null, so a consumer that reads `value` and ignores
  `state` gets nothing rather than a wrong answer. `history_available` reports that history exists
  without leaking the stale value into `value`. Expired qualifications stay visible in history and
  are never presented as currently valid. A confirmed fact whose value is an explicit null projects
  as `unknown`, not as `confirmed` with a null payload — `Unknown` has one serialized shape, and a
  second spelling of it is one every consumer would have to learn. A null colliding with a real
  value is a conflict: the records disagree about whether the value is known.
- `private-list` takes `--as-of` and derives each document's `current` / `superseded` /
  `not_yet_effective` / `unknown_effective_date` state and its `effective_to` from `effective_from`,
  using the same rule the fact timeline uses. Phase 2 stores documents as `observed` only, so this
  is where document currency is decided; import order never decides it. Two documents sharing the
  newest effective date are reported as a conflict rather than ordered arbitrarily, and documents
  sharing any effective date are not treated as each other's successor — doing so would derive an
  `effective_to` one day before the record's own `effective_from`.
- The fact projection revalidates every fact-bearing row it reads and fails closed. The ledger is a
  hand-editable file, and a row no writer would have accepted — a confirmed fact with no evidence,
  an impossible `occurred_at` — must not reach a projection whose output crosses into agent context.
  Events without a `fact` object are untouched.
- A draft fact never enters the projection and never retires a confirmed one. Letting an unapproved
  proposal close an interval would route a state change around the approval gate.
- `as_of` is a required parameter on every function in the timeline, projection, and context
  path, and none of them reads a clock. The default is injected once, at the CLI boundary, via
  `--as-of`. `select_context` and `context_eligible` take it too, so the Vault context path is now
  reproducible for a fixed date instead of changing at midnight.
- The personal projection is **not** injected into `context` yet. Section 12.1 requires track/stage
  relevance and a selection cap on personal context and both are phase 4; until then, wiring the
  whole profile into the model-facing payload would be exactly the unbounded personal context that
  section warns about. Use `personal-profile` explicitly.
- Supersession is validated as a single acyclic chain of confirmed facts inside one logical fact
  key. Both ends of a link must be confirmed, so an unapproved draft cannot become a predecessor and
  make a confirmed field report a conflict it did not cause; a successor must share the
  predecessor's `category` and `key`, so a JLPT record cannot close a compensation record's
  interval; a predecessor may have at most one confirmed successor, since a fork would let each
  successor derive a different `effective_to` and make the projection depend on ledger order; and
  the chain may not loop. A mutual supersession passes every per-node check while deriving
  `effective_to` values that precede their own `effective_from`, and the projection would then
  report an ordinary `Unknown` for what is actually corrupt history.
- Added `validation.iso_date` as the single calendar-date parser and fixed a real divergence it
  exposes: a malformed `expires_on` made a context note **ineligible** rather than permanently
  non-expiring. The lenient path was the one feeding the model, while `doctor` reported the same
  value as a hard error. Date fields are matched against the whole string: parsing a ten-character
  prefix accepted `2026-01-20junk` and `2026-01-20T99:99:99Z` by discarding the part that made them
  wrong. `occurred_at` is validated by `validation.iso_timestamp`, which parses the time component
  instead of pattern-matching around it and requires a full UTC instant — the trailing `Z`, and not
  a bare date, which is a date rather than an instant. Previously only `deadline` was calendar-checked
  at all, so an impossible date could enter the ledger through the field every projection orders by,
  and an offset or naive local time would have stored instants in notations that sort differently as
  strings. `utc_now()` is the only thing that has ever written an `occurred_at` here, so there is no
  legacy shape to accommodate.
- A fact-bearing event may only be `draft` or `confirmed`. `superseded` is derived from another
  fact's `supersedes` link, so a stored copy is a second way to say the same thing and the two can
  disagree; hand-writing it also removed a fact from the projection with no successor and no record
  of why. Ordinary career events still accept the status.
- Conflict candidates are ordered by effective date, then fact id, before the selection cap is
  applied. Capping unordered input made the visible subset depend on ledger order even though the
  conflict itself did not.
- A duplicate fact id is rejected on read. Per-row validation only checks that an id is present, so
  a hand-edited ledger could repeat one, and every `supersedes` link resolves its target by id — the
  same history in a different order would then supersede a different record. All duplicate ids are
  collected and sorted into one message so the failure is order-independent too.

## [1.9.0] - 2026-08-05

- Added the private career-document store (`skills/career-agent/private_store.py`) with three new
  CLI commands: `private-doctor`, `private-import`, and `private-list`.
- The canonical private root cannot resolve inside any Git worktree. Resolution order is
  `--private-home`, `CAREER_PRIVATE_HOME`, `<CAREER_VAULT>/private` (only when the Vault itself is
  outside every worktree), then a user-local default. An unsafe root fails with an actionable error
  naming the offending worktree instead of silently storing documents where `git add -f` can reach
  them.
- Import copies and verifies; it never moves or deletes the original. Bytes are stored
  content-addressed by SHA-256 in one flat `blobs/` directory and verified after publication, so
  identical bytes imported under two logical keys are stored exactly once and referenced by two
  independent records. Document type, company, purpose and original filename are properties of the
  record, never of the storage path. Re-importing identical bytes under the same logical key is
  idempotent and records a re-observation rather than a new version.
- Import records observation only: every record is `observed`, and currency, `effective_to`, and
  supersession are left to the projection, which gets an explicit `as_of`. Deciding currency at
  import time would make a 2024 resume imported after a 2026 one the current one, recreating the
  stale-context contamination this feature exists to prevent. Document version chains remain scoped
  by logical identity, so an ES for one company is never confused with an ES for another. Importing
  records the artifact only; no claim becomes a canonical fact.
- One import appends exactly one canonical registry line, so a crash cannot leave two documents both
  claiming to be current — a lock serializes processes but does nothing about a partial sequence. A
  blob published before a failed registry append is left as an inert, unreferenced orphan, reported
  by `private-doctor` and reused by the next import of the same bytes rather than silently deleted.
- `private-doctor` reports stray personal documents under `--scan-root` directories (repeatable,
  defaulting to the working directory) by reusing the commit gate's detector rather than growing a
  second one that could disagree with it. The private root itself is always excluded, and reports
  carry paths and classifications only, never document content.
- Only tool caches and dependency trees (`.git/`, `node_modules/`, `__pycache__/`, virtualenvs) are
  skipped everywhere. This repository's own ignored directories — `data/`, `career-home/`, `dist/`,
  `build/` — are skipped only at the top level of a scan root that is itself a Git worktree, so an
  explicitly configured root such as `~/Documents` is not silently blind to `data/履歴書.pdf`.
- Hitting the per-root file cap makes the stray check fail with the count and remediation advice,
  never pass with an empty finding list. A capped walk is an incomplete answer, and rendering "I
  stopped looking" as "nothing found" is the one way this check could actively mislead.
- The private commands resolve their own root and never require an initialized Career Vault.
- `private-list` returns metadata only; document bodies are never printed.
- Added `persistence.atomic_write_bytes` for binary blobs, and registered the new module in the
  architecture boundary guard, the boundary-import test, the canonical-writer policy set, and the
  check runner. Corrected the stale canonical-writer entry that still named the `career_agent.py`
  shim instead of `persistence.py`.

## [1.8.0] — 2026-08-05

- Added `scripts/check_private_data.py`, a deterministic gate against tracking or committing
  personal career documents. It runs over every tracked file in the canonical check matrix and,
  with `--staged`, over the staged set. Detection is standard-library only: filename tokens,
  document extensions, ZIP container shape (so a renamed `.docx` is still caught), structured
  personal-field labels, and the release bundler's existing secret patterns.
- `--staged` reads the staged blob via `git cat-file`, not the working-tree file. The commit
  contains the staged bytes, so staging a document and then overwriting the worktree copy must not
  clear the gate.
- The synthetic allowlist requires an explicit declaration — `.example.` infix, `synthetic://`
  reference, or declared synthetic provenance. Directory location never suppresses detection:
  exempting `examples/`, `tests/`, or `mock/` would make them blind spots for real data. The gate
  is verified clean against the repository's own tracked content, so it cannot be normalized into
  being bypassed.
- Content detection matches filled-in personal field labels, never topic words, so the repository's
  own documentation about resumes is not flagged.
- Hardened `.gitignore` with personal-document extensions, Japanese and romanized document-name
  tokens, and `**/private/`. Romanized patterns are scoped so ordinary source names cannot collide.
- Added a tracked `.githooks/pre-commit` hook, enabled per clone with
  `git config core.hooksPath .githooks`. It fails closed, and probes candidate interpreters by
  executing them — resolving the name alone selects the non-functional Microsoft Store `python3`
  stub on Windows, which would have blocked every commit.
- Corrected the verification commands in `CONTRIBUTING.md` to the hash-pinned lock files CI uses.
- Added `docs/PRIVATE_CAREER_DATA_PRD.md`, the reviewed requirements for the private career data
  store, timeline, and fresh-context contract. Documentation only; phases 2-4 are not implemented.

## [1.7.1] — 2026-08-04

- Career Agent event validation now rejects deadlines with a syntactically valid
  `YYYY-MM-DD` shape but no real calendar date (e.g. `2026-99-99`).
- Numeric-claim confirmation now compares parsed claim tokens against parsed evidence
  tokens instead of raw substring containment, closing a false-match window (e.g. a
  `"20%"` claim matching inside `"120%"` evidence).
- `matching_v3` MHLW mapping `official_values` now uses a positive allowlist
  (`manual`/`rule_based`) instead of excluding only `heuristic_mapping`, so an
  unrecognized `method` value can no longer be misclassified as official.
- Pinned `actions/checkout` and `actions/setup-python` to commit SHA in CI and release
  workflows.

## [1.7.0] - 2026-08-04

- Added an informational HTTPS endpoint-health canary with an approved repository-variable target
  and explicit `HOST_UNAVAILABLE` classification; it does not claim agent or model execution.
- Completed the production-hardening release line with deterministic behavior replay, dependency
  locks, SBOM, source identity, checksums, and verified release bundle workflow.

## [1.6.21] - 2026-08-04

- Added clean-tree, source-commit, archive-path, local-path, secret-pattern, manifest, checksum,
  and SBOM release integrity verification.
- Added a deterministic release bundle workflow that verifies and uploads the archive, manifest,
  checksums, and SBOM before publishing release assets.

## [1.6.20] - 2026-08-04

- Added hash-pinned runtime and verification dependency locks with a lock-drift check.
- Added deterministic CycloneDX 1.5 SBOM generation and verification, and switched CI/release
  dependency installation to the locked files.

## [1.6.19] - 2026-08-04

- Added 17 critical behavior-replay scenarios for mock-interviewer, matching-simulator, and Career
  Agent, covering Unknown preservation, provenance, interest independence, readiness, user exit,
  approval, concurrency, and projection boundaries.
- Named instruction-only interview evaluation a deterministic contract replay and classified all 17
  replays separately from runtime E2E; no skill or live model execution is implied.

## [1.6.18] - 2026-08-04

- Added a machine-readable behavior-evaluation schema and a deterministic runner with a closed
  adapter registry, explicit contract-audit classifications, input/output hashes, and runtime
  identity metadata.

## [1.6.17] - 2026-08-04

- Completed the Career Agent architecture boundary: `runtime.py` is now orchestration/CLI plus
  compatibility exports, while extracted owner modules contain the domain algorithms.
- Reduced the boundary guard to a final `PASS` state and documented the ownership map.

## [1.6.16] - 2026-08-04

- Moved company slug normalization, workspace resolution, pipeline writes, event-to-state
  projection, and legacy pipeline migration into `projection.py`.
- Kept evidence and provenance in the canonical Vault ledger; `data/pipeline.yml` remains a short
  workspace projection backed by the shared atomic store.

## [1.6.15] - 2026-08-04

- Moved proposal creation, context proposals, metadata-only listing, and event construction into
  `proposals.py`.
- Moved Vault locking, approval, retry-safe state commits, failed-attempt recording, and restore
  semantics into `lifecycle.py` without changing the CLI or append-only contract.

## [1.6.14] - 2026-08-04

- Moved multilingual track, stage, skill-context, and flow-phase routing into `routing.py`.
- Removed routing from the staged runtime-facade importer allowlist while preserving public imports.

## [1.6.13] - 2026-08-04

- Moved canonical JSON/TOML/JSONL writers and Vault metadata/state ownership out of `runtime.py`.
- Preserved the public runtime compatibility surface while making the persistence and Vault modules
  independent of the runtime facade.

## [1.6.12] — 2026-08-04

- Extracted Career Agent vocabulary, typed DTO contracts, and pure event/context validation from
  `runtime.py` without changing the on-disk or CLI contract.
- Added the staged architecture boundary guard and focused tests; remaining runtime facade imports
  are reported explicitly until the later extraction PRs remove them.

## [1.6.11] — 2026-08-04

- Tightened mock-interviewer readiness precedence: material `Unknown`, unverified quantitative
  claims, and unresolved contradictions require targeted follow-up; bounded qualitative outcomes
  may be Ready without numeric measurement.
- Updated adaptive deep-dive frontmatter and added an executable contract guard to keep readiness
  rules and adaptive terminology aligned with the eval scenarios.

## [1.6.10] — 2026-08-04

- Made mock-interviewer deep-dive selection adaptive with a session-local coverage ledger,
  explicit document/user/context provenance, bounded readiness assessment, and user-confirmed
  Defensible Core summaries.
- Added regression scenarios for breadth preservation, unverified document claims, user-controlled
  exit, and approval-safe interview summaries.

## [1.6.9] — 2026-08-04

- Hardened E2E artifact redaction across Windows raw/resolved path forms and POSIX/Windows
  absolute-path detection, with regression coverage for cross-platform fixtures.

## [1.6.8] — 2026-08-04

- Added reproducible E2E artifact packaging with clean-tree/expected-commit gates, repository and
  runtime identity metadata, full text redaction scanning, explicit runtime-versus-contract skill
  classifications, fixture-correction status, and ZIP integrity verification.
- Added focused regression coverage and documented the safe packaging workflow for Career Agent
  E2E audits.

## [1.6.7] — 2026-08-04

- Hardened Career Agent E2E persistence: pipeline history now keeps only short projection metadata
  and event IDs while canonical evidence remains intact in `events.jsonl`.
- Separated proposal approval instructions from confirmed next actions and linked immutable draft
  proposal snapshots to confirmed events through a resolution record.
- Added strict UTF-8 ingestion, normalized company slugs with legacy alias preservation, explicit
  synthetic provenance/source references (synthetic postings use `synthetic://` without a fake URL),
  LF-only canonical writers, and redacted `commands.jsonl` E2E capture with fresh-vault lifecycle
  coverage. Capture now preserves invalid UTF-8 output with validity flags.

## [1.6.6] — 2026-08-04

- Split the CLI into a thin `career_agent.py` entry point with explicit runtime boundaries for
  models, routing, persistence, Vault/indexing, proposals, projection, and lifecycle APIs.
- Added golden CLI projections covering setup, status, chat proposal, proposals, approve, context,
  and doctor while excluding UUID/timestamp fields.

## [1.6.5] — 2026-08-04

- Added a main-merge release workflow that runs the full repository verification before creating
  an immutable annotated tag and GitHub Release.
- Added `scripts/check_release_tag.py` and focused tests to keep the tag SHA, both manifests,
  CHANGELOG, and all three README release markers aligned.

## [1.6.4] — 2026-08-04

- Made incomplete Career Agent setup explicit and actionable when track (or the shinsotsu
  graduation year) is missing, with a structured next command and exit 2.
- Added a read-only `proposals` metadata command and actionable evidence retry guidance for
  approval failures.
- Added a five-minute Quickstart and a fully synthetic demo workspace for the evidence-based v3
  diagnosis.
- Corrected the shinsotsu setup recovery command to request `--graduation-year` instead of
  reopening track selection.
- Added a fresh-vault Quickstart E2E regression covering setup, chat proposal, metadata lookup,
  evidence-backed approval, status, and workspace projection.
- Aligned the synthetic pipeline fixture with its confirmed conflict diagnosis and made forbidden
  outcome-field checks recursive.
- Made numeric evidence retry guidance executable as a quoted CLI-shaped command.

## [1.6.3] — 2026-08-04

- Locked four Career Vault writers (`add_proposal`, discover-postings dedupe-then-append, the
  vault-index rewrite, and `restore_state`'s checkpoint append) that previously wrote without
  `vault_lock`, so two concurrent CLI invocations on the same Vault could interleave. Added
  `fsync` to `pipeline_store.atomic_write` and routed `calibrate.py`'s rule promotion through the
  same lock + atomic path instead of a bare `write_text`.
- Unified workspace resolution: `calibrate.py`, `check_action.py`, `legacy_calibrate.py`, and
  `pipeline.py` now respect `CAREER_WORKSPACE`/`--workspace` through one shared
  `pipeline_store.resolve_workspace()`/`resolve_pipeline_path()`/`extract_workspace_flag()`
  implementation instead of a CWD-relative `data/pipeline.yml` each hardcoded independently.
- Added static policy guards for a canonical writer using bare `write_text`, a frozen legacy field
  constructed with a literal numeric value, a version-pinned plugin cache path in a hook command,
  and a bare `# noqa`.
- Fixed the version-pinned-cache-path guard to match a real Codex install's nested
  `.../plugins/cache/<plugin>/<plugin>/<version>/...` layout, not only a single cache directory
  level; the regression fixture is the exact path from the original failure, not a synthesized one.
- Added `scripts/check_version_bump.py`: a PR that changes a non-test/non-doc file under
  `skills/`, `_shared/`, `scripts/`, or `hooks/` without bumping both `plugin.json`s now fails
  `run_all_checks.py`/CI instead of silently merging unversioned.

## [1.6.2] — 2026-08-03

- Made the UserPromptSubmit launcher fail open for missing or stale plugin cache paths, unavailable
  Python, and status-bar runtime errors while visibly reporting that execution gates and deadlines
  were not checked.
- Buffered POSIX and Windows status-bar output so a runtime failure emits one degraded block and
  never leaks partial status output; a host-enforced timeout may still terminate the launcher before
  it can print any block.
- Added POSIX/Windows hook lifecycle regression coverage, including deleted-version cache paths and
  paths containing spaces or non-ASCII characters, plus a partial-output regression.
- Completed canonical `SELF_ANALYSIS_PROFILE v2` checks for known activity IDs, unique episode IDs,
  valid behavior-to-episode references, strict optional nested shapes, and derailer identifiers with
  allowed-ID diagnostics without changing the readable list/null contract or migrating legacy data.
- Changed confirmed required skill and experience gaps from `Proceed` to `Review`; preferred gaps,
  hard-conflict precedence, interest independence, and no-score semantics remain unchanged. Review
  output now includes deterministic gap-verification questions, and pipeline persistence keeps
  `match_required_gaps` separate from `match_unknowns`.
- Made manifest consistency checks address Claude/Codex files and marketplace entries by identity,
  not array order; the shared schema is now v2.3.
- Synchronized plugin manifests, README contracts, CI, and the Claude standard-hook loading rule.
- Fixed Jiko checklist export wiring so the learning-confidence slider preserves numeric,
  unanswered, and explicit-Unknown states.
- Added a deterministic release-consistency check for both plugin manifests, all README release
  markers, and the top CHANGELOG heading; CI and contributor checks now run it.
- Added `scripts/run_all_checks.py` as the single cross-platform verification entry point so local
  and CI command coverage cannot drift silently.

## [1.6.1] — 2026-08-03

- Made Career Vault JSON, TOML, and rewritten JSONL state writes atomic while preserving TOML as the
  human-editable source of truth and append-only JSONL semantics.
- Added deterministic context-budget checks, a smaller always-loaded contract, lazy development
  references, and status-bar trimming that preserves every blocker and bounded previews.
- Added executable Jiko Bunseki export regression coverage and strict canonical `SELF_ANALYSIS_PROFILE
  v2` validation; raw checklist submissions remain non-canonical.
- Synchronized CI checks, README entry points, contributor guidance, schema notes, and plugin
  manifests.

## [1.6.0] — 2026-08-03

- Added the Jiko Bunseki v2 user-led reflection workflow with twelve independent behavior
  tendencies, separated interest, self-efficacy, environment preferences, values, and episodes,
  and explicit unanswered versus `Unknown` handling.
- Added bounded academic theory references for question design and interpretation. The checklist
  remains a theory-informed reflection worksheet, not a validated assessment or recommendation
  engine.
- Hardened downstream contracts and regression tests so raw reflection values do not become
  candidate skills, `matching_v3` inputs, occupation or company recommendations, or canonical
  career context without user review and approval.
- Fixed Japanese checklist localization and Ruff CI import-order compliance.

## [1.5.0] — 2026-08-03

- Documented the status-bar version check, its 24-hour cadence, and the opt-out environment
  variable in all three README files and `AGENTS.md`.
- Reduced always-loaded agent context by moving onboarding, routing, market-flow, persistence,
  learning, and architecture details into lazy `_shared/agent_context/` references.
- Added bounded PyYAML dependency metadata, Ruff CI linting, manifest metadata parity checks, a
  safe status-bar truncation path, README contract checks, and contribution/release templates.
- Fixed the duplicate `2b` architecture heading and bumped the plugin manifests to `1.5.0`.

## [1.4.0]

- Evidence-based v3 alignment, approval-gated career state, workspace routing, lazy job-seeker
  references, and compressed status-bar context.
