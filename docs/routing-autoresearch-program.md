# Routing Autoresearch — research agent program

You are running one routing experiment. This file is everything you need; reading the evaluator,
the runner, or the benchmark fixtures is not required and, for the fixtures, is out of contract.

## The loop

```bash
python scripts/routing_autoresearch.py --baseline -m "..."   # operator only, once per harness change
python scripts/routing_autoresearch.py -m "<hypothesis>"     # score one candidate
```

One hypothesis per run. Edit, score, read the verdict, keep or revert, then the next hypothesis.
Verdicts:

| Verdict | Meaning | What to do |
| --- | --- | --- |
| `provisional_keep` | Gates 0–5 passed; this is now the score to beat | keep the edit, start the next hypothesis |
| `discard` | a gate rejected it | revert the edit, and do not retry the same shape |
| `infra_error` | Gate 6 was not decidable here | not your candidate's fault; carry on |
| `INVALID` | you edited something you may not | revert everything outside the mutation surface |
| `CRASH` | the subject does not load | fix the syntax error you introduced |

## Mutation surface

You may edit exactly two files:

- `skills/career-agent/references/routing.yml` — the lexicon. This is where almost every
  hypothesis belongs.
- `skills/career-agent/routing.py` — the matching logic. Only when an experiment explicitly calls
  for it; a lexicon change is nearly always the smaller answer.

Anything else — the evaluator, the runner, the contract tests, the fixtures, other production
files — makes the run INVALID before any gate is read. The runner compares a digest of every
judging file against the baseline row, so this is enforced, not requested.

## What the subject does

`skill_context()` picks the reference for a message. Four functions decide it, all on the
lowercased message, all plain substring matching:

1. `infer_track(message, requested)` — an explicit `track` argument wins. Otherwise the
   `track.shinsotsu` terms are tested **before** `track.chuto`, so a chuto term cannot override a
   shinsotsu one. A stated graduation year ("27卒", "class of 2027") implies shinsotsu. `第二新卒`
   is rewritten to `中途` before any lookup, because it contains `新卒` as a substring.
2. `stage_for(message, track, current_stage)` — returns the first `stage_alias` group whose terms
   match, **in file order**, mapped to that track's stage list. No match falls back to the current
   stage, then to the track's first stage.
3. `explicit_stage_alias(message)` — the same scan, but skipping the track-only aliases `chuto`
   and `shinsotsu`. Returns `None` when the message names no task. Onboarding uses this to decide
   whether to route or ask, so forcing a non-`None` answer here is a Gate 0 failure.
4. `skill_context(...)` — **only when the track is `chuto`**, the first `message_context` entry
   whose terms match, in file order, selects one reference. Otherwise the stage fallback applies.
   This is why a lexicon change to `message_context` cannot break the shinsotsu boundary; only
   `track` and `stage_alias` can.

`term_present()` is a plain substring test, except for the short ASCII terms in
`_WORD_BOUNDARY_TERMS` (`es`, `jd`), which require non-alphanumeric neighbours. Do not reach for
`\b` — it treats CJK as word characters, so it never matches inside a Japanese or Korean sentence.

**Order is precedence.** Both `message_context` and `stage_alias` return on first match, and their
current order is the order the rules were written in, not an ordering by specificity. Reordering is
a legitimate one-line hypothesis.

## Gates, in the order they are read

A candidate stops at the first gate it fails; nothing after it is even measured.

| Gate | Rejects |
| --- | --- |
| 0 | any decision-philosophy failure — inventing an intent the user did not state, or moving the lifecycle stage to make a route fire. Absolute zero. |
| 1 | any critical failure the current best did not have. A **set** comparison: trading one critical failure for another is a DISCARD even though the count is unchanged. |
| 2 | any focused regression test failing |
| 3 | held-out correctness below the current best |
| 4 | any fallback failure the current best did not have |
| 5 | more than 25 changed production lines, or more than 12 added routing terms |
| 6 | the canonical repository matrix, on promotion only |
| 7 | equal held-out correctness without being simpler (fewer routing terms) |

Accuracy never buys back an earlier gate. A candidate that raises held-out correctness while
sending a new-graduate message to the mid-career track is rejected at Gate 1, and its accuracy is
never read.

## What you see, and what you do not

The runner reports aggregate held-out counts only — never which held-out fixture failed, or what
it contained. That is deliberate: a rule written against a specific benchmark utterance is
memorisation, not routing. Form hypotheses from the language, from the development set, and from
the structure above.

You may not open the frozen holdout fixtures. The runner cannot stop you from reading a file, but
a candidate built from them is out of contract, and the anti-gaming check rejects any production
rule that quotes a whole benchmark utterance or names a fixture.

## Hypothesis quality

The benchmark rewards generalisation over coverage. A term that only ever matches one phrasing is
worth little; a term that captures how people actually write the intent is worth a lot.

Known weak spots in the current lexicon, from the baseline measurement:

- **Negation** — the keyword is present and the intent is its opposite ("年収交渉は必要ありません。
  入社手続きだけ確認したいです"). First-match ordering cannot see this. The remaining critical
  failures are all of this shape, and they may not be solvable in the lexicon at all.
- **Paraphrase** — groups list fully-fused compounds (`年収交渉`) and miss the split or plain forms
  a user is more likely to write.
- **Redundant compounds** — several groups list three compounds of one word where the bare word
  subsumes all three. Collapsing them is an improvement under Gate 7.
- **Multilingual asymmetry** — a group often covers JA well, KO partially, EN barely, or has
  hybrid spellings that match neither language (`학チカ` versus `학チ카`).

## Hard rules

- One hypothesis per run, one owning layer.
- No new dependencies, no schema change, no release or version metadata edits.
- Do not touch tests to make a candidate pass. Do not delete or skip a fixture.
- Do not widen a rule until it captures a generic request; the non-capture fixtures exist to catch
  exactly that, and they are Gate 1.
- If a hypothesis needs more than 25 changed lines, it is more than one hypothesis.

## When to stop

Stop and report rather than continuing if any of these hold:

- The benchmark is at 100% with every hard gate passing.
- Twenty consecutive valid experiments produced no improvement.
- Further improvement would require exceeding the complexity budget.
- The remaining failures are not lexical. Negation and precedence in particular may be an
  architectural limit of first-match phrase routing rather than a missing term — say so, and let a
  human decide whether that warrants a different experiment class.

Reference: `docs/ROUTING_AUTORESEARCH.md` for the contract decisions behind these gates, and
`docs/routing-autoresearch-results.tsv` for what has already been tried.
