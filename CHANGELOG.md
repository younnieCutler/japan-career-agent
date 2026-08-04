# Changelog

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
