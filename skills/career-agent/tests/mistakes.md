# career-agent — Mistakes Log

Append-only. One row per real failure this skill produced in actual use — wrong stage routing,
a bad heartbeat suggestion, an event that shouldn't have confirmed, a doctor check that missed
something. Not speculative edge cases; those belong in `test_career_agent.py` (deterministic CLI
behavior, already covered) or a future `tests/eval.md` (none yet — this skill is code-driven, not
prompt-only, so most bugs so far have been fixed directly with a regression test instead).

Review periodically (not every session). When the same pattern repeats 2-3+ times, promote it:
fix the wording in `SKILL.md`, the logic in `career_agent.py`, or add a case to
`test_career_agent.py` — whichever the failure actually calls for — then re-run
`python3 test_career_agent.py` to check nothing regressed, then mark the row Promoted with what
changed. Process: [AGENTS.md § Learning From Mistakes](file:///Users/macbook/dev/career/japan-recruit-skills/AGENTS.md#-learning-from-mistakes).

## Log

| Date | Input (what was asked) | What happened | Expected | Status |
|---|---|---|---|---|
