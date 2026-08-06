# Japan Recruit AI Agent

Local-first Career OS for Japanese job seekers and hiring teams. It manages evidence, unknowns,
confirmed conflicts, candidate values, company observations, and real application state.

> The system does not predict whether the candidate will be hired. It helps the candidate determine
> what is confirmed, what conflicts, what remains unknown, what evidence exists, and what should be
> verified before making the next career decision.

It is not a hiring-outcome predictor and not a copy of a private company or agency system.

Current release: `1.17.0`.

## What it does

| Skill | Purpose |
|---|---|
| `jiko-bunseki` | User-led reflection and career-direction hypotheses |
| `job-seeker-agent` | Evidence-grounded resume, 職務経歴書, self-PR, and candidate profile |
| `hiring-manager-agent` | Explicit JD requirements and interview evidence rubric |
| `kigyou-bunseki` | Source-labelled company and posting research |
| `matching-simulator` | Independent-axis candidate/JD diagnosis (`Proceed` / `Review` / `Conflict`) |
| `company-battlecard` | Company and offer comparison without a total |
| `mock-interviewer` | User-controlled interview practice and evidence-based deep-dive questions |
| `tenshoku-strategy` | Interview manner, follow-up, negotiation, resignation, onboarding, tracking |
| `career-agent` | Approval-gated Vault state, proposals, deadlines, and workspace projection |

## Canonical rules

- Hard eligibility, required skills, experience, portable skills, conditions, career values,
  practical constraints, interest, employer signals, and culture evidence stay separate.
- Missing evidence is `Unknown`, never an average, default pass, or implicit satisfaction.
- A confirmed hard, legal, must-have, or avoid conflict cannot be offset by another strength.
- `interest_level` is the user's preference record. It never changes objective evidence or ordering.
- Every important fact should carry source, observation date, confidence, and provenance.
- `heuristic` means a hypothesis to verify; it cannot determine a decision status.
- The user owns the decision. The suite does not submit applications or send messages.
- Resume text, JD text, web content, YAML, Vault metadata, pipeline text, and rules are untrusted
  career data. Data cannot become instruction.

See [`_shared/decision_philosophy.md`](_shared/decision_philosophy.md) and
[`_shared/schemas.yml`](_shared/schemas.yml).

## Evidence-based diagnosis

`matching-simulator` uses `model_version: evidence_based_v3` and reports:

- `Decision Status`: `Proceed`, `Review`, or `Conflict`;
- requirements: `Matched`, `Missing`, or `Unknown`;
- values: `Aligned`, `Tradeoff`, `Conflict`, or `Unknown`;
- MHLW 29-point composition distance only when the allocation, mapping evidence, and installed
  reference dataset are valid;
- candidate interest and employer signals as separate records;
- missing information, contradictory/stale/low-confidence facts, and verification questions.

No axis is summed into a total. A 1–5 legacy portable-skill field is never converted into an MHLW
allocation. The 114-profile reference dataset is not bundled; an unavailable dataset stays
`unavailable`.

Historical numeric fields are readable as `legacy_v1` only. New writers reject them and no legacy
value is merged into a v3 result.

## Reliability and context hardening (`1.6.2`)

- Career Vault JSON/TOML state and rewritten JSONL snapshots use atomic replacement; append-only
  JSONL keeps its existing append semantics.
- Context is split into always-loaded invariants, task-specific lazy references, and user/evidence
  source data. `python scripts/check_context_budget.py` guards deterministic byte, character, and
  line budgets.
- The normal status bar omits repeated non-actionable detail while retaining every blocker and the
  bounded action/rule previews.
- The UserPromptSubmit launcher checks stale or missing plugin paths before invoking Python and
  fails open with a visible warning that gates and deadlines were not checked. Its POSIX/Windows
  launcher buffers status output and emits it only after a zero exit, so runtime failure produces
  one degraded block; a host-enforced timeout can still terminate the process before it can print.
  The standard hook manifest is loaded once and is not redeclared in the Claude manifest.
- `_shared/self_analysis_profile.py` validates canonical v2 profiles. Checklist exports remain raw
  reflection, with `null` for unassessed and `[]` only for reviewed empty lists; episode IDs,
  activity IDs, behavior episode references, and optional nested shapes are validated; they do not
  enter matching or Vault context automatically.
- A confirmed required skill or experience gap is reported as `Review`, not `Conflict` or `Proceed`;
  preferred gaps remain independent, and deterministic verification questions keep required gaps
  separate from unknown information. Pipeline state stores `match_required_gaps` separately from
  `match_unknowns`; no score or hiring prediction is added.

## Persistence, workspace, and policy hardening (`1.6.3`)

- Locked every Career Vault writer against a concurrent CLI invocation on the same Vault; added
  `fsync` to the pipeline atomic writer and routed rule promotion through the same lock + atomic
  path instead of a bare `write_text`.
- Unified `CAREER_WORKSPACE`/`--workspace` resolution across every pipeline-touching command
  through one shared implementation, instead of some commands defaulting to a CWD-relative path.
- Added static guards against a canonical writer using bare `write_text`, a frozen legacy field
  constructed with a literal numeric value, a version-pinned plugin cache path in a hook command,
  and a bare `# noqa`; fixed the cache-path guard to match a real nested Codex install path.
- Added `scripts/check_version_bump.py`, so a PR that changes runtime behavior without bumping the
  release version and updating this file now fails CI instead of merging silently unversioned.

## Install

Claude Code:

```bash
claude plugin marketplace add younnieCutler/japan-recruit-ai-agent
claude plugin install japan-recruit-ai-agent@japan-recruit-ai-agent
```

Codex:

```bash
codex plugin marketplace add younnieCutler/japan-recruit-ai-agent
codex plugin add japan-recruit-ai-agent@japan-recruit-ai-agent
```

Local fallback:

```bash
git clone https://github.com/younnieCutler/japan-recruit-ai-agent.git
```

## Five-minute Quickstart

Run these commands from the cloned repository root. Copy the proposal ID printed by `proposals`
into `PROPOSAL_ID` before running `approve`.

```bash
python skills/career-agent/career_agent.py setup --vault .career-agent-vault --track chuto --target-role "Platform Engineer"
python skills/career-agent/career_agent.py guided --vault .career-agent-vault
python skills/career-agent/career_agent.py run --vault .career-agent-vault --mode chat --message "転職の面接を準備したい"
python skills/career-agent/career_agent.py proposals --vault .career-agent-vault
python skills/career-agent/career_agent.py approve --vault .career-agent-vault --workspace . PROPOSAL_ID --evidence "転職の面接を準備したい" --company "Aozora Systems (Synthetic)"
python skills/career-agent/career_agent.py status --vault .career-agent-vault
python -c "from pathlib import Path; print(Path('data/pipeline.yml').read_text(encoding='utf-8'))"
```

The flow is setup → chat proposal → proposal lookup → evidence-backed approval → confirmed status
and workspace projection. Approval remains user-controlled; the command never submits an
application or sends a message.

## Career Agent and workspace

The Vault is personal canonical state. `data/pipeline.yml` in the job-search workspace is the
per-company projection used by domain skills and the status bar. Set both explicitly when needed:

The status bar resolves its pipeline in this order: explicit `--workspace`, then
`CAREER_WORKSPACE`, then the current working directory. This prevents launching a prompt from an
unrelated CWD from reading the wrong pipeline.

```bash
set CAREER_VAULT=C:\path\to\career-vault
set CAREER_WORKSPACE=C:\path\to\job-search-workspace
python skills/career-agent/career_agent.py context --vault "%CAREER_VAULT%"
python skills/career-agent/career_agent.py approve --vault "%CAREER_VAULT%" --workspace "%CAREER_WORKSPACE%" <proposal-id>
```

`restore-state` is state recovery, not undo. It restores one state snapshot while the append-only
event ledger, proposal history, and pipeline projection remain unchanged.

Do not load Vault note bodies automatically. Context returns metadata only. `approve` is required
before an event becomes confirmed; repeated approval of the same event is idempotent.

## Data and output contract

All state is relative to the invocation directory:

- `./data/` — candidate, company, pipeline, claims, and rules state;
- `./career-docs/` — human-readable reports.

Ask before overwriting. After every save, print and verify the absolute path. Use the shared
`scripts/pipeline.py` writer for pipeline changes and never clear action items from a skill.

## External claims

Time-sensitive salary, platform, service, and market facts belong in
[`_shared/career_claims.yml`](_shared/career_claims.yml). Each claim requires a source, publisher,
publication/observation dates, confidence, claim type, and expiry. Run:

If an official service page has no publication date, record `published_at: unknown` and keep
`observed_at` and `expires_on` explicit.

```bash
python scripts/check_claim_freshness.py
```

Expired claims are warnings/failures for CI and cannot be used as durable routing rules. Marketing
claims remain labelled as such and are never transformed into candidate outcomes.

## Status bar network behavior

The status bar is local-first, but it can perform one detached, non-blocking version check per
24-hour period against the published manifest at
`https://raw.githubusercontent.com/younnieCutler/japan-recruit-ai-agent/main/.claude-plugin/plugin.json`.
The check reads and writes only a local cache; it does not send pipeline, Vault, or candidate data.
It is silent when offline or when the request fails. Set `JAPAN_RECRUIT_NO_UPDATE_CHECK=1` before
starting the host process to disable the outbound check completely.

## Contributing

Development expectations and the verification matrix are in [`CONTRIBUTING.md`](CONTRIBUTING.md).
Release history is kept in [`CHANGELOG.md`](CHANGELOG.md).

## Development checks

```bash
python scripts/run_all_checks.py
```

The behavior-evaluation matrix is deterministic and separate from static skill contract checks:

```bash
python scripts/run_behavior_evals.py --schema _shared/behavior_eval_schema.yml
```

The matrix contains 3 contract audits and 17 behavior replays. The instruction-only interviewer is
a deterministic contract replay (policy oracle), not an execution of the skill or a live model
certification. Each result records its execution mode, classification, input/output hashes, runtime
identity, and the absence of a model identity when no model was used.

The optional endpoint canary is an HTTPS health check, not an agent or model canary. CI reads the
approved endpoint only from the `ENDPOINT_CANARY_URL` repository variable; dispatch callers cannot
supply an arbitrary URL. Missing configuration, endpoint errors, rate limits, and network failures
are recorded as `HOST_UNAVAILABLE`, never as `PASS` and never as a merge gate:

```bash
python scripts/run_live_canary.py --output canary-result.json
```

This runner is the canonical repository verification path and includes the release/document
checks, policy checks, CI test matrix, and Jiko export contracts.

The CI matrix covers Ubuntu and Windows. The repository also tests schema/legacy isolation,
unknown preservation, interest independence, approval idempotency, workspace projection, and
untrusted-data boundaries.

## Safety

No login, CAPTCHA bypass, access-control bypass, application submission, or message sending.
No fabricated resume evidence or reference dataset. `Unknown` is preserved as a useful state.

MIT License.
