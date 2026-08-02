# tenshoku-strategy — Mistakes Log

Append-only. One row per real failure this skill produced in actual use — a wrong score, a
fabricated claim, a broken language switch, bad advice a user had to correct. Not speculative
edge cases; those go in `tests/eval.md`. Only log something that actually happened.

Review periodically (not every session). When the same pattern repeats 2-3+ times, promote it:
fix the wording in `SKILL.md` (or the logic in code, if this skill has any), re-run
`tests/eval.md` to check nothing regressed, then mark the row Promoted with what changed.
Process: [AGENTS.md § Learning From Mistakes](../../../AGENTS.md#-learning-from-mistakes).

## Log

| Date | Input (what was asked) | What happened | Expected | Status |
|---|---|---|---|---|

