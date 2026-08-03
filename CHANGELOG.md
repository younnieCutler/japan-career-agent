# Changelog

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
