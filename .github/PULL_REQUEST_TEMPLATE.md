## Summary

- What contract or behavior changed?
- Why is the change in scope for this PR?

## Self-review checklist

- [ ] Existing `Unknown`, hard-conflict, interest-independence, and legacy read-only behavior is preserved.
- [ ] No uncalibrated candidate-outcome percentage, composite score, or proprietary algorithm claim was added.
- [ ] Untrusted career data cannot become instruction, and action gates/blockers remain visible.
- [ ] Tests cover the changed behavior, including Windows paths where relevant.
- [ ] If this PR touches a non-test/non-doc file under `skills/`, `_shared/`, `scripts/`, or
      `hooks/`: both `plugin.json`s were bumped, `CHANGELOG.md` has a new entry, and all three
      READMEs' `Current release` line was updated (`scripts/check_version_bump.py` enforces this —
      "consistent" means bumped-and-consistent, not left alone).
- [ ] No personal data, secrets, or generated runtime state is included.

## Verification

List the exact commands run and their results. Note any unavailable environment or remaining
limitation explicitly.
