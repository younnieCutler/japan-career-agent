---
name: career-agent
description: >
  Local-first Career Agent runtime for Japan job hunting. Routes shinsotsu and chuto requests,
  loads only the relevant existing skill context, keeps an append-only event ledger, and proposes
  grounded next actions. It never submits applications, sends messages, or edits skills.
  Use for career state, next-action, heartbeat, deadline, event approval, and public posting discovery.
---

# Career Agent

This is the orchestration layer for the existing seven skills. It does not replace them and does
not inject every `SKILL.md` into every run.

## Run

From the repository root:

```bash
VAULT=/path/to/career-agent-vault
python skills/career-agent/career_agent.py init --vault "$VAULT"
# Fill 00-control/career-profile.toml, then verify it.
python skills/career-agent/career_agent.py doctor --vault "$VAULT"
python skills/career-agent/career_agent.py run --vault "$VAULT" --mode chat --message "신졸이고 学チカ 경험을 정리하고 싶어요"
python skills/career-agent/career_agent.py run --vault "$VAULT" --mode heartbeat
python skills/career-agent/career_agent.py run --vault "$VAULT" --mode discover --source postings.json
python skills/career-agent/career_agent.py status --vault "$VAULT"
python skills/career-agent/career_agent.py approve --vault "$VAULT" <proposal-id> --evidence "resume line 12"
python skills/career-agent/career_agent.py rollback --vault "$VAULT" <version>
python skills/career-agent/career_agent.py index --vault "$VAULT"
python skills/career-agent/career_agent.py context --vault "$VAULT"
```

Set `CAREER_VAULT` instead of passing `--vault` repeatedly. The runtime never defaults to the
repository or current working directory.

## Runtime contract

`init` creates the dedicated Vault contract: `00-control` through `07-archive`, plus an internal
`.career-agent` cache. `career-profile.toml` is the human-editable profile, `career-state.toml` is
the human-readable state summary, and runtime JSON is a replaceable cache.

The loop records `observe → plan → act → verify → correct → persist` in `02-state/trajectories.jsonl`.
Facts are append-only in `02-state/events.jsonl`; version snapshots live in `.career-agent/versions/`.
A chat run creates only a `draft` event proposal. `approve` is required before a confirmed event
reaches the ledger.

`correct` actively reacts to `verify` at three points: an `approve` failure is logged (not silently
dropped) and escalated to the user; `discover` drops individually-corrupted postings and keeps the rest
of the batch instead of one bad item aborting everything (a fully-corrupted batch still safe-stops); and
a `chat` safe-stop (ambiguous track, missing shinsotsu graduation year) flags itself once it repeats 3+
times in a row, instead of asking the identical question forever.
Other trajectory sites (`heartbeat`, `index`) still record `correct` as inert bookkeeping — no active
recovery happens there.

`heartbeat` also surfaces any `career-profile.toml` field holding an ISO date within the next 7 days
(`reason: "profile_deadline"`), not only dates recorded through a confirmed event's `deadline` field.

The runtime always reads only `00-control` and `02-state`. It selects at most five verified notes
from `03-active`, `04-evidence`, `05-playbooks`, and `06-reference`; `01-capture` and `07-archive`
are never automatic context. `index` persists only note metadata, headings, wikilinks, hashes,
relative paths, and source kind in `.career-agent/vault-index.jsonl`; it never imports note bodies.

Confirmed events must include evidence. Pass one or more `--evidence` values when approving; numeric
claims without matching evidence are rejected.
Heartbeat emits at most three actions, each with its source event, stage, flow phase, deadline, and
confirmation flag. `discover` accepts a local JSON export of public postings, preserves the original
URL, and deduplicates by URL (or company + role when no URL exists). It records candidates only; it
never applies.

The runtime uses the request language for response metadata (`ko`, `ja`, or `en`), keeps Japanese
career terms in the source text, and pauses when track intent is not explicit rather than inventing
facts. External search, login, CAPTCHA, application submission, email, and messaging are outside
this first local adapter.

`references/japan-career-flow.toml` separates work stages from time-based flow phases. Its dates and
official sources are reviewed manually each year; raw YouTube subtitles and personal answer examples
are never loaded as shared runtime rules.

## Shared skill context

Candidate-side skills use this runtime's `context` command before work when `CAREER_VAULT` is set.
It returns only the shared profile, state, and selected note metadata. Follow
`references/shared-vault-context.md`; do not let individual skills create competing state in their
current directory.
