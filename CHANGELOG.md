# Changelog

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
