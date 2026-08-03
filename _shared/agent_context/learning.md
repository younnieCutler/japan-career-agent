# Learning from mistakes

`tests/eval.md` covers known scenarios. Each skill's `tests/mistakes.md` is an append-only log of
actual bad outputs: date, request, observed result, expected result, and status `open`.

When a real use error occurs, record it immediately. Do not promote one sporadic or unconfirmed
case. When the same pattern repeats two or more times across sessions, promote it to the smallest
appropriate layer:

- model judgment or instruction → the skill's `SKILL.md`;
- deterministic routing or data bug → the owning code or `routing.yml`.

Re-run the relevant eval or deterministic test, then mark the row `Promoted` with a one-line pointer.
