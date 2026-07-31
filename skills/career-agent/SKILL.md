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
python skills/career-agent/career_agent.py run --mode chat --message "신졸이고 学チカ 경험을 정리하고 싶어요"
python skills/career-agent/career_agent.py run --mode heartbeat
python skills/career-agent/career_agent.py run --mode discover --source postings.json
python skills/career-agent/career_agent.py status
python skills/career-agent/career_agent.py approve <proposal-id> --evidence "resume line 12"
python skills/career-agent/career_agent.py rollback <version>
```

Set `CAREER_HOME` to keep local state outside the repository. Without it, the default is
`./career-home/`.

## Runtime contract

The loop records `observe → plan → act → verify → correct → persist` in `trajectories.jsonl`.
Facts are append-only in `events.jsonl`; current state is `state.json`; version snapshots live in
`versions/`. A chat run creates only a `draft` event proposal. `approve` is required before a
confirmed event reaches the ledger.

Confirmed events must include evidence. Pass one or more `--evidence` values when approving; numeric
claims without matching evidence are rejected.
Heartbeat emits at most three actions, each with its source event, stage, deadline, and confirmation
flag. `discover` accepts a local JSON export of public postings, preserves the original URL, and
deduplicates by URL (or company + role when no URL exists). It records candidates only; it never
applies.

The runtime uses the request language for response metadata (`ko`, `ja`, or `en`), keeps Japanese
career terms in the source text, and pauses when track intent is not explicit rather than inventing
facts. External search, login, CAPTCHA, application submission, email, and messaging are outside
this first local adapter.
