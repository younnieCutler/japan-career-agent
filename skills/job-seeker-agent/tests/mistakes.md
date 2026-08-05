# job-seeker-agent — Mistakes Log

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
| 2026-08-05 | `no-metrics-achievement` judge fixture: duty-only 職務経歴 + a JD demanding quantified results | The 実績 draft, labelled 「現時点で確認できる事実のみ」, appended outcomes the source never states: 「業務の属人化解消に貢献」, 「現場の利用状況を把握」, 「システムの安定稼働」. The fixture lists only the duties. | A duty with no confirmed result stays a duty. `SKILL.md:54` bans fabricating a STAR story or responsibility, not just a metric. | Logged |
| 2026-08-05 | Same fixture, weakened-`SKILL.md` run | 物流ドメイン知識 was marked `Matched寄り` because the employer is described as 物流IT — a company-type inference, and a label that does not exist. | Domain knowledge needs a candidate statement, not an employer's industry (`SKILL.md:51-52`). The vocabulary is exactly `Matched`/`Missing`/`Unknown` (`SKILL.md:55`); `Matched寄り` and `Unknown（Missing寄り）` are not in it. | Logged |
| 2026-08-05 | `conflict-interest-offset` judge fixture: JD requires pandas, profile states 「pandasは未経験」 | The same fixture, run three times against an unmodified `SKILL.md`, used the `Conflict` label 9, 3, and 0 times. Every run followed the skill file — because it says both things. Output is not deterministic on this axis. | `SKILL.md:103`'s table header allows only `Matched / Missing / Unknown`, while `:104` says to mark `Conflict` for an evidenced hard-requirement disagreement. `_shared/decision_philosophy.md:34` gives Requirement no `Conflict` value at all; `:30` makes `Conflict` a **Decision**-level state. The two are not reconcilable as written. | Logged — needs a decision, not a wording fix. Affects every requirement table, and blocks any regression experiment on this skill: a control that varies 0-to-9 cannot show a treatment effect. Reproduced across 3 independent runs, so the usual "wait for the pattern to repeat" bar is already met. |

