# Changelog

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
- The historical comparison takes `--type` and `--company`. Comparing two resumes should not also
  disclose every certificate and every company's ES. It stays metadata-only in this mode too, since
  document text extraction is a v1 non-goal — the user opens the files themselves.
- `--candidate-profile` validates each value against the domain `_shared/schemas.yml` states and
  reports a violation as `invalid` with a null value. A fact's `value` is otherwise unconstrained and
  the consuming skill is told to quote it exactly, so an unchecked `jlpt_level: N9` became a schema
  violation two skills downstream. Checked per field, so one bad record does not take the others down.
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
