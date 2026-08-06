# First 10 Minutes

## Goal

Move from a fresh local setup to one explicitly approved, provenance-linked personal fact.

## Starting state

- No Career Vault, workspace projection, or private store exists.
- The only document is the committed `synthetic-resume.example.txt` fixture.

## Synthetic data

The document says only that a fictional candidate has Python platform-maintenance experience. It is
copied into a temporary private store outside the Git worktree; it is never treated as a command or
as an automatically confirmed fact.

## Commands

```bash
python scripts/run_workflows.py --workflow first-10-minutes --format human
```

The runner executes these canonical operations in order:

```text
career_agent.py setup
career_agent.py status
career_agent.py private-import
career_agent.py propose-fact
career_agent.py proposals --id <proposal-id>
career_agent.py approve <proposal-id> --evidence <user evidence>
career_agent.py personal-profile --as-of 2026-08-06
```

## Expected invariants

- Setup explains the Vault at the setup boundary.
- Initial status has no fabricated personal facts and explains the resolved workspace.
- Import preserves the source and says the document is not yet a confirmed fact.
- The proposal is `pending` and the canonical profile is unchanged before approval.
- Review is read-only and exposes the private-document provenance link.
- Approval is explicit and uses the existing evidence gate.
- The final personal-profile projection shows `skill/python` as `confirmed`.

## Decision point

The user decides whether to approve the reviewed proposal. Keeping it pending is valid.

## Product does not do

- It does not infer facts by reading document text.
- It does not auto-approve or submit an application.
- It does not send a message or produce an employment-outcome probability.

## Recovery

If evidence is absent, approval stops with canonical state unchanged. Repair the evidence or keep the
proposal pending, then retry the same canonical approval command.

## Repeatability

Each run uses a new temporary vault, workspace, private store, and synthetic source copy. No user
data or committed runtime state is required.
